import logging
import re
from typing import Any, Dict, Tuple

from langchain_core.messages import HumanMessage, SystemMessage

from app.domain.langgraph.nodes.eval_turn.utils import get_llm_intent
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


_CODE_META_RE = re.compile(
    r"코드\s*작성\s*시|작성\s*시\s*주의|작성할\s*때|짤\s*때",
    re.IGNORECASE,
)
_DELIVERABLE_CODE_RE = re.compile(
    r"코드\s*짜|구현\s*해|베이스\s*코드\s*(?:작성|달라|줘|만들)|스켈레톤|풀\s*코드",
    re.IGNORECASE,
)
_EXPLORATION_RE = re.compile(
    r"분해|엣지\s*(?:케이스|포인트)|주의\s*사항|로드맵|Pseudo\s*Code|의사\s*코드",
    re.IGNORECASE,
)
_PRIOR_REF_RE = re.compile(
    r"방금|이전|토대로|써준|작성한|너가\s*방금|위\s*스크립트|앞서",
    re.IGNORECASE,
)
_SPEC_WALL_MARKERS = ("\n# ", "\n## ", "\n```", "<Content>", "<Role>")


def _user_request_prefix(human_message: str, max_len: int = 800) -> str:
    t = (human_message or "").strip()
    if not t:
        return ""
    for sep in _SPEC_WALL_MARKERS:
        idx = t.find(sep)
        if idx > 80:
            return t[:idx][:max_len]
    return t[:max_len]


def _asks_for_deliverable_code(prefix: str) -> bool:
    if not prefix:
        return False
    if _CODE_META_RE.search(prefix) and not _DELIVERABLE_CODE_RE.search(prefix):
        return False
    return bool(_DELIVERABLE_CODE_RE.search(prefix))


def _apply_intent_policy_overrides(
    human_message: str,
    is_first_turn: bool,
    unified_enum: UnifiedIntentType,
    user_request_in_turn: str,
) -> Tuple[UnifiedIntentType, str, str]:
    """eval_intent_disambiguation v2.2 — 분해·엣지·주의사항 vs CREATION, 후속 REFINEMENT."""
    prefix = _user_request_prefix(human_message)
    exploration = bool(_EXPLORATION_RE.search(prefix))
    deliverable = _asks_for_deliverable_code(prefix)
    prior_ref = bool(_PRIOR_REF_RE.search(prefix)) and not is_first_turn
    ur = (user_request_in_turn or "NONE").strip().upper()
    note = ""

    if exploration and not deliverable:
        if unified_enum in (
            UnifiedIntentType.CREATION,
            UnifiedIntentType.FOLLOW_UP,
        ):
            unified_enum = UnifiedIntentType.EXPLORATION
            note = "policy_exploration_over_code_meta"
        if ur == "CODE_CREATE":
            ur = "EXPLAIN"

    elif prior_ref and deliverable and unified_enum == UnifiedIntentType.CREATION:
        unified_enum = UnifiedIntentType.REFINEMENT
        note = "policy_refinement_prior_output"

    return unified_enum, ur, note


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

    llm = get_llm_intent()
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
            content=(
                "위 지시에 따라 predicted_intent, intent_cot, problem_in_turn, "
                "user_request_in_turn, request_one_liner, carry_forward를 담은 JSON을 출력하세요."
            )
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
        problem_in_turn = (parsed.problem_in_turn or "NONE").strip().upper()
        user_request_in_turn = (parsed.user_request_in_turn or "NONE").strip().upper()

        unified_enum, user_request_in_turn, policy_note = _apply_intent_policy_overrides(
            human_message,
            is_first_turn,
            unified_enum,
            user_request_in_turn,
        )

        confidence = 0.9
        intent_cot = (parsed.intent_cot or "").strip()
        reasoning = f"{path};{intent_cot}"
        if policy_note:
            reasoning = f"{reasoning};{policy_note}"
            intent_cot = (
                f"{intent_cot}\n[시스템 보정] eval_intent v2.2 정책({policy_note})."
                if intent_cot
                else f"[시스템 보정] eval_intent v2.2 정책({policy_note})."
            )
            confidence = min(confidence, 0.88)

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
                intent_cot = (
                    f"{intent_cot}\n[시스템 보정] 첫 턴 FOLLOW_UP 불가 → SETTING으로 라우팅."
                    if intent_cot
                    else "[시스템 보정] 첫 턴 FOLLOW_UP 불가 → SETTING으로 라우팅."
                )
            else:
                unified = UnifiedIntentType.CREATION.value
                intent_values = [unified]
                reasoning = f"{reasoning};first_turn_override_creation"
                intent_cot = (
                    f"{intent_cot}\n[시스템 보정] 첫 턴 FOLLOW_UP 불가 → CREATION으로 라우팅."
                    if intent_cot
                    else "[시스템 보정] 첫 턴 FOLLOW_UP 불가 → CREATION으로 라우팅."
                )
            confidence = min(confidence, 0.85)

        logger.info(
            f"[4.0 Intent Analysis] 완료 - session_id: {session_id}, turn: {turn}, "
            f"의도: {intent_values}, unified_intent: {unified}, 신뢰도: {confidence:.2f}, 경로: {reasoning[:200]}"
        )

        request_one_liner = (parsed.request_one_liner or "").strip()
        carry_forward = (parsed.carry_forward or "").strip() or request_one_liner

        result: Dict[str, Any] = {
            "intent_types": intent_values,
            "intent_confidence": confidence,
            "unified_intent": unified,
            "intent_cot": intent_cot or None,
            "problem_in_turn": problem_in_turn,
            "user_request_in_turn": user_request_in_turn,
            "request_one_liner": request_one_liner or None,
            "carry_forward": carry_forward or None,
        }

        if "eval_tokens" in state:
            result["eval_tokens"] = state["eval_tokens"]

        return result

    except Exception as e:
        logger.error(
            f"[4.0 Intent Analysis] 오류 - session_id: {session_id}, turn: {turn}, error: {str(e)}",
            exc_info=True,
        )
        preview = (human_message[:80] + "…") if len(human_message) > 80 else human_message
        return {
            "intent_types": [UnifiedIntentType.DEBUGGING.value],
            "intent_confidence": 0.0,
            "unified_intent": UnifiedIntentType.DEBUGGING.value,
            "intent_cot": None,
            "problem_in_turn": "NONE",
            "user_request_in_turn": "OTHER",
            "request_one_liner": preview or None,
            "carry_forward": preview or None,
        }
