"""N7→N8 라우팅: 프롬프트 턴 평가 없으면 N9 직행."""

from app.domain.langgraph.nodes.eval.eval_turn_targets import (
    eval_target_turn_numbers,
    has_prompt_turn_evaluations,
    should_run_holistic_debate,
)
from app.domain.langgraph.nodes.eval.routers import holistic_debate_router


def test_eval_target_turn_numbers_matches_n4():
    assert eval_target_turn_numbers(0) == []
    assert eval_target_turn_numbers(1) == []
    assert eval_target_turn_numbers(5) == [1, 2, 3, 4]


def test_should_run_holistic_debate_when_turn_scores_present():
    state = {"turn_scores": {"1": {"turn_score": 80.0}}}
    assert has_prompt_turn_evaluations(state) is True
    assert should_run_holistic_debate(state) is True
    assert holistic_debate_router(state) == "holistic_debate"


def test_should_skip_holistic_debate_when_no_turn_scores():
    state = {"current_turn": 3, "turn_scores": {}}
    assert eval_target_turn_numbers(3) == [1, 2]
    assert should_run_holistic_debate(state) is False
    assert holistic_debate_router(state) == "aggregate_final_scores"
