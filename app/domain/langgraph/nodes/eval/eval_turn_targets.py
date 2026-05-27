"""N4 Eval Turn Guard와 동일한 평가 대상 턴 판별 (N8 라우팅 등 공유)."""

from __future__ import annotations

from typing import Any, List, Mapping, Optional

from app.domain.langgraph.utils.guardrail_turns import get_guardrail_flag_turns


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


def _turn_key_to_int(key: Any) -> Optional[int]:
    try:
        return int(key)
    except (TypeError, ValueError):
        return None


def _is_guardrail_turn_score(
    turn: int, entry: Any, state: Mapping[str, Any]
) -> bool:
    if turn in set(get_guardrail_flag_turns(state)):
        return True
    if isinstance(entry, dict) and entry.get("is_guardrail_failed"):
        return True
    return False


def has_prompt_turn_evaluations(state: Mapping[str, Any]) -> bool:
    """
    N4가 저장한 turn_scores가 1건 이상인지 (가드레일 0점 포함).

    N8 실행 여부는 has_non_guardrail_prompt_evaluations 를 사용한다.
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


def has_non_guardrail_prompt_evaluations(state: Mapping[str, Any]) -> bool:
    """
    가드레일 턴을 제외한 프롬프트 턴 평가가 1건 이상인지.

    N8(홀리스틱 토론)은 이 조건을 만족할 때만 LLM 토론을 실행한다.
    """
    turn_scores = state.get("turn_scores")
    if not isinstance(turn_scores, dict) or not turn_scores:
        return False
    for key, entry in turn_scores.items():
        turn = _turn_key_to_int(key)
        if turn is None:
            continue
        if _is_guardrail_turn_score(turn, entry, state):
            continue
        if isinstance(entry, dict) and entry.get("turn_score") is not None:
            return True
        if isinstance(entry, (int, float)):
            return True
    return False


def should_run_holistic_debate(state: Mapping[str, Any]) -> bool:
    """비가드레일 프롬프트 턴이 1건 이상일 때만 N8 LLM 토론 실행."""
    return has_non_guardrail_prompt_evaluations(state)
