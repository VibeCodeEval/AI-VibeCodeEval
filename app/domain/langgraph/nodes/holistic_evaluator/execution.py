"""
6c: 코드 실행 평가 (Judge0 연동)
Correctness 먼저 평가 → 통과 시 Performance 평가

평가 순서:
1. Correctness 평가 (테스트 케이스 통과율)
   - 실패 시: Performance 평가 건너뛰고 바로 종료
   - 통과 시: Performance 평가 진행
2. Performance 평가 (실행 시간, 메모리 사용량)
"""
import asyncio
import logging
import time
from typing import Dict, Any
from datetime import datetime

from app.domain.langgraph.states import MainGraphState
from app.domain.langgraph.utils.token_tracking import extract_token_usage, accumulate_tokens
from app.domain.langgraph.nodes.holistic_evaluator.langsmith_utils import (
    wrap_node_with_tracing,
    should_enable_langsmith,
)

logger = logging.getLogger(__name__)

TRACE_NAME_CODE_EXECUTION = "eval_code_execution"


async def _eval_code_execution_impl(state: MainGraphState) -> Dict[str, Any]:
    """
    6c: 코드 실행 평가 (Judge0 연동)
    
    평가 순서:
    1. Correctness 평가 (테스트 케이스 통과율)
       - 실패 시: Performance 평가 건너뛰고 바로 종료
       - 통과 시: Performance 평가 진행
    2. Performance 평가 (실행 시간, 메모리 사용량)
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[6c. Eval Code Execution] 진입 - session_id: {session_id}")
    
    code_content = state.get("code_content")
    submission_id = state.get("submission_id")
    
    if not code_content:
        logger.warning(f"[6c. Eval Code Execution] 코드 없음 - session_id: {session_id}")
        return {
            "code_correctness_score": None,
            "code_performance_score": None,
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    logger.info(f"[6c. Eval Code Execution] 코드 평가 시작 - session_id: {session_id}, 코드 길이: {len(code_content)}")
    
    # 코드 내용 디버깅 (처음 200자)
    if code_content:
        code_preview = code_content[:200].replace('\n', '\\n')
        logger.debug(f"[6c] 코드 미리보기 (처음 200자): {code_preview}")
        logger.debug(f"[6c] 코드 인코딩 확인: UTF-8, 길이: {len(code_content.encode('utf-8'))} bytes")
    
    # 문제 정보 가져오기
    problem_context = state.get("problem_context", {})
    constraints = problem_context.get("constraints", {})
    timeout = constraints.get("time_limit_sec") or 1.0
    memory_limit = constraints.get("memory_limit_mb") or 128
    
    # 테스트 케이스 준비 (API 제한으로 인해 첫 번째 TC만 사용)
    test_cases_raw = problem_context.get("test_cases", [])
    if test_cases_raw:
        # 첫 번째 테스트 케이스만 사용
        first_tc = test_cases_raw[0]
        test_cases = [{
            "input": first_tc.get("input", ""),
            "expected": first_tc.get("expected", "")
        }]
        test_cases_total = 1  # API 제한으로 1개만 사용
        logger.info(f"[6c] 테스트 케이스 1개만 사용 (API 제한) - TC: {first_tc.get('description', '기본 케이스')}")
    else:
        test_cases = []
        test_cases_total = 0
        logger.warning(f"[6c] 테스트 케이스 없음 - session_id: {session_id}")
    
    # 언어 정보 가져오기 (기본값: python)
    language = "python"  # TODO: state에서 언어 정보 가져오기
    
    # ===== 1단계: Correctness 평가 =====
    logger.info(f"[6c. Eval Code Execution] ===== 1단계: Correctness 평가 시작 =====")
    logger.info(f"[6c. Eval Code Execution] test_cases: {len(test_cases)} (API 제한: 1개만 사용)")
    logger.info(f"[6c. Eval Code Execution] timeout: {timeout}초, memory_limit: {memory_limit}MB")
    
    correctness_score = None
    test_cases_passed = None
    correctness_result = None
    # Correctness 결과에서도 execution_time과 memory_used_mb 추출 (Performance 실패 시 대비)
    correctness_execution_time = None
    correctness_memory_used_mb = None
    
    try:
        from app.domain.queue import create_queue_adapter, JudgeTask
        import uuid
        
        queue = create_queue_adapter()
        
        # Correctness 작업 생성
        correctness_task_id = f"correct_{session_id}_{uuid.uuid4().hex[:8]}"
        correctness_task = JudgeTask(
            task_id=correctness_task_id,
            code=code_content,
            language=language,
            test_cases=test_cases,
            timeout=timeout,
            memory_limit=memory_limit,
            meta={
                "session_id": session_id,
                "submission_id": submission_id,
                "evaluation_type": "correctness"
            }
        )
        
        # 큐에 작업 추가
        await queue.enqueue(correctness_task)
        logger.info(f"[6c] Correctness 작업 추가 - task_id: {correctness_task_id}, test_cases: {len(test_cases)}")
        
        # 결과 대기 (폴링)
        max_wait = 30  # 최대 30초 대기 (TC 1개만 사용하므로 시간 단축)
        start_time = time.time()
        poll_interval = 0.5
        
        while time.time() - start_time < max_wait:
            status = await queue.get_status(correctness_task_id)
            elapsed = time.time() - start_time
            logger.debug(f"[6c] 상태 조회 - task_id: {correctness_task_id}, status: {status}, 경과: {elapsed:.2f}초")
            
            if status == "completed":
                correctness_result = await queue.get_result(correctness_task_id)
                
                if correctness_result:
                    if correctness_result.status == "success" and test_cases:
                        # 테스트 케이스 통과율 계산
                        # JudgeWorker에서 여러 테스트 케이스 실행 시 결과를 집계
                        # TODO: result에서 테스트 케이스별 통과 여부 추출
                        # 현재는 간단히 status로 판단
                        correctness_score = 100.0 if correctness_result.status == "success" else 0.0
                        test_cases_passed = len(test_cases) if correctness_result.status == "success" else 0
                        
                        # Correctness 결과에서 execution_time과 memory_used 추출
                        if correctness_result.execution_time is not None:
                            correctness_execution_time = correctness_result.execution_time
                        if correctness_result.memory_used is not None:
                            correctness_memory_used_mb = correctness_result.memory_used / (1024 * 1024)  # bytes -> MB
                        
                        logger.info(f"[6c. Eval Code Execution] ===== Correctness 평가 완료 =====")
                        logger.info(f"[6c. Eval Code Execution] task_id: {correctness_task_id}")
                        logger.info(f"[6c. Eval Code Execution] status: {correctness_result.status}")
                        logger.info(f"[6c. Eval Code Execution] Correctness Score: {correctness_score}")
                        logger.info(f"[6c. Eval Code Execution] test_cases_passed: {test_cases_passed}/{len(test_cases)}")
                        if correctness_execution_time is not None:
                            logger.info(f"[6c. Eval Code Execution] 실행 시간: {correctness_execution_time:.3f}초")
                        if correctness_memory_used_mb is not None:
                            logger.info(f"[6c. Eval Code Execution] 메모리 사용: {correctness_memory_used_mb:.2f}MB")
                        if correctness_result.output:
                            logger.info(f"[6c. Eval Code Execution] 출력 (처음 200자): {correctness_result.output[:200]}...")
                        if correctness_result.error:
                            logger.warning(f"[6c. Eval Code Execution] 에러: {correctness_result.error}")
                        break
                    elif correctness_result.status == "success" and not test_cases:
                        # 테스트 케이스가 없으면 실행만 확인
                        correctness_score = 50.0
                        test_cases_passed = 0
                        logger.info(f"[6c] Correctness 평가 완료 (TC 없음) - task_id: {correctness_task_id}")
                        break
                    else:
                        # 실행 실패
                        correctness_score = 0.0
                        test_cases_passed = 0
                        error_msg = correctness_result.error if correctness_result else "Unknown error"
                        logger.warning(f"[6c] Correctness 평가 실패 - task_id: {correctness_task_id}, error: {error_msg}")
                        break
            
            elif status == "failed":
                correctness_score = 0.0
                test_cases_passed = 0
                # 실패 원인 확인
                result = await queue.get_result(correctness_task_id)
                if result:
                    logger.warning(
                        f"[6c] Correctness 작업 실패 - task_id: {correctness_task_id}, "
                        f"status: {result.status}, error: {result.error}, "
                        f"execution_time: {result.execution_time}s"
                    )
                else:
                    logger.warning(
                        f"[6c] Correctness 작업 실패 - task_id: {correctness_task_id}, "
                        f"결과 없음 (Worker가 작업을 처리하지 못했을 수 있음)"
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
                f"[6c] Correctness 평가 타임아웃 - task_id: {correctness_task_id}, "
                f"최종 상태: {final_status}, 대기 시간: {max_wait}초"
            )
        
    except Exception as e:
        logger.warning(f"[6c] Correctness 평가 오류 - session_id: {session_id}, error: {str(e)}")
        correctness_score = 0.0
        test_cases_passed = 0
    
    # ===== Correctness 실패 시 Performance 평가 건너뛰기 =====
    if correctness_score is None or correctness_score == 0.0:
        logger.info(f"[6c] Correctness 실패 - Performance 평가 건너뛰기 (score: {correctness_score})")
        return {
            "code_correctness_score": 0.0,
            "code_performance_score": 0.0,  # Correctness 실패 시 Performance도 0점
            "test_cases_passed": test_cases_passed or 0,
            "test_cases_total": test_cases_total,
            "execution_time": None,
            "memory_used_mb": None,
            "skip_performance": True,
            "skip_reason": "Correctness 평가 실패",
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    # ===== 2단계: Performance 평가 (Correctness 통과 시에만) =====
    logger.info(f"[6c. Eval Code Execution] ===== 2단계: Performance 평가 시작 =====")
    logger.info(f"[6c. Eval Code Execution] Correctness 통과 여부: {correctness_score is not None and correctness_score > 0}")
    
    performance_score = None
    execution_time = None
    memory_used_mb = None
    
    try:
        queue = create_queue_adapter()
        
        # Performance 작업 생성 (TC 없이 실행 시간/메모리만 측정)
        performance_task_id = f"perf_{session_id}_{uuid.uuid4().hex[:8]}"
        performance_task = JudgeTask(
            task_id=performance_task_id,
            code=code_content,
            language=language,
            test_cases=[],  # 성능 평가는 테스트 케이스 없이 실행 시간/메모리만 측정
            timeout=timeout,
            memory_limit=memory_limit,
            meta={
                "session_id": session_id,
                "submission_id": submission_id,
                "evaluation_type": "performance"
            }
        )
        
        # 큐에 작업 추가
        await queue.enqueue(performance_task)
        logger.info(f"[6c] Performance 작업 추가 - task_id: {performance_task_id}")
        
        # 결과 대기 (폴링)
        max_wait = 30  # 최대 30초 대기
        start_time = time.time()
        poll_interval = 0.5
        
        while time.time() - start_time < max_wait:
            status = await queue.get_status(performance_task_id)
            
            if status == "completed":
                performance_result = await queue.get_result(performance_task_id)
                
                if performance_result and performance_result.status == "success":
                    # 성능 점수 계산 (실행 시간과 메모리 기반)
                    execution_time = performance_result.execution_time
                    memory_used_mb = performance_result.memory_used / (1024 * 1024)  # bytes -> MB
                    
                    # 점수 계산 (합격 기준 기반)
                    # 시간 점수: 코드 걸린 시간 < 합격 시간이면 50점, 아니면 0점
                    time_score = 50.0 if execution_time < timeout else 0.0
                    # 메모리 점수: 코드 메모리 소모량 < 메모리 소모량이면 50점, 아니면 0점
                    memory_score = 50.0 if memory_used_mb < memory_limit else 0.0
                    # 성능 점수: 시간 점수 + 메모리 점수 (최대 100점)
                    performance_score = time_score + memory_score
                    
                    logger.info(f"[6c. Eval Code Execution] ===== Performance 평가 완료 =====")
                    logger.info(f"[6c. Eval Code Execution] task_id: {performance_task_id}")
                    logger.info(f"[6c. Eval Code Execution] 실행 시간: {execution_time:.3f}초 (합격 기준: {timeout}초) → 시간 점수: {time_score}점")
                    logger.info(f"[6c. Eval Code Execution] 메모리 사용: {memory_used_mb:.2f}MB (합격 기준: {memory_limit}MB) → 메모리 점수: {memory_score}점")
                    logger.info(f"[6c. Eval Code Execution] Performance Score: {performance_score:.2f}점 (시간 {time_score}점 + 메모리 {memory_score}점)")
                    break
                else:
                    # 실행 실패
                    error_msg = performance_result.error if performance_result else "Unknown error"
                    logger.warning(f"[6c] Performance 평가 실패 - task_id: {performance_task_id}, error: {error_msg}")
                    performance_score = 0.0
                    break
            
            elif status == "failed":
                logger.warning(f"[6c] Performance 작업 실패 - task_id: {performance_task_id}")
                performance_score = 0.0
                break
            
            # 아직 처리 중이면 대기
            await asyncio.sleep(poll_interval)
        
        # 타임아웃 처리
        if performance_score is None:
            performance_score = 0.0
            logger.warning(f"[6c] Performance 평가 타임아웃 - task_id: {performance_task_id}")
        
    except Exception as e:
        logger.warning(f"[6c] Performance 평가 오류 - session_id: {session_id}, error: {str(e)}")
        performance_score = 0.0
    
    # ===== 결과 반환 =====
    # Performance 결과가 없으면 Correctness 결과에서 가져온 값 사용
    final_execution_time = execution_time if execution_time is not None else correctness_execution_time
    final_memory_used_mb = memory_used_mb if memory_used_mb is not None else correctness_memory_used_mb
    
    result = {
        "code_correctness_score": round(correctness_score, 2) if correctness_score is not None else 0.0,
        "code_performance_score": round(performance_score, 2) if performance_score is not None else 0.0,
        "test_cases_passed": test_cases_passed or 0,
        "test_cases_total": test_cases_total,
        "execution_time": final_execution_time,
        "memory_used_mb": round(final_memory_used_mb, 2) if final_memory_used_mb is not None else None,
        "updated_at": datetime.utcnow().isoformat(),
    }
    
    # Performance 점수 상세 로깅
    logger.info(
        f"[6c. Eval Code Execution] 완료 - session_id: {session_id}, "
        f"correctness: {result['code_correctness_score']}, performance: {result['code_performance_score']}"
    )
    if performance_score is not None and performance_score > 0:
        logger.info(
            f"[6c. Performance 점수 상세] session_id: {session_id}, "
            f"최종 Performance 점수: {result['code_performance_score']:.2f}점, "
            f"실행 시간: {execution_time:.3f}초, 메모리: {memory_used_mb:.2f}MB"
        )
    else:
        logger.warning(
            f"[6c. Performance 점수] session_id: {session_id}, "
            f"Performance 평가 실패 또는 점수 없음: {result['code_performance_score']:.2f}점"
        )
    
    return result


async def eval_code_execution(state: MainGraphState) -> Dict[str, Any]:
    """
    6c: 코드 실행 평가 (Judge0 연동)
    
    Correctness 먼저 평가 → 통과 시 Performance 평가
    
    LangSmith 추적:
    - State의 enable_langsmith_tracing 값에 따라 활성화/비활성화
    - None이면 환경 변수 LANGCHAIN_TRACING_V2 사용
    """
    # LangSmith 추적과 함께 래핑
    wrapped_func = wrap_node_with_tracing(
        node_name=TRACE_NAME_CODE_EXECUTION,
        impl_func=_eval_code_execution_impl,
        state=state
    )
    return await wrapped_func(state)

