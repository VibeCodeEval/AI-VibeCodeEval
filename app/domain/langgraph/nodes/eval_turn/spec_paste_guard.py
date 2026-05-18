"""FULL_SPEC + 요청 없음 턴: eval LLM 생략, 고정 30점."""

import logging
from typing import Any, Dict

from app.domain.langgraph.states import EvalTurnState

logger = logging.getLogger(__name__)

SPEC_PASTE_GUARDRAIL_SCORE = 30


def is_spec_paste_only_turn(state: EvalTurnState) -> bool:
    """문제 스펙만 붙여넣고 사용자 행동 요청이 없는 턴."""
    problem = (state.get("problem_in_turn") or "").strip().upper()
    request = (state.get("user_request_in_turn") or "").strip().upper()
    return problem == "FULL_SPEC" and request == "NONE"


async def eval_spec_paste_guard(state: EvalTurnState) -> Dict[str, Any]:
    """
    스펙 붙여넣기만(FULL_SPEC + NONE) → 루브릭 LLM 생략, turn_score 30 고정.
    """
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    one_liner = (state.get("request_one_liner") or "").strip()

    reasoning = (
        "[가드레일] problem_in_turn=FULL_SPEC, user_request_in_turn=NONE — "
        "문제 스펙만 제시하고 코드·수정·설명 등 행동 요청이 없어 "
        f"고정 {SPEC_PASTE_GUARDRAIL_SCORE}점 처리 (eval_turn LLM 미호출)."
    )
    if one_liner:
        reasoning += f" 요약: {one_liner}"

    logger.info(
        "[4.0 Spec Paste Guard] session_id=%s turn=%s score=%s",
        session_id,
        turn,
        SPEC_PASTE_GUARDRAIL_SCORE,
    )

    stub_eval = {
        "final_score": SPEC_PASTE_GUARDRAIL_SCORE,
        "likert_score": 2,
        "rubrics": [],
        "final_reasoning": reasoning,
        "scoring_cot": {
            "R1": "스펙만 제시 — 스펙 상세성·요청 명확성 루브릭 LLM 평가 생략(가드레일).",
            "R2": reasoning,
        },
        "rubric_breakdown": {},
        "applied_rubrics": [],
    }

    return {
        "spec_paste_guardrail_applied": True,
        "turn_score": float(SPEC_PASTE_GUARDRAIL_SCORE),
        "generation_eval": stub_eval,
    }
