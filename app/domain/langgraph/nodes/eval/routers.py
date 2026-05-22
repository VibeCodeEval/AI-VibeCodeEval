"""제출 평가 파이프라인 조건부 라우팅."""

import logging

from app.domain.langgraph.nodes.eval.eval_turn_targets import (
    eval_target_turn_numbers,
    should_run_holistic_debate,
)
from app.domain.langgraph.states import MainGraphState

logger = logging.getLogger(__name__)


def holistic_debate_router(state: MainGraphState) -> str:
    """
    N7 이후: 프롬프트 턴 평가(N4 turn_scores)가 없으면 N8 생략 → N9 직행.
    """
    if should_run_holistic_debate(state):
        return "holistic_debate"

    targets = eval_target_turn_numbers(state.get("current_turn", 0))
    logger.info(
        "[Eval Router] N8 생략 — 프롬프트 턴 평가 없음 "
        "(N4 평가 대상 턴=%s, turn_scores 비어 있음) → N9",
        targets,
    )
    return "aggregate_final_scores"
