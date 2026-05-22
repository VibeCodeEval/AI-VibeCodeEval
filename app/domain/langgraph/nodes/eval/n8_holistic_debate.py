"""
N8: Holistic Debate Flow (다중 에이전트 토론)

MainGraphState에서 필요한 컨텍스트를 DebateState로 변환한 뒤
create_debate_subgraph()를 호출하여 3개 LLM 토론을 실행합니다.

[N8이 수집하는 정보]
- N4 (turn_scores):    턴별 숫자 점수 (MainGraphState)
- N4 (turn_logs):      턴별 전체 평가 내용 — Redis에서 직접 읽음
                       (user_prompt_summary, llm_answer_summary,
                        intent, rubrics, final_reasoning)
- N5 (Judge0):         code_correctness_score, code_performance_score,
                       test_cases_passed/total, execution_time, memory_used_mb
- N6 (Radon CC):       code_quality_metrics (avg_cc, max_cc, delta_cc, junior_grade)
- N7 (LLM 코드리뷰):  code_eval_report (efficiency/readability/error_handling review)

출력:
- holistic_flow_score (float, 0-100): 토론 합의 기반 종합 점수
- holistic_flow_analysis (str): 토론 분석 요약
- debate_log (List[Dict]): 전체 토론 기록 (rubric_json 저장용)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.core.config import get_settings
from app.domain.langgraph.states import DebateState, MainGraphState
from app.domain.langgraph.subgraph_debate import create_debate_subgraph
from app.domain.langgraph.utils.guardrail_turns import filter_turn_logs_for_debate
from app.infrastructure.cache.redis_client import redis_client

logger = logging.getLogger(__name__)


async def holistic_debate_flow(state: MainGraphState) -> Dict[str, Any]:
    """
    N8: 모든 평가 정보를 수집한 뒤 다중 에이전트 토론 SubGraph 실행

    구 holistic_flow처럼 Redis에서 상세 turn_logs를 읽어
    에이전트에게 대화 원문 + 평가 내용 전체를 제공합니다.
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[N8. Holistic Debate] 다중 에이전트 토론 시작 - session_id: {session_id}")

    # ── N4 Redis turn_logs 읽기 ───────────────────────────────────────────
    # N4가 save_turn_log()로 저장한 detailed_turn_log 전체를 가져옴
    # 구조: {turn_key: {user_prompt_summary, llm_answer_summary, prompt_evaluation_details}}
    try:
        turn_logs = await redis_client.get_all_turn_logs(session_id)
        logger.info(f"[N8] Redis turn_logs 로드 완료 - 턴 수: {len(turn_logs)}")
    except Exception as e:
        logger.warning(f"[N8] Redis turn_logs 로드 실패 (폴백: 빈 dict) - {e}")
        turn_logs = {}

    turn_logs = filter_turn_logs_for_debate(turn_logs, state)
    logger.info(
        "[N8] 토론용 turn_logs (가드레일 제외) - 턴 수: %s",
        len(turn_logs),
    )

    # ── DebateState 구성 ─────────────────────────────────────────────────
    debate_input: DebateState = {
        "session_id": session_id,
        "problem_context": state.get("problem_context"),
        "code_content": state.get("code_content"),

        # N4
        "turn_scores": state.get("turn_scores"),
        "aggregate_turn_score": state.get("aggregate_turn_score"),
        "turn_logs": turn_logs,

        # N5
        "code_correctness_score": state.get("code_correctness_score"),
        "code_performance_score": state.get("code_performance_score"),
        "test_cases_passed": state.get("test_cases_passed"),
        "test_cases_total": state.get("test_cases_total"),
        "execution_time": state.get("execution_time"),
        "memory_used_mb": state.get("memory_used_mb"),
        "correctness_reasoning": state.get("correctness_reasoning"),

        # N6
        "code_quality_metrics": state.get("code_quality_metrics"),

        # N7
        "code_eval_report": state.get("code_eval_report"),

        # reducer 필드 초기값
        "initial_opinions": [],
        "rebuttals": [],

        # 출력 필드 초기값
        "holistic_flow_score": None,
        "holistic_flow_analysis": None,
        "debate_log": None,
    }

    try:
        debate_graph = create_debate_subgraph()
        result = await debate_graph.ainvoke(debate_input)

        holistic_score = result.get("holistic_flow_score")
        holistic_analysis = result.get("holistic_flow_analysis")
        debate_log = result.get("debate_log")

        logger.info(
            f"[N8. Holistic Debate] 토론 완료 - "
            f"holistic_flow_score: {holistic_score}, "
            f"R1 opinions: {len(result.get('initial_opinions', []))}, "
            f"R2 rebuttals: {len(result.get('rebuttals', []))}"
        )

        # Redis: 선택 시에만 저장 (DEBATE_LOG_TO_REDIS=true). 기본은 비활성.
        if get_settings().DEBATE_LOG_TO_REDIS:
            try:
                await redis_client.save_debate_log(
                    session_id,
                    {
                        "saved_at": datetime.now(timezone.utc).isoformat(),
                        "session_id": session_id,
                        "holistic_flow_score": holistic_score,
                        "r4_context_maintenance_score": result.get(
                            "r4_context_maintenance_score"
                        ),
                        "holistic_flow_analysis": holistic_analysis,
                        "initial_opinions": result.get("initial_opinions", []),
                        "rebuttals": result.get("rebuttals", []),
                        "debate_log": debate_log,
                    },
                )
                logger.info(
                    f"[N8] Redis debate_log 저장 완료 - key debate_log:{session_id}"
                )
            except Exception as redis_err:
                logger.warning(
                    f"[N8] Redis debate_log 저장 실패 (그래프는 정상 진행) - {redis_err}"
                )

        return {
            "holistic_flow_score": holistic_score,
            "holistic_flow_analysis": holistic_analysis,
            "debate_log": debate_log,
            "debate_initial_opinions": result.get("initial_opinions", []),
            "debate_rebuttals": result.get("rebuttals", []),
            "r4_context_maintenance_score": result.get(
                "r4_context_maintenance_score"
            ),
        }

    except Exception as e:
        logger.error(
            f"[N8. Holistic Debate] 토론 실패 - session_id: {session_id}, error: {e}",
            exc_info=True,
        )
        return {
            "holistic_flow_score": None,
            "holistic_flow_analysis": f"다중 에이전트 토론 실패: {e}",
            "debate_log": None,
            "debate_initial_opinions": [],
            "debate_rebuttals": [],
            "r4_context_maintenance_score": None,
        }
