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
    N7 이후: 비가드레일 프롬프트 턴이 있으면 N8 LLM 토론,
    없으면 N8 스킵 노드(0점·플레이스홀더 debate_log) → N9.
    """
    if should_run_holistic_debate(state):
        return "holistic_debate"

    targets = eval_target_turn_numbers(state.get("current_turn", 0))
    logger.info(
        "[Eval Router] N8 스킵 — 비가드레일 프롬프트 턴 없음 "
        "(N4 평가 대상 턴=%s) → holistic_debate_skipped",
        targets,
    )
    return "holistic_debate_skipped"
