"""
N5: 코드 실행 평가 (Judge0 연동)

1. Correctness: (통과 TC / 전체 TC) × CODE_CORRECTNESS_MAX_POINTS
2. Performance: passed TC마다 time·memory raw(0~100) 산출, 실패 TC는 0,
   (Σ raw / 전체 TC) × (CODE_PERFORMANCE_MAX_POINTS / 100)
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from app.core.config import settings
from app.domain.langgraph.nodes.eval.langsmith_utils import (
    should_enable_langsmith, wrap_node_with_tracing)
from app.domain.langgraph.states import MainGraphState
from app.domain.langgraph.utils.token_tracking import (accumulate_tokens,
                                                       extract_token_usage)

logger = logging.getLogger(__name__)

TRACE_NAME_CODE_EXECUTION = "eval_code_execution"


def _scores_from_correctness_result(
    correctness_result: Any,
    test_cases: list,
    use_smart_gate_suite: bool,
) -> tuple[Any, int, int, Any]:
    """
    Worker/JudgeResult → (correctness_score 0~CODE_CORRECTNESS_MAX_POINTS, passed, total, reasoning).

    다중 TC: 통과 TC마다 (만점 / TC 수)점 — 즉 (통과 수 / 총 수) × 만점.
    """
    mx = float(settings.CODE_CORRECTNESS_MAX_POINTS)
    if use_smart_gate_suite:
        stdout = (correctness_result.output or "").strip()
        if "ALL_TESTS_PASSED" in stdout:
            return mx, 1, 1, None
        if "ASSERTION_FAILED:" in stdout:
            return 0.0, 0, 1, stdout
        if correctness_result.error:
            reasoning = "인터페이스 미준수: " + (
                correctness_result.error[:500]
                if len(correctness_result.error or "") > 500
                else (correctness_result.error or "")
            )
        else:
            reasoning = "인터페이스 미준수"
        return 0.0, 0, 1, reasoning

    n = len(test_cases)
    pt = getattr(correctness_result, "passed_test_cases", None)
    tt = getattr(correctness_result, "total_test_cases", None)
    if pt is not None and tt is not None and tt > 0:
        score = round((pt / tt) * mx, 2)
        reasoning = None if pt == tt else (correctness_result.error or None)
        return score, int(pt), int(tt), reasoning

    if correctness_result.status == "success" and n > 0:
        return round(mx, 2), n, n, None
    if correctness_result.status == "success" and n == 0:
        return round(mx * 0.5, 2), 0, 0, None
    return 0.0, 0, n, correctness_result.error


def _parse_judge_time_seconds(time_val: Any) -> Optional[float]:
    if time_val is None:
        return None
    try:
        return float(time_val)
    except (TypeError, ValueError):
        return None


def _parse_judge_memory_mb(memory_val: Any) -> Optional[float]:
    """Judge0 memory 필드는 KB 단위 문자열."""
    if memory_val is None:
        return None
    try:
        return float(memory_val) / 1024.0
    except (TypeError, ValueError):
        return None


def _per_tc_raw_performance_score(
    execution_time_sec: float,
    memory_used_mb: float,
    time_limit_sec: float,
    memory_limit_mb: float,
) -> float:
    """단일 TC의 시간·메모리 → 0~100 raw (시간 50 + 메모리 50)."""
    t = execution_time_sec
    m = memory_used_mb
    time_limit = float(time_limit_sec) if time_limit_sec else 2.0

    if t <= 0.05:
        time_score = 50.0
    elif t <= 0.2:
        time_score = 40.0
    else:
        time_score = max(
            0.0,
            40.0 * (time_limit - t) / (time_limit - 0.2) if time_limit > 0.2 else 0.0,
        )

    if m <= 10:
        memory_score = 50.0
    elif m <= 30:
        memory_score = 40.0
    else:
        mem_limit = float(memory_limit_mb) if memory_limit_mb else 256.0
        memory_score = max(
            0.0,
            40.0 * (mem_limit - m) / (mem_limit - 30.0) if mem_limit > 30 else 0.0,
        )

    return time_score + memory_score


def _performance_score_from_test_cases(
    *,
    test_case_results: Optional[list],
    time_limit_sec: float,
    memory_limit_mb: float,
    use_smart_gate_suite: bool,
    passed_count: int,
    total_count: int,
    fallback_execution_time: Optional[float],
    fallback_memory_used_mb: Optional[float],
) -> tuple[float, Optional[float], Optional[float], bool, Optional[str]]:
    """
    TC별 passed=True일 때만 raw 산출, 합을 전체 TC 수로 나눈 뒤 만점 스케일.

    Returns:
        (score, repr_execution_time, repr_memory_mb, skip_performance, skip_reason)
    """
    perf_max = float(settings.CODE_PERFORMANCE_MAX_POINTS)
    scale = perf_max / 100.0

    if use_smart_gate_suite:
        if passed_count <= 0 or total_count <= 0:
            return 0.0, None, None, True, "스마트 게이트 미통과"
        if (
            fallback_execution_time is None
            or fallback_memory_used_mb is None
        ):
            return 0.0, None, None, True, "실행 메트릭 없음"
        raw = _per_tc_raw_performance_score(
            fallback_execution_time,
            fallback_memory_used_mb,
            time_limit_sec,
            memory_limit_mb,
        )
        score = round(raw * scale, 2)
        return score, fallback_execution_time, fallback_memory_used_mb, False, None

    if not test_case_results or total_count <= 0:
        return 0.0, None, None, True, "테스트 케이스 없음"

    raw_sum = 0.0
    passed_times: list[float] = []
    passed_mems: list[float] = []
    measured_passed = 0

    for tc in test_case_results:
        if not isinstance(tc, dict) or not tc.get("passed"):
            continue
        t = _parse_judge_time_seconds(tc.get("time"))
        m = _parse_judge_memory_mb(tc.get("memory"))
        if t is None or m is None:
            continue
        raw_sum += _per_tc_raw_performance_score(
            t, m, time_limit_sec, memory_limit_mb
        )
        measured_passed += 1
        passed_times.append(t)
        passed_mems.append(m)

    if measured_passed == 0:
        return 0.0, None, None, True, "passed TC에 time·memory 없음"

    score = round((raw_sum / total_count) * scale, 2)
    avg_t = sum(passed_times) / len(passed_times)
    avg_m = sum(passed_mems) / len(passed_mems)
    skip_reason = None
    if passed_count < total_count:
        skip_reason = f"부분 TC만 Performance 반영 ({passed_count}/{total_count})"
    return score, avg_t, avg_m, False, skip_reason


async def _eval_code_execution_impl(state: MainGraphState) -> Dict[str, Any]:
    """
    N5: 코드 실행 평가 (Judge0 연동)

    평가 순서:
    1. Correctness 평가 (테스트 케이스 통과율)
       - 실패 시: Performance 평가 건너뛰고 바로 종료
       - 통과 시: Performance 평가 진행
    2. Performance 평가 (실행 시간, 메모리 사용량)
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[N5. Eval Code Execution] 진입 - session_id: {session_id}")

    raw_code = state.get("code_content")
    submission_id = state.get("submission_id")

    from app.infrastructure.judge0.utils import (
        clean_code,
        is_blank_submission_code,
        resolve_judge0_language,
    )

    code_content = clean_code(raw_code) if raw_code is not None else ""

    if is_blank_submission_code(code_content):
        logger.warning(
            "[N5. Eval Code Execution] 코드 없음 또는 공백만 — session_id=%s, raw_len=%s",
            session_id,
            len(raw_code) if raw_code is not None else 0,
        )
        return {
            "code_correctness_score": None,
            "code_performance_score": None,
            "updated_at": datetime.utcnow().isoformat(),
        }

    logger.info(
        f"[N5. Eval Code Execution] 코드 평가 시작 - session_id: {session_id}, 코드 길이: {len(code_content)}"
    )

    original_code_preview = code_content[:300].replace("\n", "\\n")
    logger.info(f"[N5] 원본 코드 미리보기 (처음 300자): {original_code_preview}")
    logger.info(
        f"[N5. Eval Code Execution] 코드 정리 완료 - 정리 후 길이: {len(code_content)}"
    )

    # 코드 내용 디버깅 (처음 300자)
    if code_content:
        code_preview = code_content[:300].replace("\n", "\\n")
        logger.info(f"[N5] 정리된 코드 미리보기 (처음 300자): {code_preview}")
        logger.info(
            f"[N5] 코드 인코딩 확인: UTF-8, 길이: {len(code_content.encode('utf-8'))} bytes"
        )
        # 실제 줄바꿈이 있는지 확인
        has_actual_newline = "\n" in code_content
        has_escaped_newline = "\\n" in code_content and "\n" not in code_content
        logger.info(
            f"[N5] 줄바꿈 확인 - 실제 줄바꿈: {has_actual_newline}, 이스케이프된 줄바꿈: {has_escaped_newline}"
        )
        # 코드 라인 수 확인
        line_count = len(code_content.split("\n"))
        logger.info(f"[N5] 코드 라인 수: {line_count}줄")

    # 문제 정보 가져오기 (DB checker_json 반영본 우선; 스마트 게이트는 test_suite_code 기준)
    problem_context = dict(state.get("problem_context") or {})
    spec_id = state.get("spec_id")

    need_reload = not problem_context
    if not need_reload and spec_id is not None:
        if spec_id in settings.SMART_GATE_SPEC_IDS:
            need_reload = not (problem_context.get("test_suite_code") or "").strip()
        else:
            need_reload = not (problem_context.get("test_cases") or [])

    if need_reload:
        if spec_id:
            logger.warning(
                f"[N5] problem_context 보강 필요 — DB 우선 재로드 spec_id={spec_id}"
            )
            try:
                from app.domain.langgraph.utils.problem_info import get_problem_info
                from app.infrastructure.persistence.session import get_db_context

                async with get_db_context() as db:
                    problem_context = await get_problem_info(spec_id, db)
            except Exception as e:
                logger.warning(
                    f"[N5] problem_context DB 로드 실패, 폴백 — spec_id={spec_id} error={e}"
                )
                from app.domain.langgraph.utils.problem_info import get_problem_info

                problem_context = await get_problem_info(spec_id, None)
            logger.info(
                f"[N5] problem_context 로드 완료 - test_cases: {len(problem_context.get('test_cases', []))}개"
            )
        else:
            logger.error("[N5] spec_id 없음 - problem_context를 로드할 수 없음")
            problem_context = {}

    constraints = problem_context.get("constraints", {})
    timeout = constraints.get("time_limit_sec") or 1.0
    memory_limit = constraints.get("memory_limit_mb") or 128

    # 스마트 게이트: v2_code + test_suite_code 합성 후 Judge0 실행 (대상 spec_id는 settings.SMART_GATE_SPEC_IDS로 관리)
    test_suite_code = problem_context.get("test_suite_code") if problem_context else None
    use_smart_gate_suite = bool(test_suite_code and spec_id in settings.SMART_GATE_SPEC_IDS)
    code_to_run = code_content
    correctness_reasoning = None

    if use_smart_gate_suite:
        v2_code = (state.get("v2_code") or code_content or "").strip()
        code_to_run = v2_code + "\n" + (test_suite_code.strip() if test_suite_code else "")
        test_cases = []
        test_cases_total = 1
        logger.info(
            f"[N5] 스마트 게이트 2026 모드 - v2_code + test_suite_code 합성, ALL_TESTS_PASSED 정답 판정"
        )
    else:
        # Judge0: checker_json에서 로드한 모든 TC를 한 번에 실행
        # (부분 통과 시 통과율 × settings.CODE_CORRECTNESS_MAX_POINTS 스케일)
        test_cases_raw = problem_context.get("test_cases", [])
        if test_cases_raw:
            test_cases = []
            for idx, raw in enumerate(test_cases_raw):
                if not isinstance(raw, dict):
                    continue
                test_cases.append(
                    {
                        "input": raw.get("input", "") or "",
                        "expected": raw.get("expected", "") or "",
                    }
                )
            test_cases_total = len(test_cases)
            if test_cases_total >= 2:
                logger.info(
                    f"[N5] 테스트 케이스 {test_cases_total}건 — "
                    f"Judge0 Batched Submissions (TC≥2, Worker에서 batch API)"
                )
            elif test_cases_total == 1:
                logger.info(
                    f"[N5] 테스트 케이스 1건 — Judge0 단일 submission API"
                )
            else:
                logger.info(f"[N5] 테스트 케이스 0건")
            if test_cases:
                tc0 = test_cases_raw[0] if isinstance(test_cases_raw[0], dict) else {}
                logger.info(
                    f"[N5] 첫 TC 설명: {tc0.get('description', '—')}, "
                    f"입력 길이: {len(test_cases[0].get('input', ''))}"
                )
        else:
            test_cases = []
            test_cases_total = 0
            logger.error(
                f"[N5] 테스트 케이스 없음 - session_id: {session_id}, spec_id: {spec_id}"
            )
            logger.error(f"[N5] problem_context 키 확인: {list(problem_context.keys())}")
            logger.error(
                f"[N5] test_cases_raw 타입: {type(test_cases_raw)}, 값: {test_cases_raw}"
            )

    # 제출 언어 → Judge0 CE language_id (submit_code request.language → state["lang"])
    raw_lang = state.get("lang") or state.get("language")
    language = resolve_judge0_language(
        str(raw_lang) if raw_lang is not None else None
    )
    logger.info(
        "[N5] Judge0 language=%s (state.lang=%r) → language_id via client",
        language,
        raw_lang,
    )

    # ===== 1단계: Correctness 평가 =====
    logger.info(f"[N5. Eval Code Execution] ===== 1단계: Correctness 평가 시작 =====")
    logger.info(f"[N5. Eval Code Execution] test_cases: {len(test_cases)}개")
    logger.info(
        f"[N5. Eval Code Execution] timeout: {timeout}초, memory_limit: {memory_limit}MB"
    )

    correctness_score = None
    test_cases_passed = None
    correctness_result = None
    # Correctness 결과에서도 execution_time과 memory_used_mb 추출 (Performance 실패 시 대비)
    correctness_execution_time = None
    correctness_memory_used_mb = None

    try:
        import uuid

        from app.domain.queue import JudgeTask, create_queue_adapter

        queue = create_queue_adapter()

        # Correctness 작업 생성 (스마트 게이트 모드면 합성 코드 사용)
        correctness_task_id = f"correct_{session_id}_{uuid.uuid4().hex[:8]}"
        correctness_task = JudgeTask(
            task_id=correctness_task_id,
            code=code_to_run,
            language=language,
            test_cases=test_cases,
            timeout=int(timeout) if timeout else 5,
            memory_limit=int(memory_limit) if memory_limit else 128,
            meta={
                "session_id": session_id,
                "submission_id": submission_id,
                "evaluation_type": "correctness",
            },
        )

        # 큐에 작업 추가
        await queue.enqueue(correctness_task)
        logger.info(
            f"[N5] Correctness 작업 추가 - task_id: {correctness_task_id}, test_cases: {len(test_cases)}"
        )

        # 결과 대기 (폴링)
        # 상태 키 업데이트 지연/누락이 있어도 결과 키가 생성되면 완료로 간주한다.
        max_wait = 30  # 최대 30초 대기
        start_time = time.time()
        poll_interval = 0.5

        while time.time() - start_time < max_wait:
            status = await queue.get_status(correctness_task_id)
            elapsed = time.time() - start_time
            logger.debug(
                f"[N5] 상태 조회 - task_id: {correctness_task_id}, status: {status}, 경과: {elapsed:.2f}초"
            )

            # 상태 기반 완료 체크가 정상 경로
            if status == "completed":
                correctness_result = await queue.get_result(correctness_task_id)
                if correctness_result is None:
                    # 간헐적으로 status만 먼저 올라오는 케이스 방어
                    await asyncio.sleep(0.2)
                    correctness_result = await queue.get_result(correctness_task_id)

                if correctness_result:
                    correctness_score, test_cases_passed, tc_tot, correctness_reasoning = (
                        _scores_from_correctness_result(
                            correctness_result, test_cases, use_smart_gate_suite
                        )
                    )
                    if tc_tot > 0:
                        test_cases_total = tc_tot
                    if correctness_result.execution_time is not None:
                        correctness_execution_time = correctness_result.execution_time
                    if correctness_result.memory_used is not None:
                        correctness_memory_used_mb = (
                            correctness_result.memory_used / (1024 * 1024)
                        )
                    logger.info(
                        f"[N5. Eval Code Execution] ===== Correctness 평가 완료 ===== task_id={correctness_task_id} "
                        f"result_status={correctness_result.status} score={correctness_score} "
                        f"passed={test_cases_passed}/{test_cases_total}"
                    )
                    if correctness_execution_time is not None:
                        logger.info(
                            f"[N5. Eval Code Execution] 실행 시간: {correctness_execution_time:.3f}초 (기준: {timeout}초)"
                        )
                    if correctness_memory_used_mb is not None:
                        logger.info(
                            f"[N5. Eval Code Execution] 메모리 사용: {correctness_memory_used_mb:.2f}MB (기준: {memory_limit}MB)"
                        )
                    if correctness_result.output:
                        logger.info(
                            f"[N5. Eval Code Execution] 출력 (처음 200자): {correctness_result.output[:200]}..."
                        )
                    if correctness_result.error:
                        logger.warning(
                            f"[N5. Eval Code Execution] 에러: {correctness_result.error}"
                        )
                    break

            elif status == "failed":
                # 구버전 큐 등: 결과만 있으면 동일 로직으로 점수 산출
                result = await queue.get_result(correctness_task_id)
                if result:
                    correctness_score, test_cases_passed, tc_tot, correctness_reasoning = (
                        _scores_from_correctness_result(
                            result, test_cases, use_smart_gate_suite
                        )
                    )
                    if tc_tot > 0:
                        test_cases_total = tc_tot
                    if result.execution_time is not None:
                        correctness_execution_time = result.execution_time
                    if result.memory_used is not None:
                        correctness_memory_used_mb = result.memory_used / (1024 * 1024)
                    logger.warning(
                        f"[N5] 상태 failed이나 결과 존재 — score={correctness_score} "
                        f"passed={test_cases_passed}/{test_cases_total} "
                        f"result_status={result.status}"
                    )
                else:
                    correctness_score = 0.0
                    test_cases_passed = 0
                    logger.warning(
                        f"[N5] Correctness 작업 실패 - task_id: {correctness_task_id}, 결과 없음"
                    )
                break

            # 상태 키가 지연되거나 누락되어 "pending/processing/unknown"으로 남아도
            # 결과 키가 이미 존재하면 해당 결과를 우선 사용한다.
            if status in {"pending", "processing", "unknown"}:
                maybe_result = await queue.get_result(correctness_task_id)
                if maybe_result is not None:
                    correctness_result = maybe_result
                    correctness_score, test_cases_passed, tc_tot, correctness_reasoning = (
                        _scores_from_correctness_result(
                            correctness_result, test_cases, use_smart_gate_suite
                        )
                    )
                    if tc_tot > 0:
                        test_cases_total = tc_tot
                    if correctness_result.execution_time is not None:
                        correctness_execution_time = correctness_result.execution_time
                    if correctness_result.memory_used is not None:
                        correctness_memory_used_mb = (
                            correctness_result.memory_used / (1024 * 1024)
                        )
                    if correctness_result.status != "success" and (
                        test_cases_passed == 0 and len(test_cases) > 0
                    ):
                        logger.warning(
                            f"[N5] 결과 키 확인: result_status={correctness_result.status}, "
                            f"error: {correctness_result.error}"
                        )
                    logger.info(
                        f"[N5] 결과 키 기반 완료 감지 - task_id: {correctness_task_id}, "
                        f"status_key={status}, result_status={correctness_result.status}, "
                        f"passed={test_cases_passed}/{test_cases_total}"
                    )
                    break

            # 아직 처리 중이면 대기
            await asyncio.sleep(poll_interval)

        # 타임아웃 처리
        if correctness_score is None:
            correctness_score = 0.0
            test_cases_passed = 0
            final_status = await queue.get_status(correctness_task_id)
            logger.warning(
                f"[N5] Correctness 평가 타임아웃 - task_id: {correctness_task_id}, "
                f"최종 상태: {final_status}, 대기 시간: {max_wait}초"
            )

    except Exception as e:
        logger.warning(
            f"[N5] Correctness 평가 오류 - session_id: {session_id}, error: {str(e)}"
        )
        correctness_score = 0.0
        test_cases_passed = 0

    # ===== Performance: TC별 passed일 때만 time·memory raw, Correctness와 동일 분모(전체 TC) =====
    passed_count = int(test_cases_passed or 0)
    total_count = int(test_cases_total or 0)
    time_limit_sec = float(timeout) if timeout else 2.0
    memory_limit_mb = float(memory_limit) if memory_limit else 128.0

    tc_results = (
        getattr(correctness_result, "test_case_results", None)
        if correctness_result is not None
        else None
    )

    logger.info(
        f"[N5. Eval Code Execution] ===== Performance (TC별 passed만, "
        f"만점 {settings.CODE_PERFORMANCE_MAX_POINTS}) ====="
    )

    performance_score, perf_time, perf_memory, skip_perf, perf_skip_reason = (
        _performance_score_from_test_cases(
            test_case_results=tc_results,
            time_limit_sec=time_limit_sec,
            memory_limit_mb=memory_limit_mb,
            use_smart_gate_suite=use_smart_gate_suite,
            passed_count=passed_count,
            total_count=total_count,
            fallback_execution_time=correctness_execution_time,
            fallback_memory_used_mb=correctness_memory_used_mb,
        )
    )

    if tc_results:
        for tc in tc_results:
            if not isinstance(tc, dict):
                continue
            idx = tc.get("test_case_index", "?")
            if tc.get("passed"):
                t = _parse_judge_time_seconds(tc.get("time"))
                m = _parse_judge_memory_mb(tc.get("memory"))
                if t is not None and m is not None:
                    raw = _per_tc_raw_performance_score(
                        t, m, time_limit_sec, memory_limit_mb
                    )
                    logger.info(
                        f"[N5] TC[{idx}] passed — raw Performance {raw:.1f}/100 "
                        f"(time={t:.3f}s, mem={m:.2f}MB)"
                    )
            else:
                logger.info(f"[N5] TC[{idx}] failed — Performance raw 0")

    logger.info(
        f"[N5] Performance 합산: {performance_score:.2f} / "
        f"{settings.CODE_PERFORMANCE_MAX_POINTS} "
        f"(passed {passed_count}/{total_count})"
    )

    final_execution_time = perf_time if perf_time is not None else correctness_execution_time
    final_memory_used_mb = (
        perf_memory if perf_memory is not None else correctness_memory_used_mb
    )

    result = {
        "code_correctness_score": (
            round(correctness_score, 2) if correctness_score is not None else 0.0
        ),
        "code_performance_score": performance_score,
        "test_cases_passed": test_cases_passed or 0,
        "test_cases_total": test_cases_total,
        "execution_time": final_execution_time,
        "memory_used_mb": (
            round(final_memory_used_mb, 2) if final_memory_used_mb is not None else None
        ),
        "time_limit_sec": time_limit_sec,
        "memory_limit_mb": memory_limit_mb,
        "skip_performance": skip_perf,
        "skip_reason": perf_skip_reason,
        "correctness_reasoning": correctness_reasoning,
        "test_case_results": (
            [tc for tc in tc_results if isinstance(tc, dict)]
            if tc_results
            else []
        ),
        "updated_at": datetime.utcnow().isoformat(),
    }

    # Performance 점수 상세 로깅
    logger.info(
        f"[N5. Eval Code Execution] 완료 - session_id: {session_id}, "
        f"correctness: {result['code_correctness_score']}, performance: {result['code_performance_score']}"
    )
    if performance_score > 0 and final_execution_time is not None:
        logger.info(
            f"[N5. Performance 점수 상세] session_id: {session_id}, "
            f"최종 Performance 점수: {result['code_performance_score']:.2f}점, "
            f"대표 실행 시간: {final_execution_time:.3f}초, "
            f"대표 메모리: {final_memory_used_mb:.2f}MB"
        )
    else:
        logger.warning(
            f"[N5. Performance 점수] session_id: {session_id}, "
            f"Performance 평가 실패 또는 점수 없음: {result['code_performance_score']:.2f}점"
        )

    return result


async def eval_code_execution(state: MainGraphState) -> Dict[str, Any]:
    """
    N5: 코드 실행 평가 (Judge0 연동)

    Correctness 후 TC별 passed에 대해 Performance 합산

    LangSmith 추적:
    - State의 enable_langsmith_tracing 값에 따라 활성화/비활성화
    - None이면 환경 변수 LANGCHAIN_TRACING_V2 사용
    """
    # LangSmith 추적과 함께 래핑
    wrapped_func = wrap_node_with_tracing(
        node_name=TRACE_NAME_CODE_EXECUTION,
        impl_func=_eval_code_execution_impl,
        state=state,
    )
    return await wrapped_func(state)
