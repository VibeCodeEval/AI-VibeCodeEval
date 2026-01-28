"""
6d: 코드 정확성 평가 (Judge0 연동)

[구조]
- 상수: 프롬프트 템플릿
- Chain 구성 함수: 평가 Chain 생성
- 내부 구현: 실제 평가 로직
- 외부 래퍼: LangSmith 추적 제어
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict

from langchain_core.runnables import RunnableLambda

from app.domain.langgraph.nodes.holistic_evaluator.langsmith_utils import (
    TRACE_NAME_CODE_CORRECTNESS, should_enable_langsmith,
    wrap_node_with_tracing)
from app.domain.langgraph.nodes.holistic_evaluator.utils import get_llm
from app.domain.langgraph.states import CodeQualityEvaluation, MainGraphState
from app.domain.langgraph.utils.token_tracking import (accumulate_tokens,
                                                       extract_token_usage)

logger = logging.getLogger(__name__)

# ===== 상수 =====

CORRECTNESS_SYSTEM_PROMPT = """당신은 코드 정확성 평가자입니다.
주어진 코드의 정확성을 평가하세요:

1. 로직 정확성
2. 에지 케이스 처리
3. 입출력 형식 준수
4. 정확성 점수 (0-100)

correctness는 로직 정확성을,
efficiency는 이 경우 에지 케이스 처리를,
readability는 코드 명확성을,
best_practices는 정확성 관련 모범 사례를 평가하세요."""

# 점수 계산 가중치
CORRECTNESS_WEIGHTS = {
    "correctness": 0.7,
    "efficiency": 0.2,
    "best_practices": 0.1,
}


async def _eval_code_correctness_impl(state: MainGraphState) -> Dict[str, Any]:
    """
    6d: 코드 정확성 평가 (Judge0 연동)

    평가 항목:
    - 테스트 케이스 통과율
    - 에지 케이스 처리
    - 정확성 점수
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[6d. Eval Code Correctness] 진입 - session_id: {session_id}")

    code_content = state.get("code_content")
    submission_id = state.get("submission_id")

    if not code_content:
        logger.warning(
            f"[6d. Eval Code Correctness] 코드 없음 - session_id: {session_id}"
        )
        return {
            "code_correctness_score": None,
            "updated_at": datetime.utcnow().isoformat(),
        }

    # Judge0 큐 시스템 사용
    try:
        import uuid

        from app.domain.queue import JudgeTask, create_queue_adapter

        queue = create_queue_adapter()

        # 문제 정보에서 테스트 케이스 가져오기
        problem_context = state.get("problem_context", {})
        constraints = problem_context.get("constraints", {})
        timeout = constraints.get("time_limit_sec") or 5
        memory_limit = constraints.get("memory_limit_mb") or 128

        # 테스트 케이스 준비 (problem_context에서 가져오기)
        test_cases_raw = problem_context.get("test_cases", [])
        test_cases = [
            {"input": tc.get("input", ""), "expected": tc.get("expected", "")}
            for tc in test_cases_raw
        ]

        # 언어 정보 가져오기 (기본값: python)
        language = "python"  # TODO: state에서 언어 정보 가져오기

        # 작업 생성
        task_id = f"correct_{session_id}_{uuid.uuid4().hex[:8]}"
        task = JudgeTask(
            task_id=task_id,
            code=code_content,
            language=language,
            test_cases=test_cases,
            timeout=timeout,
            memory_limit=memory_limit,
            meta={
                "session_id": session_id,
                "submission_id": submission_id,
                "evaluation_type": "correctness",
            },
        )

        # 큐에 작업 추가
        await queue.enqueue(task)
        logger.info(
            f"[6d] Judge0 작업 추가 - task_id: {task_id}, test_cases: {len(test_cases)}"
        )

        # 결과 대기 (폴링)
        max_wait = 60  # 최대 60초 대기 (테스트 케이스가 많을 수 있음)
        start_time = time.time()
        poll_interval = 0.5

        while time.time() - start_time < max_wait:
            status = await queue.get_status(task_id)

            if status == "completed":
                # 결과 조회
                result = await queue.get_result(task_id)

                if result:
                    if result.status == "success" and test_cases:
                        # 테스트 케이스 결과 분석
                        # result.output에서 테스트 케이스별 결과 파싱
                        # (JudgeWorker에서 여러 테스트 케이스 실행 시 결과를 집계)

                        # 정확성 점수 계산 (통과율 기반)
                        # TODO: result에서 테스트 케이스별 통과 여부 추출
                        # 현재는 간단히 status로 판단
                        correctness_score = 100.0 if result.status == "success" else 0.0

                        logger.info(
                            f"[6d] Judge0 실행 완료 - task_id: {task_id}, "
                            f"status: {result.status}, score: {correctness_score}"
                        )

                        return {
                            "code_correctness_score": round(correctness_score, 2),
                            "test_cases_passed": None,  # TODO: 실제 통과 개수
                            "test_cases_total": len(test_cases) if test_cases else 0,
                            "judge_task_id": task_id,
                            "updated_at": datetime.utcnow().isoformat(),
                        }
                    elif result.status == "success" and not test_cases:
                        # 테스트 케이스가 없으면 실행만 확인
                        correctness_score = 50.0  # 부분 점수

                        return {
                            "code_correctness_score": round(correctness_score, 2),
                            "test_cases_passed": None,
                            "test_cases_total": 0,
                            "judge_task_id": task_id,
                            "note": "테스트 케이스 없음, 실행만 확인",
                            "updated_at": datetime.utcnow().isoformat(),
                        }
                    else:
                        # 실행 실패
                        error_msg = result.error if result else "Unknown error"
                        logger.warning(
                            f"[6d] Judge0 실행 실패 - task_id: {task_id}, error: {error_msg}"
                        )
                        # LLM 기반 평가로 폴백
                        break

            elif status == "failed":
                logger.warning(f"[6d] Judge0 작업 실패 - task_id: {task_id}")
                # LLM 기반 평가로 폴백
                break

            # 아직 처리 중이면 대기
            await asyncio.sleep(poll_interval)

        # 타임아웃 또는 실패 시 LLM 기반 평가로 폴백
        logger.warning(
            f"[6d] Judge0 타임아웃 또는 실패 - task_id: {task_id}, LLM 기반 평가로 폴백"
        )

    except Exception as e:
        logger.warning(
            f"[6d] Judge0 큐 시스템 오류 - session_id: {session_id}, error: {str(e)}, LLM 기반 평가로 폴백"
        )

    # LLM 기반 평가 (폴백)

    # Correctness 평가 Chain 구성
    def prepare_correctness_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Correctness 평가 입력 준비"""
        code_content = inputs.get("code_content", "")
        user_prompt = f"코드:\n```\n{code_content}\n```"

        return {
            "system_prompt": CORRECTNESS_SYSTEM_PROMPT,
            "user_prompt": user_prompt,
        }

    def format_correctness_messages(inputs: Dict[str, Any]) -> list:
        """메시지를 LangChain BaseMessage 객체로 변환"""
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = []
        if inputs.get("system_prompt"):
            messages.append(SystemMessage(content=inputs["system_prompt"]))
        if inputs.get("user_prompt"):
            messages.append(HumanMessage(content=inputs["user_prompt"]))
        return messages

    def process_correctness_output_with_response(
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """출력 처리 (LLM 응답 객체 포함)"""
        llm_response = inputs.get("llm_response")
        result = llm_response  # structured_llm의 결과는 이미 CodeQualityEvaluation 객체

        # 정확성 점수 계산 (가중치 적용)
        correctness_score = (
            result.correctness * CORRECTNESS_WEIGHTS["correctness"]
            + result.efficiency * CORRECTNESS_WEIGHTS["efficiency"]
            + result.best_practices * CORRECTNESS_WEIGHTS["best_practices"]
        )

        processed = {
            "code_correctness_score": round(correctness_score, 2),
            "updated_at": datetime.utcnow().isoformat(),
            "_llm_response": llm_response,  # 토큰 추출용
        }
        return processed

    # Chain 구성 (토큰 추출을 위해 원본 LLM 응답도 전달)
    llm = get_llm()
    structured_llm = llm.with_structured_output(CodeQualityEvaluation)

    correctness_chain = (
        RunnableLambda(prepare_correctness_input)
        | RunnableLambda(format_correctness_messages)
        | structured_llm
        | RunnableLambda(lambda x: {"llm_response": x})
        | RunnableLambda(process_correctness_output_with_response)
    )

    try:
        # Chain 실행 전에 원본 LLM 호출하여 메타데이터 추출
        # 주의: with_structured_output은 원본 응답 메타데이터를 보존하지 않으므로
        # 원본 LLM을 먼저 호출하여 메타데이터 추출
        chain_input = {"code_content": code_content}

        # 메시지 포맷팅 (토큰 추출용 원본 LLM 호출에 사용)
        prepared_input = prepare_correctness_input(chain_input)
        formatted_messages = format_correctness_messages(prepared_input)

        # 원본 LLM 호출 (토큰 사용량 추출용)
        raw_response = await llm.ainvoke(formatted_messages)

        # 토큰 사용량 추출 및 State에 누적 (원본 응답에서)
        tokens = extract_token_usage(raw_response)
        if tokens:
            accumulate_tokens(state, tokens, token_type="eval")
            logger.debug(
                f"[6d. Eval Code Correctness] 토큰 사용량 - prompt: {tokens.get('prompt_tokens')}, completion: {tokens.get('completion_tokens')}, total: {tokens.get('total_tokens')}"
            )
        else:
            logger.warning(
                f"[6d. Eval Code Correctness] 토큰 사용량 추출 실패 - raw_response 타입: {type(raw_response)}"
            )

        # Chain 실행 (구조화된 출력 파싱)
        chain_result = await correctness_chain.ainvoke(chain_input)

        # _llm_response는 더 이상 필요 없음 (이미 원본 응답에서 토큰 추출 완료)
        chain_result.pop("_llm_response", None)

        result = chain_result

        # State에 누적된 토큰 정보를 result에 포함 (LangGraph 병합을 위해)
        if "eval_tokens" in state:
            result["eval_tokens"] = state["eval_tokens"]

        logger.info(
            f"[6d. Eval Code Correctness] 완료 - session_id: {session_id}, score: {result['code_correctness_score']}"
        )

        # LangSmith 추적 정보 로깅
        if should_enable_langsmith(state):
            logger.debug(
                f"[LangSmith] 6d 노드 추적 활성화 - session_id: {session_id}, 코드 길이: {len(code_content)}"
            )

        return result

    except Exception as e:
        logger.error(
            f"[6d. Eval Code Correctness] 오류 - session_id: {session_id}, error: {str(e)}",
            exc_info=True,
        )
        return {
            "code_correctness_score": None,
            "error_message": f"정확성 평가 실패: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }


# ===== 외부 래퍼 함수 =====


async def eval_code_correctness(state: MainGraphState) -> Dict[str, Any]:
    """
    6d: 코드 정확성 평가 (Judge0 연동)

    LangSmith 추적:
    - State의 enable_langsmith_tracing 값에 따라 활성화/비활성화
    - None이면 환경 변수 LANGCHAIN_TRACING_V2 사용
    """
    # LangSmith 추적과 함께 래핑
    wrapped_func = wrap_node_with_tracing(
        node_name=TRACE_NAME_CODE_CORRECTNESS,
        impl_func=_eval_code_correctness_impl,
        state=state,
    )
    return await wrapped_func(state)
