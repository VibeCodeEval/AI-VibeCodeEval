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
from app.domain.langgraph.nodes.eval.holistic_debate_skip import (
    HOLISTIC_DEBATE_SKIP_MESSAGE,
    build_skipped_holistic_debate_result,
)
from app.domain.langgraph.states import DebateState, MainGraphState
from app.domain.langgraph.subgraph_debate import create_debate_subgraph
from app.domain.langgraph.utils.guardrail_turns import filter_turn_material_for_debate
from app.infrastructure.cache.redis_client import redis_client

logger = logging.getLogger(__name__)


async def _maybe_save_debate_log_to_redis(
    session_id: str, payload: Dict[str, Any]
) -> None:
    if not get_settings().DEBATE_LOG_TO_REDIS:
        return
    try:
        await redis_client.save_debate_log(session_id, payload)
        logger.info(
            "[N8] Redis debate_log 저장 완료 - key debate_log:%s", session_id
        )
    except Exception as redis_err:
        logger.warning(
            "[N8] Redis debate_log 저장 실패 (그래프는 정상 진행) - %s",
            redis_err,
        )


def _synthesize_turn_logs_from_scores(
    turn_scores: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """
    Redis turn_logs가 비어도 N8 토론이 진행되도록 최소 컨텍스트를 생성한다.

    목적:
    - Redis 장애/누락으로 turn_logs가 비어 있을 때 오탐 스킵 방지
    - turn_scores 기반으로 intent/점수 궤적은 유지
    """
    synthesized: Dict[str, Dict[str, Any]] = {}
    for key, entry in (turn_scores or {}).items():
        if not isinstance(entry, dict):
            continue
        synthesized[str(key)] = {
            "user_prompt_summary": "(Redis turn_logs 없음: turn_scores 폴백)",
            "llm_answer_summary": "(Redis turn_logs 없음: turn_scores 폴백)",
            "prompt_evaluation_details": {
                "intent": entry.get("intent_type") or entry.get("unified_intent") or "UNKNOWN",
                "score": entry.get("turn_score", 0),
                "reasoning": "(turn_scores 기반 최소 컨텍스트)",
            },
        }
    return synthesized


async def holistic_debate_skipped_flow(state: MainGraphState) -> Dict[str, Any]:
    """
    N8 스킵: LLM 토론 없이 holistic 0점·debate_log 플레이스홀더만 반환.
    """
    session_id = state.get("session_id", "unknown")
    logger.info(
        "[N8. Holistic Debate] 스킵 — %s (session_id=%s)",
        HOLISTIC_DEBATE_SKIP_MESSAGE,
        session_id,
    )
    result = build_skipped_holistic_debate_result()
    await _maybe_save_debate_log_to_redis(
        session_id,
        {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "holistic_flow_score": result["holistic_flow_score"],
            "r4_context_maintenance_score": result["r4_context_maintenance_score"],
            "holistic_flow_analysis": result["holistic_flow_analysis"],
            "initial_opinions": result["debate_initial_opinions"],
            "rebuttals": result["debate_rebuttals"],
            "debate_log": result["debate_log"],
            "skipped": True,
            "skip_reason": HOLISTIC_DEBATE_SKIP_MESSAGE,
        },
    )
    return result


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

    raw_turn_scores = state.get("turn_scores") or {}
    turn_logs, debate_turn_scores, excluded_turns = filter_turn_material_for_debate(
        turn_logs, raw_turn_scores, state
    )
    logger.info(
        "[N8] 토론용 turn_logs (가드레일 제외) - 턴 수: %s (원본 %s)",
        len(turn_logs),
        len(raw_turn_scores) if isinstance(raw_turn_scores, dict) else 0,
    )
    logger.info(
        "[N8] 토론용 turn_scores (가드레일 제외) - 턴 수: %s, 키: %s",
        len(debate_turn_scores),
        sorted(debate_turn_scores.keys(), key=lambda k: int(k) if str(k).isdigit() else 0),
    )
    if excluded_turns:
        logger.info(
            "[N8] N8 토론에서 제외된 턴 (turn_logs·turn_scores·대화요약): %s",
            excluded_turns,
        )

    if not turn_logs and not debate_turn_scores:
        logger.info(
            "[N8] 비가드레일 turn_logs/turn_scores 모두 없음 — %s",
            HOLISTIC_DEBATE_SKIP_MESSAGE,
        )
        return await holistic_debate_skipped_flow(state)

    if not turn_logs and debate_turn_scores:
        logger.warning(
            "[N8] Redis turn_logs 없음 + 비가드레일 turn_scores=%s건 — "
            "오탐 스킵 방지를 위해 turn_scores 기반 최소 컨텍스트로 토론 진행",
            len(debate_turn_scores),
        )
        turn_logs = _synthesize_turn_logs_from_scores(debate_turn_scores)
        logger.info(
            "[N8] 토론용 합성 turn_logs 생성 완료 - 턴 수: %s",
            len(turn_logs),
        )

    # ── DebateState 구성 ─────────────────────────────────────────────────
    debate_input: DebateState = {
        "session_id": session_id,
        "problem_context": state.get("problem_context"),
        "code_content": state.get("code_content"),

        # N4 (가드레일 턴 제외 — 토론 컨텍스트·R4 궤적)
        "turn_scores": debate_turn_scores,
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

        await _maybe_save_debate_log_to_redis(
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
