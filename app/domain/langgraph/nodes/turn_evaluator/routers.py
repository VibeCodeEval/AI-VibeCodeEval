import logging

from app.domain.langgraph.states import EvalTurnState
from app.infrastructure.persistence.models.enums import CodeIntentType

logger = logging.getLogger(__name__)


def intent_router(state: EvalTurnState) -> list[str]:
    """
    4.0.1: Intent Router
    의도에 따라 개별 평가 노드로 분기 (다중 선택 시 병렬 실행)
    """
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    intent_types = state.get("intent_types", [])

    # 하위 호환성: intent_types가 없고 intent_type만 있는 경우 처리
    if not intent_types and state.get("intent_type"):
        intent_types = [state.get("intent_type")]

    # 기본값 처리
    if not intent_types:
        intent_types = [CodeIntentType.HINT_OR_QUERY.value]

    logger.info(
        f"[4.0.1 Intent Router] 의도별 라우팅 - session_id: {session_id}, turn: {turn}, 의도: {intent_types}"
    )

    routing_map = {
        CodeIntentType.SYSTEM_PROMPT.value: "eval_system_prompt",  # 신규 추가
        CodeIntentType.RULE_SETTING.value: "eval_rule_setting",
        CodeIntentType.GENERATION.value: "eval_generation",
        CodeIntentType.OPTIMIZATION.value: "eval_optimization",
        CodeIntentType.DEBUGGING.value: "eval_debugging",
        CodeIntentType.TEST_CASE.value: "eval_test_case",
        CodeIntentType.HINT_OR_QUERY.value: "eval_hint_query",
        CodeIntentType.FOLLOW_UP.value: "eval_follow_up",
    }

    # 선택된 모든 평가 노드 반환 (중복 제거)
    selected_nodes = list(
        set(routing_map.get(intent, "eval_hint_query") for intent in intent_types)
    )

    return selected_nodes
