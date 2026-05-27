"""
eval_turn 분할 프롬프트 조합.

런타임: evaluators.prepare_evaluation_input_internal → render_eval_turn_prompt
파일: prompts/eval_turn/{base_context,common_scale,gates/*,rubrics/*,intent_matrix,cot_output}
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.domain.langgraph.prompts import render_prompt

logger = logging.getLogger(__name__)

# intent_router UNIFIED_TO_NODE와 동일 축
RUBRIC_PARTS_BY_UNIFIED_INTENT: Dict[str, List[str]] = {
    "CREATION": ["r1", "r2", "r3"],
    "SETTING": ["r2", "r3"],
    "REFINEMENT": ["r1", "r2", "r3", "r4"],
    "DEBUGGING": ["r1", "r2", "r4"],
    "EXPLORATION": ["r1", "r2"],
    "FOLLOW_UP": ["r4"],
    "VALIDATION": ["r1", "r2", "r4"],
}

GATE_ORDER = (
    "mixed_spec_code",
    "spec_turn",
    "request_only",
    "follow_up_ref",
    "default",
)


def _has_prior_dialogue(state: Dict[str, Any]) -> bool:
    raw = (state.get("previous_turn_dialogue") or "").strip()
    return bool(raw) and "이전 턴 대화 없음" not in raw


def resolve_turn_archetype_gate(state: Dict[str, Any]) -> str:
    """
    턴 분해(Intent) 결과로 게이트 YAML 선택.

    우선순위: mixed_spec_code > spec_turn > request_only > follow_up_ref > default
    """
    problem = (state.get("problem_in_turn") or "NONE").strip()
    request = (state.get("user_request_in_turn") or "NONE").strip()
    has_spec = problem in ("FULL_SPEC", "PARTIAL")
    mixed = has_spec and request == "CODE_CREATE"
    has_prior = _has_prior_dialogue(state)

    if mixed:
        return "mixed_spec_code"
    if has_spec:
        return "spec_turn"
    if request not in ("NONE", "") and problem == "NONE":
        if has_prior:
            return "follow_up_ref"
        if request == "CODE_CREATE":
            return "request_only"
        return "follow_up_ref"
    if has_prior:
        return "follow_up_ref"
    return "default"


def resolve_unified_intent_for_prompt(state: Dict[str, Any]) -> str:
    unified = (state.get("unified_intent") or "").upper().strip()
    if unified:
        return unified
    types = state.get("intent_types") or []
    if types:
        return str(types[0]).upper().strip()
    return "CREATION"


def rubric_parts_for_state(state: Dict[str, Any]) -> List[str]:
    intent = resolve_unified_intent_for_prompt(state)
    return list(RUBRIC_PARTS_BY_UNIFIED_INTENT.get(intent, RUBRIC_PARTS_BY_UNIFIED_INTENT["CREATION"]))


def render_eval_turn_prompt(state: Dict[str, Any], **variables) -> str:
    """
    분할 YAML을 순서대로 렌더링해 하나의 system 프롬프트로 합칩니다.
    """
    gate = resolve_turn_archetype_gate(state)
    rubrics = rubric_parts_for_state(state)
    ctx = dict(variables)

    parts: List[str] = [
        render_prompt("eval_turn/base_context", **ctx),
        render_prompt("eval_turn/common_scale", **ctx),
        render_prompt(f"eval_turn/gates/{gate}", **ctx),
    ]
    for key in rubrics:
        parts.append(render_prompt(f"eval_turn/rubrics/{key}", **ctx))
    parts.append(render_prompt("eval_turn/intent_matrix", **ctx))
    parts.append(render_prompt("eval_turn/cot_output", **ctx))

    logger.debug(
        "[eval_turn compose] gate=%s rubrics=%s intent=%s",
        gate,
        rubrics,
        resolve_unified_intent_for_prompt(state),
    )
    return "\n".join(parts)


def eval_turn_compose_metadata(state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """로그·디버그용: 이번 턴에 붙은 프롬프트 조각 목록."""
    gate = resolve_turn_archetype_gate(state or {})
    rubrics = rubric_parts_for_state(state or {})
    return {
        "version": "3.5.0",
        "gate": gate,
        "rubrics": rubrics,
        "unified_intent": resolve_unified_intent_for_prompt(state or {}),
        "parts": [
            "eval_turn/base_context",
            "eval_turn/common_scale",
            f"eval_turn/gates/{gate}",
            *[f"eval_turn/rubrics/{r}" for r in rubrics],
            "eval_turn/intent_matrix",
            "eval_turn/cot_output",
        ],
    }
