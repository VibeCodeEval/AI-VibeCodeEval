"""
Hybrid 평가 모델 + Legacy Fallback 검증

- Tier 1 (New): likert_score / final_score → 환산표 적용
- Tier 2 (Legacy): score / average 그대로 사용
- Tier 3 (Fallback): rubrics만 있으면 Legacy Adapter로 계산
"""
import pytest

from app.domain.langgraph.nodes.eval_turn.aggregation import aggregate_turn_log
from app.domain.langgraph.nodes.eval_turn.grading import (
    EvaluationResult,
    likert_to_final,
    evaluation_result_from_payload,
)
from app.domain.langgraph.nodes.eval_turn.weights import legacy_turn_score_from_rubrics


@pytest.mark.asyncio
async def test_legacy_input_score_85_returns_85():
    """Legacy 입력: score 85만 있으면 턴 점수 85."""
    state = {
        "session_id": "test",
        "turn": 1,
        "intent_types": ["generation"],
        "unified_intent": "CREATION",
        "is_guardrail_failed": False,
        "is_phase2_first_turn": False,
        "generation_eval": {
            "score": 85,
            "average": 85,
            "rubrics": [],
            "final_reasoning": "legacy",
        },
    }
    result = await aggregate_turn_log(state)
    assert result["turn_score"] == 85.0


@pytest.mark.asyncio
async def test_new_input_likert_4_returns_90():
    """New 입력: likert_score 4면 환산표 적용 → 90."""
    state = {
        "session_id": "test",
        "turn": 1,
        "intent_types": ["generation"],
        "unified_intent": "CREATION",
        "is_guardrail_failed": False,
        "is_phase2_first_turn": False,
        "generation_eval": {
            "likert_score": 4,
            "final_reasoning": "good",
        },
    }
    result = await aggregate_turn_log(state)
    assert result["turn_score"] == 90.0


@pytest.mark.asyncio
async def test_tier3_rubrics_only_uses_legacy_adapter():
    """Tier 3: score/likert 없고 rubrics만 있으면 Legacy Adapter로 계산."""
    # 의도별 가중치로 합산되므로, clarity 100만 넣으면 FOLLOW_UP이면 context 0.8 -> 80 근처
    state = {
        "session_id": "test",
        "turn": 1,
        "intent_types": ["follow_up"],
        "unified_intent": "FOLLOW_UP",
        "is_guardrail_failed": False,
        "is_phase2_first_turn": False,
        "follow_up_eval": {
            "rubrics": [
                {"criterion": "문맥 (Context)", "score": 100, "reasoning": "ok"},
            ],
            "final_reasoning": "context good",
        },
    }
    result = await aggregate_turn_log(state)
    # FOLLOW_UP weights: context 0.8 -> 100 * 0.8 = 80
    assert result["turn_score"] == 80.0


def test_likert_to_final_mapping():
    """환산표: 5→100, 4→90, 3→80, 2→60, 1→0."""
    assert likert_to_final(5) == 100
    assert likert_to_final(4) == 90
    assert likert_to_final(3) == 80
    assert likert_to_final(2) == 60
    assert likert_to_final(1) == 0


def test_evaluation_result_likert_optional_legacy_score():
    """EvaluationResult: likert_score Optional, Legacy는 final_score만 채워도 됨."""
    r = EvaluationResult.from_legacy_score(85, feedback_summary="legacy")
    assert r.likert_score is None
    assert r.final_score == 85


def test_evaluation_result_from_payload_always_has_final_score():
    """evaluation_result_from_payload: 출력은 항상 final_score 채움 (Legacy score로 가능)."""
    legacy = evaluation_result_from_payload({"score": 85, "final_reasoning": "x"})
    assert legacy["final_score"] == 85
    new_style = evaluation_result_from_payload({"likert_score": 4})
    assert new_style["final_score"] == 90
