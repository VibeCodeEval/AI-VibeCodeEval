import logging
from typing import Any

from app.domain.langgraph.states import EvalTurnState

logger = logging.getLogger(__name__)

# V2.3: 6대 통합 의도 → 평가 노드 1:1 매핑
UNIFIED_TO_NODE: dict[str, str] = {
    "SETTING": "eval_rule_setting",
    "CREATION": "eval_generation",
    "REFINEMENT": "eval_optimization",
    "DEBUGGING": "eval_debugging",
    "EXPLORATION": "eval_exploration",
    "FOLLOW_UP": "eval_follow_up",
    # 구버전·저장 데이터 호환
    "VALIDATION": "eval_debugging",
}

DEFAULT_NODE = "eval_debugging"


def intent_router(state: EvalTurnState) -> list[str]:
    """
    4.0.1: Intent Router
    V2.3: 6대 통합 의도(unified_intent)에 따라 단일 평가 노드로 분기.
    """
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    unified_intent = state.get("unified_intent", "")
    intent_types = state.get("intent_types", [])

    # unified_intent 우선, 없으면 intent_types[0] 사용
    primary = (unified_intent or (intent_types[0] if intent_types else "")).upper().strip()
    node = UNIFIED_TO_NODE.get(primary, DEFAULT_NODE)

    logger.info(
        f"[4.0.1 Intent Router] 의도별 라우팅 - session_id: {session_id}, turn: {turn}, "
        f"unified_intent: {unified_intent}, 노드: {node}"
    )

    return [node]
