"""intent_cot State 반환 및 prompt_evaluations details 필드."""

from app.domain.langgraph.nodes.eval_turn.analysis import intent_analysis
from app.domain.langgraph.states import UnifiedIntentType


async def test_intent_analysis_returns_intent_cot(monkeypatch):
    class FakeParsed:
        predicted_intent = UnifiedIntentType.EXPLORATION.value
        intent_cot = "사용자가 문제 인지 여부를 묻고 있어 EXPLORATION에 해당합니다."
        problem_in_turn = "NONE"
        user_request_in_turn = "EXPLAIN"
        request_one_liner = "사용자는 문제 인지 여부를 질문했습니다."
        carry_forward = "사용자 요청: 설명"

    async def fake_llm(*_a, **_k):
        return FakeParsed()

    monkeypatch.setattr(
        "app.domain.langgraph.nodes.eval_turn.analysis._classify_intent_single_llm",
        lambda *_a, **_k: fake_llm(),
    )

    state = {
        "session_id": "session_1",
        "turn": 2,
        "human_message": "문제 알고 있어?",
        "previous_turns_summary": "턴1 요약",
    }
    out = await intent_analysis(state)
    assert out["unified_intent"] == UnifiedIntentType.EXPLORATION.value
    assert "EXPLORATION" in (out.get("intent_cot") or "")
