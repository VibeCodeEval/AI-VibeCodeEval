"""
6a: 전체 플로우 평가 - 전략 Chaining 분석

[구조]
- 상수: 프롬프트 템플릿
- Chain 구성 함수: 평가 Chain 생성
- 내부 구현: 실제 평가 로직
- 외부 래퍼: LangSmith 추적 제어
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from langchain_core.runnables import RunnableLambda

from app.domain.langgraph.nodes.holistic_evaluator.langsmith_utils import (
    TRACE_NAME_HOLISTIC_FLOW, should_enable_langsmith, wrap_node_with_tracing)
from app.domain.langgraph.nodes.holistic_evaluator.utils import get_llm
from app.domain.langgraph.states import HolisticFlowEvaluation, MainGraphState
from app.domain.langgraph.utils.structured_output_parser import \
    parse_structured_output_async
from app.domain.langgraph.utils.token_tracking import (accumulate_tokens,
                                                       extract_token_usage)

logger = logging.getLogger(__name__)

# ===== 상수 =====


def create_holistic_system_prompt(
    problem_context: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Holistic Evaluator 시스템 프롬프트 생성 (문제 정보 포함)

    YAML 파일에서 프롬프트 템플릿을 로드하고 변수를 치환합니다.

    Args:
        problem_context: 문제 정보 딕셔너리

    Returns:
        str: 시스템 프롬프트
    """
    from app.domain.langgraph.prompts import render_prompt

    # 문제 정보 추출
    problem_info_section = ""
    hint_roadmap_section = ""
    algorithms_text = "알 수 없음"

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

    # YAML 템플릿에서 프롬프트 렌더링
    return render_prompt(
        "eval_holistic_flow",
        problem_info_section=problem_info_section,
        algorithms_text=algorithms_text,
        hint_roadmap_section=hint_roadmap_section,
    )


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

        logger.info(
            f"[6a. Eval Holistic Flow] 턴 로그 조회 - session_id: {session_id}, 턴 개수: {len(all_turn_logs)}"
        )

        # Chaining 평가를 위한 구조화된 로그 생성
        # PostgreSQL에서 모든 턴의 ai_summary를 한 번에 조회 (성능 최적화)
        ai_summaries_map = {}  # {turn_num: ai_summary}
        try:
            from sqlalchemy import and_, select, text

            from app.infrastructure.persistence.models.enums import \
                EvaluationTypeEnum
            from app.infrastructure.persistence.models.sessions import \
                PromptEvaluation
            from app.infrastructure.persistence.session import get_db_context

            # session_id를 PostgreSQL id로 변환
            postgres_session_id = (
                int(session_id.replace("session_", ""))
                if session_id.startswith("session_")
                else None
            )

            if postgres_session_id:
                turn_numbers = sorted([int(k) for k in all_turn_logs.keys()])
                if turn_numbers:
                    async with get_db_context() as db:
                        # 모든 턴의 평가 결과를 한 번에 조회
                        query = select(PromptEvaluation).where(
                            and_(
                                PromptEvaluation.session_id == postgres_session_id,
                                PromptEvaluation.turn.in_(turn_numbers),
                                text(
                                    "prompt_evaluations.evaluation_type::text = :eval_type"
                                ),
                            )
                        )
                        result = await db.execute(
                            query.params(eval_type=EvaluationTypeEnum.TURN_EVAL.value)
                        )
                        evaluations = result.scalars().all()

                        # turn별로 ai_summary 매핑
                        for evaluation in evaluations:
                            if evaluation.turn is not None and evaluation.details:
                                ai_summary = evaluation.details.get("ai_summary", "")
                                if ai_summary:
                                    ai_summaries_map[evaluation.turn] = ai_summary

                        logger.debug(
                            f"[6a. Eval Holistic Flow] PostgreSQL에서 ai_summary 조회 완료 - {len(ai_summaries_map)}개 턴"
                        )
        except Exception as e:
            logger.debug(
                f"[6a. Eval Holistic Flow] PostgreSQL에서 ai_summary 조회 실패 (Redis 사용) - error: {str(e)}"
            )

        structured_logs = []
        for turn_num in sorted([int(k) for k in all_turn_logs.keys()]):
            log = all_turn_logs[str(turn_num)]

            # ai_summary 우선순위: PostgreSQL > Redis turn_log
            ai_summary = (
                ai_summaries_map.get(turn_num)
                or log.get("llm_answer_summary", "")
                or log.get("answer_summary", "")
            )

            structured_logs.append(
                {
                    "turn": turn_num,
                    "intent": log.get("prompt_evaluation_details", {}).get(
                        "intent", "UNKNOWN"
                    ),
                    "prompt_summary": log.get("user_prompt_summary", ""),
                    "llm_reasoning": log.get("llm_answer_reasoning", ""),
                    "ai_summary": ai_summary,  # AI 응답 요약 (Chaining 전략 평가에 사용)
                    "score": log.get("prompt_evaluation_details", {}).get("score", 0),
                    "rubrics": log.get("prompt_evaluation_details", {}).get(
                        "rubrics", []
                    ),
                }
            )

        if not structured_logs:
            logger.warning(
                f"[6a. Eval Holistic Flow] 턴 로그 없음 - session_id: {session_id}"
            )
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

        def process_holistic_output_with_response(
            inputs: Dict[str, Any],
        ) -> Dict[str, Any]:
            """출력 처리 (LLM 응답 객체 포함)"""
            # Chain에서 전달되는 형태: {"llm_response": HolisticFlowEvaluation}
            if isinstance(inputs, dict):
                llm_response = inputs.get("llm_response")
            else:
                # 직접 HolisticFlowEvaluation 객체가 전달된 경우
                llm_response = inputs

            if llm_response is None:
                logger.error(
                    f"[Chain] process_holistic_output_with_response - llm_response가 None입니다. inputs 타입: {type(inputs)}, inputs: {inputs}"
                )
                raise ValueError("Holistic Flow 평가 결과를 파싱할 수 없습니다.")

            result = (
                llm_response  # structured_llm의 결과는 이미 HolisticFlowEvaluation 객체
            )

            processed = {
                "holistic_flow_score": result.overall_flow_score,
                "holistic_flow_analysis": result.analysis,  # 체이닝 전략에 대한 상세 분석 (문제 분해, 피드백 수용성, 주도성, 전략적 탐색)
                "problem_decomposition": result.problem_decomposition,
                "feedback_integration": result.feedback_integration,
                "strategic_exploration": result.strategic_exploration,
                "updated_at": datetime.utcnow().isoformat(),
                "_llm_response": llm_response,  # 토큰 추출용
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
            logger.info(
                f"[6a. Eval Holistic Flow] 평가 대상 턴 수: {len(structured_logs)}"
            )
            raw_response = await llm.ainvoke(formatted_messages)

            # LLM 원본 응답 로그
            if hasattr(raw_response, "content"):
                logger.info(
                    f"[6a. Eval Holistic Flow] LLM 원본 응답 (처음 500자): {raw_response.content[:500]}..."
                )

            # 토큰 사용량 추출 및 State에 누적
            tokens = extract_token_usage(raw_response)
            if tokens:
                accumulate_tokens(state, tokens, token_type="eval")
                logger.info(
                    f"[6a. Eval Holistic Flow] 토큰 사용량 - prompt: {tokens.get('prompt_tokens')}, completion: {tokens.get('completion_tokens')}, total: {tokens.get('total_tokens')}"
                )
            else:
                logger.warning(
                    f"[6a. Eval Holistic Flow] 토큰 사용량 추출 실패 - raw_response 타입: {type(raw_response)}"
                )

            # 원본 응답을 구조화된 출력으로 파싱
            logger.info(f"[6a. Eval Holistic Flow] 구조화된 출력 파싱 시작...")
            try:
                from app.domain.langgraph.utils.structured_output_parser import \
                    parse_structured_output_async

                structured_result = await parse_structured_output_async(
                    raw_response=raw_response,
                    model_class=HolisticFlowEvaluation,
                    fallback_llm=structured_llm,
                    formatted_messages=formatted_messages,
                )
            except Exception as parse_error:
                logger.error(
                    f"[6a. Eval Holistic Flow] 구조화된 출력 파싱 실패: {str(parse_error)}",
                    exc_info=True,
                )
                # 파싱 실패 시 fallback으로 구조화된 출력 Chain 사용
                logger.info(
                    "[6a. Eval Holistic Flow] Fallback: 구조화된 출력 Chain 사용"
                )
                structured_result = await structured_llm.ainvoke(formatted_messages)

            # 출력 처리 (State 형식으로 변환)
            result = {
                "holistic_flow_score": structured_result.overall_flow_score,
                "holistic_flow_analysis": structured_result.analysis,
                "problem_decomposition": structured_result.problem_decomposition,
                "feedback_integration": structured_result.feedback_integration,
                "strategic_exploration": structured_result.strategic_exploration,
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
            logger.info(
                f"[6a. Eval Holistic Flow] Problem Decomposition: {result.get('problem_decomposition')}"
            )
            logger.info(
                f"[6a. Eval Holistic Flow] Feedback Integration: {result.get('feedback_integration')}"
            )
            logger.info(
                f"[6a. Eval Holistic Flow] Strategic Exploration: {result.get('strategic_exploration')}"
            )
            if analysis:
                logger.info(
                    f"[6a. Eval Holistic Flow] Analysis (처음 500자): {analysis[:500]}..."
                )
                logger.info(
                    f"[6a. Eval Holistic Flow] 전체 Analysis 길이: {len(analysis)} 문자"
                )

                # 전체 분석 텍스트 JSON 출력 (발표자료용)
                analysis_json = {
                    "session_id": session_id,
                    "holistic_flow_score": score,
                    "problem_decomposition": result.get("problem_decomposition"),
                    "feedback_integration": result.get("feedback_integration"),
                    "strategic_exploration": result.get("strategic_exploration"),
                    "analysis_text": analysis,
                }
                logger.info("")
                logger.info(
                    f"[6a. Eval Holistic Flow] ===== Holistic Flow 평가 분석 텍스트 (JSON) ====="
                )
                logger.info(json.dumps(analysis_json, indent=4, ensure_ascii=False))
                logger.info("")
            else:
                logger.warning(
                    f"[6a. Eval Holistic Flow] 분석 내용 없음 - session_id: {session_id}"
                )

            # PostgreSQL에 평가 결과 저장
            try:
                from app.application.services.evaluation_storage_service import \
                    EvaluationStorageService
                from app.infrastructure.persistence.session import \
                    get_db_context

                # session_id를 PostgreSQL id로 변환 (Redis session_id: "session_123" -> PostgreSQL id: 123)
                postgres_session_id = (
                    int(session_id.replace("session_", ""))
                    if session_id.startswith("session_")
                    else None
                )

                if postgres_session_id and score is not None:
                    async with get_db_context() as db:
                        storage_service = EvaluationStorageService(db)

                        # 상세 정보 구성
                        details = {
                            "problem_decomposition": result.get(
                                "problem_decomposition"
                            ),
                            "feedback_integration": result.get("feedback_integration"),
                            "strategic_exploration": result.get(
                                "strategic_exploration"
                            ),
                            "structured_logs": structured_logs,  # 턴별 로그 정보
                        }

                        await storage_service.save_holistic_flow_evaluation(
                            session_id=postgres_session_id,
                            holistic_flow_score=score,
                            holistic_flow_analysis=analysis or "",
                            details=details,
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
                logger.debug(
                    f"[LangSmith] 6a 노드 추적 활성화 - session_id: {session_id}, 턴 개수: {len(structured_logs)}"
                )

            return result

        except Exception as e:
            logger.error(
                f"[6a. Eval Holistic Flow] LLM 평가 오류 - session_id: {session_id}, error: {str(e)}",
                exc_info=True,
            )
            return {
                "holistic_flow_score": None,
                "holistic_flow_analysis": None,
                "error_message": f"Holistic flow 평가 실패: {str(e)}",
                "updated_at": datetime.utcnow().isoformat(),
            }

    except Exception as e:
        logger.error(
            f"[6a. Eval Holistic Flow] 오류 - session_id: {session_id}, error: {str(e)}",
            exc_info=True,
        )
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
        state=state,
    )
    return await wrapped_func(state)
