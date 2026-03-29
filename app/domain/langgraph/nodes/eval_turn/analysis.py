import logging
import re
from typing import Any, Dict, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage

from app.domain.langgraph.nodes.eval_turn.utils import get_llm
from app.domain.langgraph.states import (EvalTurnState, IntentClassification,
                                         PromptCharacteristics)
from app.domain.langgraph.utils.structured_output_parser import \
    parse_structured_output_async
from app.domain.langgraph.utils.token_tracking import (accumulate_tokens,
                                                       extract_token_usage)
from app.infrastructure.persistence.models.enums import UnifiedIntentType

logger = logging.getLogger(__name__)

# 짧은 동의·진행만 있는 턴 (FOLLOW_UP 후보)
_FOLLOW_ACK = re.compile(
    r"^(?:\s*)(?:응|네|좋아요?|알겠|고마워요?|감사|thx|thanks|thank\s+you|ok(?:ay)?|yes|yep|계속|다음|진행)(?:[\s.,!~…]|$)",
    re.IGNORECASE | re.UNICODE,
)


def has_role_content_tags(text: str) -> bool:
    """<Role> 또는 <Content> 태그가 있는지 확인"""
    return bool(re.search(r"<Role>|<Content>", text, re.IGNORECASE))


def _looks_like_follow_up(human: str, c: PromptCharacteristics) -> bool:
    """규칙 기반 FOLLOW_UP 후보 (코드·에러·작성 요청이 없을 때만)."""
    if c.has_code_snippet or c.is_error_reported or c.is_requesting_new_code:
        return False
    if c.is_asking_for_concept:
        return False
    s = human.strip()
    if len(s) > 100:
        return False
    if _FOLLOW_ACK.match(s):
        return True
    return len(s) <= 12 and len(s) > 0


def _resolve_intent_from_characteristics(
    human_message: str,
    chars: PromptCharacteristics,
) -> Optional[Tuple[UnifiedIntentType, float, str]]:
    """
    2단계(규칙): 특성 → 의도. None이면 폴백 LLM 호출.
    """
    if has_role_content_tags(human_message):
        return (UnifiedIntentType.SETTING, 0.9, "rule:role_or_content_tags")

    if chars.is_error_reported:
        return (UnifiedIntentType.DEBUGGING, 0.92, "rule:error_reported")

    if chars.is_requesting_new_code and chars.has_code_snippet:
        return (UnifiedIntentType.REFINEMENT, 0.88, "rule:modify_with_code_context")

    if chars.is_requesting_new_code:
        return (UnifiedIntentType.CREATION, 0.88, "rule:new_code_request")

    if chars.is_asking_for_concept and not chars.is_requesting_new_code:
        return (UnifiedIntentType.EXPLORATION, 0.9, "rule:concept_only")

    if chars.is_asking_for_concept:
        return (UnifiedIntentType.EXPLORATION, 0.82, "rule:concept_with_code_request")

    if _looks_like_follow_up(human_message, chars):
        return (UnifiedIntentType.FOLLOW_UP, 0.78, "rule:short_ack_or_proceed")

    return None


def _format_characteristics_block(c: PromptCharacteristics) -> str:
    return (
        f"- has_code_snippet: {c.has_code_snippet}\n"
        f"- is_error_reported: {c.is_error_reported}\n"
        f"- is_asking_for_concept: {c.is_asking_for_concept}\n"
        f"- is_requesting_new_code: {c.is_requesting_new_code}"
    )


async def _extract_prompt_characteristics(
    state: EvalTurnState,
    human_message: str,
    ai_message: str,
    is_first_turn: bool,
    has_role_content: bool,
) -> PromptCharacteristics:
    """1단계 LLM: PromptCharacteristics만 구조화 추출."""
    from app.domain.langgraph.prompts import load_prompt, render_prompt

    llm = get_llm()
    structured_llm = llm.with_structured_output(PromptCharacteristics)

    yaml_meta = load_prompt("eval_intent_analysis")
    priority_note = (
        yaml_meta.get("first_turn_priority_note", "") if is_first_turn else ""
    )
    xml_hint = (
        yaml_meta.get("xml_tag_hint", "") if has_role_content else ""
    )

    system_prompt = render_prompt(
        "eval_prompt_characteristics",
        priority_note=priority_note,
        xml_hint=xml_hint,
    )
    user_block = f"사용자: {human_message}\n\nAI 응답: {ai_message}"
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_block),
    ]

    raw_response = await llm.ainvoke(messages)
    tokens = extract_token_usage(raw_response)
    if tokens:
        accumulate_tokens(state, tokens, token_type="eval")

    try:
        parsed = await parse_structured_output_async(
            raw_response=raw_response,
            model_class=PromptCharacteristics,
            fallback_llm=structured_llm,
            formatted_messages=messages,
        )
    except Exception as e:
        logger.error(
            f"[4.0 Intent Analysis] 특성 추출 파싱 실패: {e}",
            exc_info=True,
        )
        parsed = await structured_llm.ainvoke(messages)

    return parsed


async def _disambiguate_intent_llm(
    state: EvalTurnState,
    human_message: str,
    ai_message: str,
    chars: PromptCharacteristics,
    is_first_turn: bool,
) -> IntentClassification:
    """규칙으로 확정 못 할 때만: 가벼운 2차 LLM (의도만)."""
    from app.domain.langgraph.prompts import render_prompt

    llm = get_llm()
    structured_llm = llm.with_structured_output(IntentClassification)

    first_turn_note = (
        "**첫 턴**: FOLLOW_UP은 선택할 수 없습니다.\n"
        if is_first_turn
        else ""
    )
    system_prompt = render_prompt(
        "eval_intent_disambiguation",
        characteristics_block=_format_characteristics_block(chars),
        user_block=f"사용자: {human_message}\n\nAI 응답: {ai_message}",
        first_turn_note=first_turn_note,
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="위 정보로 intent_types 하나만 골라 출력하세요."),
    ]

    raw_response = await llm.ainvoke(messages)
    tokens = extract_token_usage(raw_response)
    if tokens:
        accumulate_tokens(state, tokens, token_type="eval")

    try:
        return await parse_structured_output_async(
            raw_response=raw_response,
            model_class=IntentClassification,
            fallback_llm=structured_llm,
            formatted_messages=messages,
        )
    except Exception as e:
        logger.error(
            f"[4.0 Intent Analysis] 의도 폴백 파싱 실패: {e}",
            exc_info=True,
        )
        return await structured_llm.ainvoke(messages)


async def intent_analysis(state: EvalTurnState) -> Dict[str, Any]:
    """
    4.0: Intent Analysis (투스텝)

    1단계: 구조화 출력으로 PromptCharacteristics만 추출 (의도 라벨 없음).
    2단계: 규칙으로 UnifiedIntentType 확정; 애매하면 가벼운 LLM 폴백.
    """
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.0 Intent Analysis] 진입 - session_id: {session_id}, turn: {turn}")

    human_message = state.get("human_message", "")
    ai_message = state.get("ai_message", "")

    is_first_turn = turn == 1
    has_role_content = has_role_content_tags(human_message)

    try:
        chars = await _extract_prompt_characteristics(
            state,
            human_message,
            ai_message,
            is_first_turn=is_first_turn,
            has_role_content=has_role_content,
        )

        logger.info(
            f"[4.0 Intent Analysis] 1단계 특성 - "
            f"code={chars.has_code_snippet}, err={chars.is_error_reported}, "
            f"concept={chars.is_asking_for_concept}, new_code={chars.is_requesting_new_code}"
        )

        resolved = _resolve_intent_from_characteristics(human_message, chars)
        if resolved is not None:
            unified_enum, confidence, reason = resolved
            reasoning = reason
        else:
            logger.info("[4.0 Intent Analysis] 규칙 미매칭 → 2단계 폴백 LLM")
            parsed = await _disambiguate_intent_llm(
                state,
                human_message,
                ai_message,
                chars,
                is_first_turn=is_first_turn,
            )
            if not parsed.intent_types:
                unified_enum = UnifiedIntentType.DEBUGGING
                confidence = 0.5
                reasoning = "fallback_llm_empty"
            else:
                unified_enum = parsed.intent_types[0]
                confidence = parsed.confidence
                reasoning = parsed.reasoning or "fallback_llm"

        unified = unified_enum.value
        intent_values = [unified]

        if is_first_turn and unified == UnifiedIntentType.FOLLOW_UP.value:
            logger.warning(
                f"[4.0 Intent Analysis] 첫 턴 FOLLOW_UP → 재분류. 특성: {chars.model_dump()}"
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
            f"의도: {intent_values}, unified_intent: {unified}, 신뢰도: {confidence:.2f}, 경로: {reasoning}"
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
