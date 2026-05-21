"""eval_intent_disambiguation v2.2 서버 정책 보정."""

from app.domain.langgraph.nodes.eval_turn.analysis import (
    _apply_intent_policy_overrides,
    _asks_for_deliverable_code,
    _user_request_prefix,
)
from app.domain.langgraph.states import UnifiedIntentType


def test_p6_turn1_prefix_is_exploration_not_code_create():
    msg = (
        "이 문제에 대해서 읽어본 뒤에\n"
        "문제를 기능별로 분해해봐 그리고 엣지케이스를 고려해서\n"
        "기능별 코드 작성시 주의사항\n\n"
        "# Problem Title\n\nlong spec..."
    )
    prefix = _user_request_prefix(msg)
    assert "분해" in prefix
    assert not _asks_for_deliverable_code(prefix)

    intent, ur, note = _apply_intent_policy_overrides(
        msg,
        is_first_turn=True,
        unified_enum=UnifiedIntentType.CREATION,
        user_request_in_turn="CODE_CREATE",
    )
    assert intent == UnifiedIntentType.EXPLORATION
    assert ur == "EXPLAIN"
    assert note == "policy_exploration_over_code_meta"


def test_deliverable_code_after_prior_turn_is_refinement():
    msg = "방금 써준 로드맵 토대로 베이스 코드 작성해줘"
    intent, ur, note = _apply_intent_policy_overrides(
        msg,
        is_first_turn=False,
        unified_enum=UnifiedIntentType.CREATION,
        user_request_in_turn="CODE_CREATE",
    )
    assert intent == UnifiedIntentType.REFINEMENT
    assert ur == "CODE_CREATE"
    assert note == "policy_refinement_prior_output"
