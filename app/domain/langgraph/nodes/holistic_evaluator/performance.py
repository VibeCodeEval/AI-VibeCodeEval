"""
6c: 코드 성능 평가 (Judge0 연동)

[구조]
- 상수: 프롬프트 템플릿
- Chain 구성 함수: 평가 Chain 생성
- 내부 구현: 실제 평가 로직
- 외부 래퍼: LangSmith 추적 제어
"""
import asyncio
import logging
import time
from typing import Dict, Any
from datetime import datetime

from langchain_core.runnables import RunnableLambda

from app.domain.langgraph.states import MainGraphState, CodeQualityEvaluation
from app.domain.langgraph.nodes.holistic_evaluator.utils import get_llm
from app.domain.langgraph.nodes.holistic_evaluator.langsmith_utils import (
    wrap_node_with_tracing,
    should_enable_langsmith,
    TRACE_NAME_CODE_PERFORMANCE,
)
from app.domain.langgraph.utils.token_tracking import extract_token_usage, accumulate_tokens

logger = logging.getLogger(__name__)

# ===== 상수 =====

PERFORMANCE_SYSTEM_PROMPT = """당신은 코드 성능 평가자입니다.
주어진 코드의 성능을 평가하세요:

1. 시간 복잡도 분석
2. 공간 복잡도 분석
3. 최적화 가능성
4. 효율성 점수 (0-100)

correctness는 성능과 관련된 정확성을,
efficiency는 알고리즘 효율성을,
readability는 코드 가독성을,
best_practices는 성능 관련 모범 사례 준수를 평가하세요."""

# 점수 계산 가중치
PERFORMANCE_WEIGHTS = {
    "efficiency": 0.6,
    "correctness": 0.2,
    "best_practices": 0.2,
}


async def _eval_code_performance_impl(state: MainGraphState) -> Dict[str, Any]:
    """
    6c: 코드 성능 평가 (Judge0 연동)
    
    평가 항목:
    - 실행 시간
    - 메모리 사용량
    - 효율성 점수
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[6c. Eval Code Performance] 진입 - session_id: {session_id}")
    
    code_content = state.get("code_content")
    submission_id = state.get("submission_id")
    
    if not code_content:
        logger.warning(f"[6c. Eval Code Performance] 코드 없음 - session_id: {session_id}")
        return {
            "code_performance_score": None,
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    logger.info(f"[6c. Eval Code Performance] 코드 평가 시작 - session_id: {session_id}, 코드 길이: {len(code_content)}")
    
    # Judge0 큐 시스템 사용
    try:
        from app.domain.queue import create_queue_adapter, JudgeTask
        import uuid
        
        queue = create_queue_adapter()
        
        # 문제 정보에서 제한사항 가져오기
        problem_context = state.get("problem_context", {})
        constraints = problem_context.get("constraints", {})
        timeout = constraints.get("time_limit_sec") or 5
        memory_limit = constraints.get("memory_limit_mb") or 128
        
        # 언어 정보 가져오기 (기본값: python)
        language = "python"  # TODO: state에서 언어 정보 가져오기
        
        # 작업 생성
        task_id = f"perf_{session_id}_{uuid.uuid4().hex[:8]}"
        task = JudgeTask(
            task_id=task_id,
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
        await queue.enqueue(task)
        logger.info(f"[6c] Judge0 작업 추가 - task_id: {task_id}")
        
        # 결과 대기 (폴링)
        max_wait = 30  # 최대 30초 대기
        start_time = time.time()
        poll_interval = 0.5  # 0.5초마다 확인
        
        while time.time() - start_time < max_wait:
            status = await queue.get_status(task_id)
            
            if status == "completed":
                # 결과 조회
                result = await queue.get_result(task_id)
                
                if result and result.status == "success":
                    # 성능 점수 계산 (실행 시간과 메모리 기반)
                    execution_time = result.execution_time
                    memory_used_mb = result.memory_used / (1024 * 1024)  # bytes -> MB
                    
                    # 점수 계산 (합격 기준 기반)
                    # 시간 점수: 코드 걸린 시간 < 합격 시간이면 50점, 아니면 0점
                    time_score = 50.0 if execution_time < timeout else 0.0
                    # 메모리 점수: 코드 메모리 소모량 < 메모리 소모량이면 50점, 아니면 0점
                    memory_score = 50.0 if memory_used_mb < memory_limit else 0.0
                    # 성능 점수: 시간 점수 + 메모리 점수 (최대 100점)
                    performance_score = time_score + memory_score
                    
                    logger.info(
                        f"[6c] Judge0 실행 완료 - task_id: {task_id}, "
                        f"time: {execution_time}s, memory: {memory_used_mb:.2f}MB, score: {performance_score:.2f}"
                    )
                    
                    return {
                        "code_performance_score": round(performance_score, 2),
                        "execution_time": execution_time,
                        "memory_used_mb": round(memory_used_mb, 2),
                        "judge_task_id": task_id,
                        "updated_at": datetime.utcnow().isoformat(),
                    }
                else:
                    # 실행 실패
                    error_msg = result.error if result else "Unknown error"
                    logger.warning(f"[6c] Judge0 실행 실패 - task_id: {task_id}, error: {error_msg}")
                    # LLM 기반 평가로 폴백
                    break
            
            elif status == "failed":
                logger.warning(f"[6c] Judge0 작업 실패 - task_id: {task_id}")
                # LLM 기반 평가로 폴백
                break
            
            # 아직 처리 중이면 대기
            await asyncio.sleep(poll_interval)
        
        # 타임아웃 또는 실패 시 LLM 기반 평가로 폴백
        logger.warning(f"[6c] Judge0 타임아웃 또는 실패 - task_id: {task_id}, LLM 기반 평가로 폴백")
        
    except Exception as e:
        logger.warning(f"[6c] Judge0 큐 시스템 오류 - session_id: {session_id}, error: {str(e)}, LLM 기반 평가로 폴백")
    
    # LLM 기반 평가 (폴백)
    
    # Performance 평가 Chain 구성
    def prepare_performance_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Performance 평가 입력 준비"""
        code_content = inputs.get("code_content", "")
        user_prompt = f"코드:\n```\n{code_content}\n```"
        
        return {
            "system_prompt": PERFORMANCE_SYSTEM_PROMPT,
            "user_prompt": user_prompt,
        }
    
    def format_performance_messages(inputs: Dict[str, Any]) -> list:
        """메시지를 LangChain BaseMessage 객체로 변환"""
        from langchain_core.messages import HumanMessage, SystemMessage
        
        messages = []
        if inputs.get("system_prompt"):
            messages.append(SystemMessage(content=inputs["system_prompt"]))
        if inputs.get("user_prompt"):
            messages.append(HumanMessage(content=inputs["user_prompt"]))
        return messages
        """메시지 포맷팅"""
        return [
            {"role": "system", "content": inputs["system_prompt"]},
            {"role": "user", "content": inputs["user_prompt"]}
        ]
    
    def process_performance_output_with_response(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """출력 처리 (LLM 응답 객체 포함)"""
        llm_response = inputs.get("llm_response")
        result = llm_response  # structured_llm의 결과는 이미 CodeQualityEvaluation 객체
        
        # 성능 점수 계산 (가중치 적용)
        perf_score = (
            result.efficiency * PERFORMANCE_WEIGHTS["efficiency"] +
            result.correctness * PERFORMANCE_WEIGHTS["correctness"] +
            result.best_practices * PERFORMANCE_WEIGHTS["best_practices"]
        )
        
        processed = {
            "code_performance_score": round(perf_score, 2),
            "updated_at": datetime.utcnow().isoformat(),
            "_llm_response": llm_response  # 토큰 추출용
        }
        return processed
    
    # Chain 구성 (토큰 추출을 위해 원본 LLM 응답도 전달)
    llm = get_llm()
    structured_llm = llm.with_structured_output(CodeQualityEvaluation)
    
    performance_chain = (
        RunnableLambda(prepare_performance_input)
        | RunnableLambda(format_performance_messages)
        | structured_llm
        | RunnableLambda(lambda x: {"llm_response": x})
        | RunnableLambda(process_performance_output_with_response)
    )
    
    try:
        # Chain 실행 전에 원본 LLM 호출하여 메타데이터 추출
        # 주의: with_structured_output은 원본 응답 메타데이터를 보존하지 않으므로
        # 원본 LLM을 먼저 호출하여 메타데이터 추출
        chain_input = {"code_content": code_content}
        
        # 메시지 포맷팅 (토큰 추출용 원본 LLM 호출에 사용)
        prepared_input = prepare_performance_input(chain_input)
        formatted_messages = format_performance_messages(prepared_input)
        
        # 원본 LLM 호출 (토큰 사용량 추출용)
        raw_response = await llm.ainvoke(formatted_messages)
        
        # 토큰 사용량 추출 및 State에 누적 (원본 응답에서)
        tokens = extract_token_usage(raw_response)
        if tokens:
            accumulate_tokens(state, tokens, token_type="eval")
            logger.debug(f"[6c. Eval Code Performance] 토큰 사용량 - prompt: {tokens.get('prompt_tokens')}, completion: {tokens.get('completion_tokens')}, total: {tokens.get('total_tokens')}")
        else:
            logger.warning(f"[6c. Eval Code Performance] 토큰 사용량 추출 실패 - raw_response 타입: {type(raw_response)}")
        
        # Chain 실행 (구조화된 출력 파싱)
        chain_result = await performance_chain.ainvoke(chain_input)
        
        # _llm_response는 더 이상 필요 없음 (이미 원본 응답에서 토큰 추출 완료)
        chain_result.pop("_llm_response", None)
        
        result = chain_result
        
        # State에 누적된 토큰 정보를 result에 포함 (LangGraph 병합을 위해)
        if "eval_tokens" in state:
            result["eval_tokens"] = state["eval_tokens"]
        
        logger.info(f"[6c. Eval Code Performance] 완료 - session_id: {session_id}, score: {result['code_performance_score']}")
        
        # LangSmith 추적 정보 로깅
        if should_enable_langsmith(state):
            logger.debug(f"[LangSmith] 6c 노드 추적 활성화 - session_id: {session_id}, 코드 길이: {len(code_content)}")
        
        return result
        
    except Exception as e:
        logger.error(f"[6c. Eval Code Performance] 오류 - session_id: {session_id}, error: {str(e)}", exc_info=True)
        return {
            "code_performance_score": None,
            "error_message": f"성능 평가 실패: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }


# ===== 외부 래퍼 함수 =====

async def eval_code_performance(state: MainGraphState) -> Dict[str, Any]:
    """
    6c: 코드 성능 평가 (Judge0 연동)
    
    LangSmith 추적:
    - State의 enable_langsmith_tracing 값에 따라 활성화/비활성화
    - None이면 환경 변수 LANGCHAIN_TRACING_V2 사용
    """
    # LangSmith 추적과 함께 래핑
    wrapped_func = wrap_node_with_tracing(
        node_name=TRACE_NAME_CODE_PERFORMANCE,
        impl_func=_eval_code_performance_impl,
        state=state
    )
    return await wrapped_func(state)

