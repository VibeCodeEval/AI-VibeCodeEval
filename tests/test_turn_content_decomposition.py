"""턴 내용 분해(문제 vs 요청) — intent_analysis·eval 입력·스펙 가드레일."""

import pytest

from app.domain.langgraph.nodes.eval_turn.analysis import intent_analysis
from app.domain.langgraph.nodes.eval_turn.routers import intent_router
from app.domain.langgraph.nodes.eval_turn.spec_paste_guard import (
    SPEC_PASTE_GUARDRAIL_SCORE,
    eval_spec_paste_guard,
    is_spec_paste_only_turn,
)
from app.domain.langgraph.nodes.eval_turn.evaluators import (
    _build_turn_content_section,
    prepare_evaluation_input_internal,
)
from app.domain.langgraph.states import IntentTurnLLMOutput, UnifiedIntentType


async def test_intent_analysis_returns_turn_content_fields(monkeypatch):
    fake = IntentTurnLLMOutput(
        predicted_intent=UnifiedIntentType.CREATION.value,
        intent_cot="스펙 제시만 해당.",
        problem_in_turn="FULL_SPEC",
        user_request_in_turn="NONE",
        request_one_liner="사용자는 문제에 대한 내용을 제시했습니다.",
        carry_forward="문제 스펙 제시됨(상세). 사용자 요청: 없음",
    )

    async def fake_llm(*_a, **_k):
        return fake

    monkeypatch.setattr(
        "app.domain.langgraph.nodes.eval_turn.analysis._classify_intent_single_llm",
        lambda *_a, **_k: fake_llm(),
    )

    out = await intent_analysis(
        {
            "session_id": "session_1",
            "turn": 1,
            "human_message": "# 문제 본문…",
            "previous_turns_summary": "(제공 없음)",
        }
    )
    assert out["problem_in_turn"] == "FULL_SPEC"
    assert out["user_request_in_turn"] == "NONE"
    assert "문제" in (out.get("request_one_liner") or "")
    assert out.get("carry_forward")


def test_build_turn_content_section_mixed_turn():
    section = _build_turn_content_section(
        {
            "problem_in_turn": "FULL_SPEC",
            "user_request_in_turn": "CODE_CREATE",
            "request_one_liner": "사용자는 문제에 대한 내용을 제시했고, 코드 작성을 요청했습니다.",
            "carry_forward": "문제 스펙 제시됨. 사용자 요청: 코드 작성",
        }
    )
    assert "FULL_SPEC" in section
    assert "CODE_CREATE" in section
    assert "스펙 상세성" in section or "요청 명확성" in section


def test_is_spec_paste_only_turn():
    assert is_spec_paste_only_turn(
        {"problem_in_turn": "FULL_SPEC", "user_request_in_turn": "NONE"}
    )
    assert not is_spec_paste_only_turn(
        {"problem_in_turn": "FULL_SPEC", "user_request_in_turn": "CODE_CREATE"}
    )


def test_intent_router_routes_spec_paste_guard():
    nodes = intent_router(
        {
            "session_id": "s",
            "turn": 1,
            "problem_in_turn": "FULL_SPEC",
            "user_request_in_turn": "NONE",
            "unified_intent": "CREATION",
        }
    )
    assert nodes == ["eval_spec_paste_guard"]


@pytest.mark.asyncio
async def test_eval_spec_paste_guard_fixed_score():
    out = await eval_spec_paste_guard(
        {
            "session_id": "s",
            "turn": 1,
            "request_one_liner": "사용자는 문제에 대한 내용을 제시했습니다.",
        }
    )
    assert out["spec_paste_guardrail_applied"] is True
    assert out["turn_score"] == SPEC_PASTE_GUARDRAIL_SCORE
    assert out["generation_eval"]["final_score"] == SPEC_PASTE_GUARDRAIL_SCORE


def test_prepare_evaluation_input_includes_turn_content_section():
    state = {
        "human_message": "방금 그 문제 코드 짜줘",
        "ai_message": "code",
        "previous_turns_summary": "[Turn 1] 사용자: 문제 제시",
        "problem_in_turn": "NONE",
        "user_request_in_turn": "CODE_CREATE",
        "request_one_liner": "앞서 제시한 문제에 대해 코드 작성을 요청했습니다.",
    }
    prepared = prepare_evaluation_input_internal(
        {"state": state}, "CREATION", "criteria"
    )
    sp = prepared["system_prompt"]
    assert "앞서 제시한 문제에 대해 코드 작성을 요청했습니다." in sp
    assert "[필독]" in sp or "필독" in sp
    assert "먼저 읽고" in sp or "먼저 읽" in sp
    assert "Context" in sp or "보정 금지" in sp
