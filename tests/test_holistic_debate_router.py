"""N7→N8 라우팅: 비가드레일 프롬프트 턴 없으면 N8 스킵 노드."""

from app.domain.langgraph.nodes.eval.eval_turn_targets import (
    eval_target_turn_numbers,
    has_non_guardrail_prompt_evaluations,
    has_prompt_turn_evaluations,
    should_run_holistic_debate,
)
from app.domain.langgraph.nodes.eval.holistic_debate_skip import (
    HOLISTIC_DEBATE_SKIP_MESSAGE,
    build_skipped_holistic_debate_result,
)
from app.domain.langgraph.nodes.eval.routers import holistic_debate_router


def test_eval_target_turn_numbers_matches_n4():
    assert eval_target_turn_numbers(0) == []
    assert eval_target_turn_numbers(1) == []
    assert eval_target_turn_numbers(5) == [1, 2, 3, 4]


def test_should_run_holistic_debate_when_non_guardrail_turn_present():
    state = {
        "turn_scores": {
            "1": {"turn_score": 0.0},
            "2": {"turn_score": 80.0},
        },
        "guardrail_flag_turns": [1],
    }
    assert has_prompt_turn_evaluations(state) is True
    assert has_non_guardrail_prompt_evaluations(state) is True
    assert should_run_holistic_debate(state) is True
    assert holistic_debate_router(state) == "holistic_debate"


def test_should_skip_holistic_debate_when_only_guardrail_turns():
    state = {
        "current_turn": 3,
        "turn_scores": {
            "1": {"turn_score": 0.0},
            "2": {"turn_score": 0.0},
        },
        "guardrail_flag_turns": [1, 2],
    }
    assert eval_target_turn_numbers(3) == [1, 2]
    assert has_prompt_turn_evaluations(state) is True
    assert has_non_guardrail_prompt_evaluations(state) is False
    assert should_run_holistic_debate(state) is False
    assert holistic_debate_router(state) == "holistic_debate_skipped"


def test_should_skip_holistic_debate_when_no_turn_scores():
    state = {"current_turn": 3, "turn_scores": {}}
    assert should_run_holistic_debate(state) is False
    assert holistic_debate_router(state) == "holistic_debate_skipped"


def test_build_skipped_holistic_debate_result_fills_placeholders():
    result = build_skipped_holistic_debate_result()
    assert result["holistic_flow_score"] == 0.0
    assert result["r4_context_maintenance_score"] == 0.0
    assert HOLISTIC_DEBATE_SKIP_MESSAGE in result["holistic_flow_analysis"]
    assert len(result["debate_log"]) == 7
    assert result["debate_log"][-1]["agent"] == "verdict"
    assert result["debate_log"][-1]["holistic_flow_score"] == 0.0
    for op in result["debate_initial_opinions"]:
        assert op["stance"] == HOLISTIC_DEBATE_SKIP_MESSAGE
    for op in result["debate_rebuttals"]:
        assert op["prompt_quality_assessment"] == HOLISTIC_DEBATE_SKIP_MESSAGE
