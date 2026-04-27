import logging
import re
from typing import Any, Dict, Tuple

from langchain_core.messages import HumanMessage, SystemMessage

from app.domain.langgraph.nodes.eval_turn.utils import get_llm
from app.domain.langgraph.states import EvalTurnState, IntentTurnLLMOutput
from app.domain.langgraph.utils.structured_output_parser import \
    parse_structured_output_async
from app.domain.langgraph.utils.token_tracking import (accumulate_tokens,
                                                       extract_token_usage)
from app.infrastructure.persistence.models.enums import UnifiedIntentType

logger = logging.getLogger(__name__)

_INTENT_VALUES = {e.value for e in UnifiedIntentType}


def has_role_content_tags(text: str) -> bool:
    """<Role> 또는 <Content> 태그가 있는지 확인"""
    return bool(re.search(r"<Role>|<Content>", text, re.IGNORECASE))


def _default_previous_summary(state: EvalTurnState) -> str:
    raw = (state.get("previous_turns_summary") or "").strip()
    return raw if raw else "(제공 없음)"


def _parse_predicted_intent(raw: str) -> Tuple[UnifiedIntentType, str]:
    """LLM predicted_intent → UnifiedIntentType, 실패 시 DEBUGGING."""
    s = (raw or "").strip().upper()
    if s in _INTENT_VALUES:
        return UnifiedIntentType(s), "intent_llm"
    # 흔한 변형
    if s in ("VALIDATION",):
        return UnifiedIntentType.DEBUGGING, "intent_llm_legacy_validation"
    logger.warning(f"[4.0 Intent Analysis] 알 수 없는 predicted_intent={raw!r} → DEBUGGING")
    return UnifiedIntentType.DEBUGGING, "intent_llm_invalid_label"


async def _classify_intent_single_llm(
    state: EvalTurnState,
    human_message: str,
    is_first_turn: bool,
) -> IntentTurnLLMOutput:
    """6대 통합 의도 단일 LLM (predicted_intent + intent_cot)."""
    from app.domain.langgraph.prompts import render_prompt

    llm = get_llm()
    structured_llm = llm.with_structured_output(IntentTurnLLMOutput)

    first_turn_note = (
        "**첫 턴**: FOLLOW_UP은 선택할 수 없습니다.\n\n"
        if is_first_turn
        else ""
    )
    system_prompt = render_prompt(
        "eval_intent_disambiguation",
        previous_turns_summary=_default_previous_summary(state),
        text=human_message,
        first_turn_note=first_turn_note,
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content="위 지시에 따라 predicted_intent와 intent_cot만 담은 JSON을 출력하세요."
        ),
    ]

    raw_response = await llm.ainvoke(messages)
    tokens = extract_token_usage(raw_response)
    if tokens:
        accumulate_tokens(state, tokens, token_type="eval")

    try:
        return await parse_structured_output_async(
            raw_response=raw_response,
            model_class=IntentTurnLLMOutput,
            fallback_llm=structured_llm,
            formatted_messages=messages,
        )
    except Exception as e:
        logger.error(
            f"[4.0 Intent Analysis] 의도 LLM 파싱 실패: {e}",
            exc_info=True,
        )
        return await structured_llm.ainvoke(messages)


async def intent_analysis(state: EvalTurnState) -> Dict[str, Any]:
    """
    4.0: Intent Analysis — 단일 LLM으로 6대 통합 의도 선택.

    출력 스키마: predicted_intent, intent_cot (eval_intent_disambiguation.yaml).
    """
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.0 Intent Analysis] 진입 - session_id: {session_id}, turn: {turn}")

    human_message = state.get("human_message", "")

    is_first_turn = turn == 1
    has_role_content = has_role_content_tags(human_message)

    try:
        parsed = await _classify_intent_single_llm(
            state,
            human_message,
            is_first_turn=is_first_turn,
        )

        unified_enum, path = _parse_predicted_intent(parsed.predicted_intent)
        confidence = 0.9
        reasoning = f"{path};{parsed.intent_cot}"

        unified = unified_enum.value
        intent_values = [unified]

        if is_first_turn and unified == UnifiedIntentType.FOLLOW_UP.value:
            logger.warning(
                f"[4.0 Intent Analysis] 첫 턴 FOLLOW_UP → 재분류. human_preview={human_message[:120]!r}"
            )
            if has_role_content:
                unified = UnifiedIntentType.SETTING.value
                intent_values = [unified]
                reasoning = f"{reasoning};first_turn_override_setting"
            else:
                unified = UnifiedIntentType.CREATION.value
                intent_values = [unified]
                reasoning = f"{reasoning};first_turn_override_creation"
            confidence = min(confidence, 0.85)

        logger.info(
            f"[4.0 Intent Analysis] 완료 - session_id: {session_id}, turn: {turn}, "
            f"의도: {intent_values}, unified_intent: {unified}, 신뢰도: {confidence:.2f}, 경로: {reasoning[:200]}"
        )

        result: Dict[str, Any] = {
            "intent_types": intent_values,
            "intent_confidence": confidence,
            "unified_intent": unified,
        }

        if "eval_tokens" in state:
            result["eval_tokens"] = state["eval_tokens"]

        return result

    except Exception as e:
        logger.error(
            f"[4.0 Intent Analysis] 오류 - session_id: {session_id}, turn: {turn}, error: {str(e)}",
            exc_info=True,
        )
        return {
            "intent_types": [UnifiedIntentType.DEBUGGING.value],
            "intent_confidence": 0.0,
            "unified_intent": UnifiedIntentType.DEBUGGING.value,
        }
