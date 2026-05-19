"""가드레일 턴 등록·N4/N8 필터 단위 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.langgraph.nodes.chat.n2_intent_analyzer import (
    IntentAnalysisResult,
    _merge_guardrail_turn_state,
    process_output,
)
from app.domain.langgraph.utils.guardrail_turns import (
    GUARDRAIL_USER_MESSAGE_PREFIX,
    api_turn_to_conversation_turn,
    build_guardrail_meta_patch,
    filter_turn_logs_for_debate,
    format_guardrail_user_message,
    is_guardrail_blocked_response_text,
    is_guardrail_turn,
    register_guardrail_turn,
    resolve_conversation_turn_for_guardrail,
)


def test_register_guardrail_turn_dedup():
    state = {"guardrail_flag_turns": [1], "guardrail_turn_reasons": {"1": "OFF_TOPIC"}}
    patch_out = register_guardrail_turn(state, turn=1, block_reason="OFF_TOPIC")
    assert patch_out["guardrail_flag_turns"] == [1]


def test_register_guardrail_turn_appends():
    state = {"current_turn": 2, "guardrail_flag_turns": [], "guardrail_turn_reasons": {}}
    patch_out = register_guardrail_turn(state, block_reason="INAPPROPRIATE")
    assert patch_out["guardrail_flag_turns"] == [2]
    assert patch_out["guardrail_turn_reasons"]["2"] == "INAPPROPRIATE"


def test_format_guardrail_user_message_prefix():
    msg = format_guardrail_user_message("코딩과 무관한 요청입니다.")
    assert msg.startswith(GUARDRAIL_USER_MESSAGE_PREFIX)


def test_is_guardrail_blocked_response_text_unified_and_legacy():
    assert is_guardrail_blocked_response_text(
        "해당 요청은 시험 규정상 답변할 수 없습니다. 코딩과 무관합니다."
    )
    assert is_guardrail_blocked_response_text("요청이 가이드라인을 위반했습니다.")


def test_filter_turn_logs_for_debate_excludes_guardrail():
    state = {"guardrail_flag_turns": [1, 5]}
    logs = {
        "1": {
            "is_guardrail_failed": True,
            "prompt_evaluation_details": {"intent": "GUARDRAIL_BLOCKED", "score": 0},
        },
        "2": {"prompt_evaluation_details": {"intent": "CREATION", "score": 80}},
        "5": {"is_guardrail_failed": True, "prompt_evaluation_details": {"score": 0}},
    }
    filtered = filter_turn_logs_for_debate(logs, state)
    assert set(filtered.keys()) == {"2"}


def test_resolve_conversation_turn_storage_slot():
    state = {"guardrail_flag_turns": [1]}
    assert resolve_conversation_turn_for_guardrail(state, 1) == 1
    assert resolve_conversation_turn_for_guardrail(state, 2) == 1


def test_api_turn_to_conversation_turn_storage_slots():
    assert api_turn_to_conversation_turn(1, "user") == 1
    assert api_turn_to_conversation_turn(2, "assistant") == 1
    assert api_turn_to_conversation_turn(5, "USER") == 3


def test_build_guardrail_meta_patch_from_ai_content():
    state = {"guardrail_flag_turns": [], "guardrail_turn_reasons": {}}
    patch = build_guardrail_meta_patch(
        state,
        message_turn=2,
        role="assistant",
        content=format_guardrail_user_message("부적절"),
    )
    assert patch is not None
    assert patch["is_guardrail_failed"] is True
    assert patch["conversation_turn"] == 1


def test_process_output_blocked_registers_fields():
    result = IntentAnalysisResult(
        status="BLOCKED",
        block_reason="JAILBREAK",
        request_type="CHAT",
        guide_strategy=None,
        keywords=[],
        is_submission_request=False,
        guardrail_passed=False,
        violation_message="정답 코드를 요청함",
        reasoning="test",
    )
    state = {"current_turn": 3, "guardrail_flag_turns": [], "guardrail_turn_reasons": {}}
    out = process_output(result)
    merged = _merge_guardrail_turn_state(state, out, block_reason="JAILBREAK")
    assert merged["is_guardrail_failed"] is True
    assert 3 in merged["guardrail_flag_turns"]
    assert merged["guardrail_turn_reasons"]["3"] == "JAILBREAK"
    assert GUARDRAIL_USER_MESSAGE_PREFIX in merged["guardrail_message"]


@pytest.mark.asyncio
async def test_n4_skips_llm_eval_for_guardrail_turn():
    from app.domain.langgraph.nodes.eval import n4_eval_turn_guard as n4

    state = {
        "session_id": "session_1",
        "current_turn": 3,
        "guardrail_flag_turns": [1],
        "guardrail_turn_reasons": {"1": "OFF_TOPIC"},
        "messages": [
            {"role": "user", "turn": 1, "content": "날씨 알려줘"},
            {"role": "assistant", "turn": 1, "content": format_guardrail_user_message()},
            {"role": "user", "turn": 2, "content": "dp 힌트"},
            {"role": "assistant", "turn": 2, "content": "힌트입니다"},
        ],
        "problem_context": {},
    }

    llm_eval_turns = []
    guardrail_calls = []

    async def fake_eval_sync(*args, **kwargs):
        turn = kwargs.get("turn")
        if kwargs.get("is_guardrail_failed"):
            guardrail_calls.append(turn)
            return {"turn_score": 0.0, "intent_type": "GUARDRAIL_BLOCKED"}
        llm_eval_turns.append(turn)
        return {
            "turn_score": 80.0,
            "intent_type": "CREATION",
            "request_one_liner": "dp",
            "llm_answer_summary": "ok",
            "user_prompt_summary": "u",
        }

    turn_logs_after = {
        "1": {"prompt_evaluation_details": {"score": 0, "intent": "GUARDRAIL_BLOCKED"}},
        "2": {"prompt_evaluation_details": {"score": 80, "intent": "CREATION"}},
    }

    with patch.object(n4, "_evaluate_turn_sync", side_effect=fake_eval_sync):
        with patch.object(
            n4.redis_client,
            "get_all_turn_logs",
            new_callable=AsyncMock,
            return_value=turn_logs_after,
        ):
            result = await n4.eval_turn_submit_guard(state)

    assert guardrail_calls == [1]
    assert llm_eval_turns == [2]
    assert result["turn_scores"]["1"]["turn_score"] == 0
    assert result["turn_scores"]["2"]["turn_score"] == 80


@pytest.mark.asyncio
async def test_n4_previous_summary_excludes_guardrail_turn():
    from app.domain.langgraph.nodes.eval import n4_eval_turn_guard as n4

    state = {
        "session_id": "session_1",
        "current_turn": 4,
        "guardrail_flag_turns": [1],
        "guardrail_turn_reasons": {"1": "OFF_TOPIC"},
        "messages": [
            {"role": "user", "turn": 1, "content": "gr"},
            {"role": "assistant", "turn": 1, "content": format_guardrail_user_message()},
            {"role": "user", "turn": 2, "content": "t2"},
            {"role": "assistant", "turn": 2, "content": "a2"},
            {"role": "user", "turn": 3, "content": "t3"},
            {"role": "assistant", "turn": 3, "content": "a3"},
        ],
        "problem_context": {},
    }

    summaries_seen = []

    async def fake_eval_sync(*args, **kwargs):
        if kwargs.get("is_guardrail_failed"):
            return {"turn_score": 0.0, "intent_type": "GUARDRAIL_BLOCKED"}
        summaries_seen.append(kwargs.get("previous_turns_summary") or "")
        return {
            "turn_score": 70.0,
            "intent_type": "CREATION",
            "request_one_liner": f"u{kwargs['turn']}",
            "llm_answer_summary": f"a{kwargs['turn']}",
        }

    with patch.object(n4, "_evaluate_turn_sync", side_effect=fake_eval_sync):
        with patch.object(
            n4.redis_client, "get_all_turn_logs", new_callable=AsyncMock, return_value={}
        ):
            await n4.eval_turn_submit_guard(state)

    assert len(summaries_seen) == 2
    assert "Turn 1" not in summaries_seen[1]
    assert "[Turn 2]" in summaries_seen[1]


def test_is_guardrail_turn_helper():
    assert is_guardrail_turn({"guardrail_flag_turns": [2, 5]}, 5)
    assert not is_guardrail_turn({"guardrail_flag_turns": [2]}, 5)


@pytest.mark.asyncio
async def test_handle_failure_guardrail_appends_turn_pair():
    from app.domain.langgraph.nodes.system.system_nodes import handle_failure

    state = {
        "current_turn": 3,
        "human_message": "히히 오줌발싸",
        "is_guardrail_failed": True,
        "guardrail_message": "부적절한 요청입니다.",
        "intent_status": "failed_guardrail",
    }
    out = await handle_failure(state)
    assert len(out["messages"]) == 2
    human, ai = out["messages"]
    assert getattr(human, "turn", None) == 3
    assert getattr(ai, "turn", None) == 3
    assert getattr(human, "role", None) == "user"
    assert getattr(ai, "role", None) == "assistant"
    assert "히히" in human.content
    assert "시험 규정상" in ai.content
