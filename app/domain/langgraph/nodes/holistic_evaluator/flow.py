"""
6a: 전체 플로우 평가 - 전략 Chaining 분석

[구조]
- 상수: 프롬프트 템플릿
- Chain 구성 함수: 평가 Chain 생성
- 내부 구현: 실제 평가 로직
- 외부 래퍼: LangSmith 추적 제어
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import json

from langchain_core.runnables import RunnableLambda

from app.domain.langgraph.states import MainGraphState, HolisticFlowEvaluation
from app.domain.langgraph.nodes.holistic_evaluator.utils import get_llm
from app.domain.langgraph.nodes.holistic_evaluator.langsmith_utils import (
    wrap_node_with_tracing,
    should_enable_langsmith,
    TRACE_NAME_HOLISTIC_FLOW,
)
from app.domain.langgraph.utils.token_tracking import extract_token_usage, accumulate_tokens
from app.domain.langgraph.utils.structured_output_parser import parse_structured_output_async

logger = logging.getLogger(__name__)

# ===== 상수 =====

def create_holistic_system_prompt(problem_context: Optional[Dict[str, Any]] = None) -> str:
    """
    Holistic Evaluator 시스템 프롬프트 생성 (문제 정보 포함)
    
    Args:
        problem_context: 문제 정보 딕셔너리
    
    Returns:
        str: 시스템 프롬프트
    """
    # 문제 정보 추출
    problem_info_section = ""
    hint_roadmap_section = ""
    
    if problem_context:
        basic_info = problem_context.get("basic_info", {})
        ai_guide = problem_context.get("ai_guide", {})
        hint_roadmap = ai_guide.get("hint_roadmap", {})
        
        problem_title = basic_info.get("title", "알 수 없음")
        key_algorithms = ai_guide.get("key_algorithms", [])
        algorithms_text = ", ".join(key_algorithms) if key_algorithms else "없음"
        
        problem_info_section = f"""
[문제 정보]
- 문제: {problem_title}
- 필수 알고리즘: {algorithms_text}

"""
        
        # 힌트 로드맵이 있는 경우 추가
        if hint_roadmap:
            hint_roadmap_section = f"""
[힌트 로드맵 (참고용)]
- 1단계: {hint_roadmap.get("step_1_concept", "")}
- 2단계: {hint_roadmap.get("step_2_state", "")}
- 3단계: {hint_roadmap.get("step_3_transition", "")}
- 4단계: {hint_roadmap.get("step_4_base_case", "")}

"""
    
    return f"""당신은 AI 코딩 테스트의 Chaining 전략을 평가하는 전문가입니다.

{problem_info_section}다음은 사용자의 턴별 대화 로그입니다. 각 턴의 의도, 프롬프트 요약, AI 추론을 분석하여 다음 항목을 평가하세요:

1. **문제 분해 (Problem Decomposition):**
   - 전체 코드가 아닌 부분 코드로 점진적으로 구성되는가?
   - 큰 문제를 작은 단계로 나누어 해결하는가?
   - 문제 특성({algorithms_text if problem_context else "알 수 없음"})에 맞는 접근 방식인가?
   - 힌트 로드맵 순서와 유사하게 진행되었는가?{hint_roadmap_section}

2. **피드백 수용성 (Feedback Integration):**
   - 턴 N의 AI 힌트 내용이 턴 N+1의 사용자 요청에 반영되었는가?
   - 이전 턴의 제안을 다음 턴에서 활용하는가?

3. **주도성 및 오류 수정 (Proactiveness):**
   - 사용자가 AI의 이전 오류를 구체적으로 지적하는가?
   - 능동적으로 개선 방향을 제시하는가?

4. **전략적 탐색 (Strategic Exploration):**
   - 의도가 HINT_OR_QUERY에서 OPTIMIZATION으로 전환되는 등 능동적인 변화가 있는가?
   - DEBUGGING에서 TEST_CASE로 전환하는 등 전략적 탐색이 있는가?

5. **고급 프롬프트 기법 활용 (Advanced Techniques Bonus):**
   - System Prompting, XML 태그, Few-shot 예시 등 고급 기법을 사용했는가?
   - 이러한 기법 사용 시 보너스 점수를 부여하세요.

각 항목은 0-100점으로 평가하세요.

**응답 형식 (반드시 다음 JSON 구조를 사용하세요):**
```json
{{
    "strategy_coherence": 0-100,  // 전략 일관성 점수 (항목 4: 전략적 탐색)
    "problem_solving_approach": 0-100,  // 문제 해결 접근법 점수 (항목 1: 문제 분해)
    "iteration_quality": 0-100,  // 반복 개선 품질 점수 (항목 2: 피드백 수용성)
    "overall_flow_score": 0-100,  // 종합 점수 (모든 항목의 가중 평균)
    "analysis": "상세 분석 내용"
}}
```

**필드 매핑:**
- `strategy_coherence`: 항목 4 (전략적 탐색) 점수
- `problem_solving_approach`: 항목 1 (문제 분해) 점수
- `iteration_quality`: 항목 2 (피드백 수용성) 점수
- `overall_flow_score`: 모든 항목을 종합한 전체 점수

**중요**: `analysis` 필드에는 다음을 포함하여 상세한 피드백을 제공하세요:
- 문제 분해 전략에 대한 구체적 평가 (어떤 부분이 잘되었고, 어떤 부분을 개선할 수 있는지)
- 피드백 수용성에 대한 구체적 평가 (이전 턴의 힌트가 어떻게 반영되었는지)
- 주도성에 대한 구체적 평가 (사용자가 어떻게 능동적으로 개선을 제시했는지)
- 전략적 탐색에 대한 구체적 평가 (의도 전환이 어떻게 이루어졌는지)
- 전체적인 체이닝 전략에 대한 종합 의견 및 개선 제안"""


async def _eval_holistic_flow_impl(state: MainGraphState) -> Dict[str, Any]:
    """
    6a: 전체 플로우 평가 - 전략 Chaining 분석 (내부 구현)
    
    평가 항목:
    1. 문제 분해 (Problem Decomposition)
    2. 피드백 수용성 (Feedback Integration)
    3. 주도성 및 오류 수정 (Proactiveness)
    4. 전략적 탐색 (Strategic Exploration)
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[6a. Eval Holistic Flow] 진입 - session_id: {session_id}")
    
    try:
        # Redis에서 모든 turn_logs 조회
        from app.infrastructure.cache.redis_client import redis_client
        all_turn_logs = await redis_client.get_all_turn_logs(session_id)
        
        logger.info(f"[6a. Eval Holistic Flow] 턴 로그 조회 - session_id: {session_id}, 턴 개수: {len(all_turn_logs)}")
        
        # Chaining 평가를 위한 구조화된 로그 생성
        structured_logs = []
        for turn_num in sorted([int(k) for k in all_turn_logs.keys()]):
            log = all_turn_logs[str(turn_num)]
            structured_logs.append({
                "turn": turn_num,
                "intent": log.get("prompt_evaluation_details", {}).get("intent", "UNKNOWN"),
                "prompt_summary": log.get("user_prompt_summary", ""),
                "llm_reasoning": log.get("llm_answer_reasoning", ""),
                "score": log.get("prompt_evaluation_details", {}).get("score", 0),
                "rubrics": log.get("prompt_evaluation_details", {}).get("rubrics", [])
            })
        
        if not structured_logs:
            logger.warning(f"[6a. Eval Holistic Flow] 턴 로그 없음 - session_id: {session_id}")
            return {
                "holistic_flow_score": 0,
                "holistic_flow_analysis": "턴 로그가 없어 평가할 수 없습니다.",
                "updated_at": datetime.utcnow().isoformat(),
            }
        
        # Holistic Flow 평가 Chain 구성
        problem_context = state.get("problem_context")
        
        def prepare_holistic_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """Holistic 평가 입력 준비 (문제 정보 포함)"""
            structured_logs = inputs.get("structured_logs", [])
            
            # 문제 정보를 포함한 시스템 프롬프트 생성
            system_prompt = create_holistic_system_prompt(problem_context)
            
            user_prompt = f"""턴별 대화 로그:

{json.dumps(structured_logs, ensure_ascii=False, indent=2)}

위 로그를 분석하여 Chaining 전략 점수를 평가하세요."""
            
            return {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
            }
        
        def format_holistic_messages(inputs: Dict[str, Any]) -> list:
            """메시지를 LangChain BaseMessage 객체로 변환"""
            from langchain_core.messages import HumanMessage, SystemMessage
            
            messages = []
            if inputs.get("system_prompt"):
                messages.append(SystemMessage(content=inputs["system_prompt"]))
            if inputs.get("user_prompt"):
                messages.append(HumanMessage(content=inputs["user_prompt"]))
            return messages
        
        def process_holistic_output_with_response(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """출력 처리 (LLM 응답 객체 포함)"""
            # Chain에서 전달되는 형태: {"llm_response": HolisticFlowEvaluation}
            if isinstance(inputs, dict):
                llm_response = inputs.get("llm_response")
            else:
                # 직접 HolisticFlowEvaluation 객체가 전달된 경우
                llm_response = inputs
            
            if llm_response is None:
                logger.error(f"[Chain] process_holistic_output_with_response - llm_response가 None입니다. inputs 타입: {type(inputs)}, inputs: {inputs}")
                raise ValueError("Holistic Flow 평가 결과를 파싱할 수 없습니다.")
            
            result = llm_response  # structured_llm의 결과는 이미 HolisticFlowEvaluation 객체
            
            processed = {
                "holistic_flow_score": result.overall_flow_score,
                "holistic_flow_analysis": result.analysis,  # 체이닝 전략에 대한 상세 분석 (문제 분해, 피드백 수용성, 주도성, 전략적 탐색)
                "strategy_coherence": result.strategy_coherence,
                "problem_solving_approach": result.problem_solving_approach,
                "iteration_quality": result.iteration_quality,
                "updated_at": datetime.utcnow().isoformat(),
                "_llm_response": llm_response  # 토큰 추출용
            }
            return processed
        
        # Chain 구성 (토큰 추출을 위해 원본 LLM 응답도 전달)
        llm = get_llm()
        structured_llm = llm.with_structured_output(HolisticFlowEvaluation)
        
        holistic_chain = (
            RunnableLambda(prepare_holistic_input)
            | RunnableLambda(format_holistic_messages)
            | structured_llm
            | RunnableLambda(lambda x: {"llm_response": x})
            | RunnableLambda(process_holistic_output_with_response)
        )
        
        try:
            # 입력 준비 및 메시지 포맷팅
            chain_input = {"structured_logs": structured_logs}
            prepared_input = prepare_holistic_input(chain_input)
            formatted_messages = format_holistic_messages(prepared_input)
            
            # 원본 LLM 호출 (1회만 - 토큰 추출 + JSON 파싱)
            logger.info(f"[6a. Eval Holistic Flow] ===== LLM 호출 시작 =====")
            logger.info(f"[6a. Eval Holistic Flow] 평가 대상 턴 수: {len(structured_logs)}")
            raw_response = await llm.ainvoke(formatted_messages)
            
            # LLM 원본 응답 로그
            if hasattr(raw_response, 'content'):
                logger.info(f"[6a. Eval Holistic Flow] LLM 원본 응답 (처음 500자): {raw_response.content[:500]}...")
            
            # 토큰 사용량 추출 및 State에 누적
            tokens = extract_token_usage(raw_response)
            if tokens:
                accumulate_tokens(state, tokens, token_type="eval")
                logger.info(f"[6a. Eval Holistic Flow] 토큰 사용량 - prompt: {tokens.get('prompt_tokens')}, completion: {tokens.get('completion_tokens')}, total: {tokens.get('total_tokens')}")
            else:
                logger.warning(f"[6a. Eval Holistic Flow] 토큰 사용량 추출 실패 - raw_response 타입: {type(raw_response)}")
            
            # 원본 응답을 구조화된 출력으로 파싱
            logger.info(f"[6a. Eval Holistic Flow] 구조화된 출력 파싱 시작...")
            try:
                from app.domain.langgraph.utils.structured_output_parser import parse_structured_output_async
                structured_result = await parse_structured_output_async(
                    raw_response=raw_response,
                    model_class=HolisticFlowEvaluation,
                    fallback_llm=structured_llm,
                    formatted_messages=formatted_messages
                )
            except Exception as parse_error:
                logger.error(f"[6a. Eval Holistic Flow] 구조화된 출력 파싱 실패: {str(parse_error)}", exc_info=True)
                # 파싱 실패 시 fallback으로 구조화된 출력 Chain 사용
                logger.info("[6a. Eval Holistic Flow] Fallback: 구조화된 출력 Chain 사용")
                structured_result = await structured_llm.ainvoke(formatted_messages)
            
            # 출력 처리 (State 형식으로 변환)
            result = {
                "holistic_flow_score": structured_result.overall_flow_score,
                "holistic_flow_analysis": structured_result.analysis,
                "strategy_coherence": structured_result.strategy_coherence,
                "problem_solving_approach": structured_result.problem_solving_approach,
                "iteration_quality": structured_result.iteration_quality,
                "updated_at": datetime.utcnow().isoformat(),
            }
            logger.info(f"[6a. Eval Holistic Flow] 구조화된 출력 파싱 완료")
            
            # State에 누적된 토큰 정보를 result에 포함 (LangGraph 병합을 위해)
            if "eval_tokens" in state:
                result["eval_tokens"] = state["eval_tokens"]
            
            # 평가 결과 로깅 (상세 분석 포함)
            analysis = result.get("holistic_flow_analysis", "")
            score = result.get("holistic_flow_score")
            logger.info(f"[6a. Eval Holistic Flow] ===== 평가 완료 =====")
            logger.info(f"[6a. Eval Holistic Flow] Holistic Flow Score: {score}")
            logger.info(f"[6a. Eval Holistic Flow] Strategy Coherence: {result.get('strategy_coherence')}")
            logger.info(f"[6a. Eval Holistic Flow] Problem Solving Approach: {result.get('problem_solving_approach')}")
            logger.info(f"[6a. Eval Holistic Flow] Iteration Quality: {result.get('iteration_quality')}")
            if analysis:
                logger.info(f"[6a. Eval Holistic Flow] Analysis (처음 500자): {analysis[:500]}...")
                logger.info(f"[6a. Eval Holistic Flow] 전체 Analysis 길이: {len(analysis)} 문자")
            else:
                logger.warning(f"[6a. Eval Holistic Flow] 분석 내용 없음 - session_id: {session_id}")
            
            # PostgreSQL에 평가 결과 저장
            try:
                from app.infrastructure.persistence.session import get_db_context
                from app.application.services.evaluation_storage_service import EvaluationStorageService
                
                # session_id를 PostgreSQL id로 변환 (Redis session_id: "session_123" -> PostgreSQL id: 123)
                postgres_session_id = int(session_id.replace("session_", "")) if session_id.startswith("session_") else None
                
                if postgres_session_id and score is not None:
                    async with get_db_context() as db:
                        storage_service = EvaluationStorageService(db)
                        
                        # 상세 정보 구성
                        details = {
                            "strategy_coherence": result.get("strategy_coherence"),
                            "problem_solving_approach": result.get("problem_solving_approach"),
                            "iteration_quality": result.get("iteration_quality"),
                            "structured_logs": structured_logs,  # 턴별 로그 정보
                        }
                        
                        await storage_service.save_holistic_flow_evaluation(
                            session_id=postgres_session_id,
                            holistic_flow_score=score,
                            holistic_flow_analysis=analysis or "",
                            details=details
                        )
                        await db.commit()
                        logger.info(
                            f"[6a. Eval Holistic Flow] PostgreSQL 저장 완료 - "
                            f"session_id: {postgres_session_id}, score: {score}"
                        )
            except Exception as pg_error:
                # PostgreSQL 저장 실패해도 Redis는 저장되었으므로 경고만
                logger.warning(
                    f"[6a. Eval Holistic Flow] PostgreSQL 저장 실패 (Redis는 저장됨) - "
                    f"session_id: {session_id}, error: {str(pg_error)}"
                )
            
            # LangSmith 추적 정보 로깅
            if should_enable_langsmith(state):
                logger.debug(f"[LangSmith] 6a 노드 추적 활성화 - session_id: {session_id}, 턴 개수: {len(structured_logs)}")
            
            return result
            
        except Exception as e:
            logger.error(f"[6a. Eval Holistic Flow] LLM 평가 오류 - session_id: {session_id}, error: {str(e)}", exc_info=True)
            return {
                "holistic_flow_score": None,
                "holistic_flow_analysis": None,
                "error_message": f"Holistic flow 평가 실패: {str(e)}",
                "updated_at": datetime.utcnow().isoformat(),
            }
            
    except Exception as e:
        logger.error(f"[6a. Eval Holistic Flow] 오류 - session_id: {session_id}, error: {str(e)}", exc_info=True)
        return {
            "holistic_flow_score": None,
            "holistic_flow_analysis": None,
            "error_message": f"Holistic flow 평가 실패: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }


# ===== 외부 래퍼 함수 =====

async def eval_holistic_flow(state: MainGraphState) -> Dict[str, Any]:
    """
    6a: 전체 플로우 평가 - 전략 Chaining 분석
    
    LangSmith 추적:
    - State의 enable_langsmith_tracing 값에 따라 활성화/비활성화
    - None이면 환경 변수 LANGCHAIN_TRACING_V2 사용
    
    사용 예시:
    - State에 enable_langsmith_tracing=True 설정 시 추적 활성화
    - State에 enable_langsmith_tracing=False 설정 시 추적 비활성화
    - State에 enable_langsmith_tracing=None 설정 시 환경 변수 사용
    """
    # LangSmith 추적과 함께 래핑
    wrapped_func = wrap_node_with_tracing(
        node_name=TRACE_NAME_HOLISTIC_FLOW,
        impl_func=_eval_holistic_flow_impl,
        state=state
    )
    return await wrapped_func(state)

