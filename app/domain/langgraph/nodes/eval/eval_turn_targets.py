"""N4 Eval Turn Guard와 동일한 평가 대상 턴 판별 (N8 라우팅 등 공유)."""

from __future__ import annotations

from typing import Any, List, Mapping


def eval_target_turn_numbers(current_turn: Any) -> List[int]:
    """
    N4 eval_turn_submit_guard와 동일: 제출 턴(current_turn) 제외, 1 ~ current_turn-1.
    """
    try:
        ct = int(current_turn or 0)
    except (TypeError, ValueError):
        ct = 0
    if ct <= 1:
        return []
    return list(range(1, ct))


def has_prompt_turn_evaluations(state: Mapping[str, Any]) -> bool:
    """
    N4가 실제로 저장한 턴 프롬프트 평가가 1건 이상인지.

    turn_scores는 Redis turn_logs의 prompt_evaluation_details.score 기준으로
    N4 종료 시 채워진다 (SAVE 턴·메시지 추출 실패 턴은 포함되지 않음).
    """
    turn_scores = state.get("turn_scores")
    if not isinstance(turn_scores, dict) or not turn_scores:
        return False
    for entry in turn_scores.values():
        if isinstance(entry, dict) and entry.get("turn_score") is not None:
            return True
        if isinstance(entry, (int, float)):
            return True
    return False


def should_run_holistic_debate(state: Mapping[str, Any]) -> bool:
    """프롬프트 턴 평가가 있을 때만 N8(다중 에이전트 토론) 실행."""
    return has_prompt_turn_evaluations(state)
