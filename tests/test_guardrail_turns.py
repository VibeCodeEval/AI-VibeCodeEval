"""가드레일 턴 등록·N4/N8 필터 단위 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.langgraph.nodes.chat.n2_intent_analyzer import (
    IntentAnalysisResult,
    _merge_guardrail_turn_state,
    process_output,
)
from app.domain.langgraph.utils.turn_messages import (
    extract_turn_pair_from_state_messages,
    message_matches_conversation_turn,
    resolve_turn_pair_for_eval,
)
from app.domain.langgraph.utils.guardrail_turns import (
    GUARDRAIL_USER_MESSAGE_PREFIX,
    api_turn_to_conversation_turn,
    build_guardrail_meta_patch,
    filter_turn_logs_for_debate,
    filter_turn_material_for_debate,
    format_guardrail_user_message,
    is_guardrail_blocked_response_text,
    is_guardrail_turn,
    normalize_state_turn_fields,
    register_guardrail_turn,
    resolve_conversation_turn_for_guardrail,
    storage_slot_to_conversation_turn,
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


def test_normalize_state_legacy_storage_current_turn():
    """대화 3턴 legacy: current_turn=6(storage), messages turn 5/6 등."""
    state = {
        "current_turn": 6,
        "turn": 6,
        "guardrail_flag_turns": [5],
        "guardrail_turn_reasons": {"5": "OFF_TOPIC"},
        "messages": [
            {"role": "user", "turn": 1, "content": "a"},
            {"role": "assistant", "turn": 2, "content": "b"},
            {"role": "user", "turn": 3, "content": "c"},
            {"role": "assistant", "turn": 4, "content": "d"},
            {"role": "user", "turn": 5, "content": "gr"},
            {"role": "assistant", "turn": 6, "content": format_guardrail_user_message()},
        ],
    }
    normalize_state_turn_fields(state)
    assert state["current_turn"] == 3
    assert state["guardrail_flag_turns"] == [3]
    assert state["messages"][-2]["turn"] == 3
    assert state["messages"][-2].get("storage_turn") == 5


def test_normalize_state_preserves_already_conversation_turns():
    state = {
        "current_turn": 2,
        "messages": [
            {"role": "user", "turn": 1, "storage_turn": 1, "content": "x"},
            {"role": "assistant", "turn": 1, "storage_turn": 2, "content": "y"},
        ],
        "guardrail_flag_turns": [1],
    }
    normalize_state_turn_fields(state)
    assert state["current_turn"] == 2
    assert state["messages"][0]["turn"] == 1
    assert state["messages"][1]["turn"] == 1


def test_normalize_state_preserves_conversation_turns_without_storage_turn():
    state = {
        "current_turn": 4,
        "messages": [
            {"role": "user", "turn": 1, "content": "u1"},
            {"role": "assistant", "turn": 1, "content": "a1"},
            {"role": "user", "turn": 2, "content": "u2"},
            {"role": "assistant", "turn": 2, "content": "a2"},
            {"role": "user", "turn": 3, "content": "u3"},
            {"role": "assistant", "turn": 3, "content": "a3"},
            {"role": "user", "turn": 4, "content": "u4"},
            {"role": "assistant", "turn": 4, "content": "a4"},
        ],
        "guardrail_flag_turns": [2, 4],
        "guardrail_turn_reasons": {"2": "INAPPROPRIATE", "4": "JAILBREAK"},
    }
    normalize_state_turn_fields(state)
    assert state["current_turn"] == 4
    assert [m["turn"] for m in state["messages"]] == [1, 1, 2, 2, 3, 3, 4, 4]
    assert state["guardrail_flag_turns"] == [2, 4]
    assert state["guardrail_turn_reasons"] == {
        "2": "INAPPROPRIATE",
        "4": "JAILBREAK",
    }


def test_storage_slot_to_conversation_turn():
    assert storage_slot_to_conversation_turn(10) == 5
    assert storage_slot_to_conversation_turn(9) == 5


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


def test_filter_turn_material_for_debate_excludes_guardrail_turn_scores():
    state = {"guardrail_flag_turns": [1]}
    logs = {
        "1": {
            "is_guardrail_failed": True,
            "prompt_evaluation_details": {"intent": "GUARDRAIL_BLOCKED", "score": 0},
        },
        "2": {"prompt_evaluation_details": {"intent": "SETTING", "score": 80}},
    }
    scores = {"1": {"turn_score": 0.0}, "2": {"turn_score": 80.0}}
    filtered_logs, filtered_scores, excluded = filter_turn_material_for_debate(
        logs, scores, state
    )
    assert set(filtered_logs.keys()) == {"2"}
    assert set(filtered_scores.keys()) == {"2"}
    assert excluded == [{"turn": "1", "reason": "guardrail_flag_turns"}]


def test_resolve_conversation_turn_storage_slot():
    state = {"guardrail_flag_turns": [1]}
    assert resolve_conversation_turn_for_guardrail(state, 1) == 1
    assert resolve_conversation_turn_for_guardrail(state, 2) == 1


def test_api_turn_to_conversation_turn_storage_slots():
    assert api_turn_to_conversation_turn(1, "user") == 1
    assert api_turn_to_conversation_turn(2, "assistant") == 1
    assert api_turn_to_conversation_turn(5, "USER") == 3


def test_message_matches_conversation_turn_storage_slot():
    assert message_matches_conversation_turn(3, "user", 0, 2)
    assert message_matches_conversation_turn(4, "assistant", 0, 2)
    assert not message_matches_conversation_turn(3, "assistant", 0, 2)


def test_message_matches_conversation_turn_disambiguates_assistant_turn_two():
    # idx=1은 첫 번째 assistant 메시지 자리 -> conversation turn 1로 해석되어야 함
    assert message_matches_conversation_turn(2, "assistant", 1, 1)
    assert not message_matches_conversation_turn(2, "assistant", 1, 2)


def test_message_matches_conversation_turn_keeps_conversation_style_when_index_matches():
    # idx=3은 두 번째 assistant 자리 -> conversation turn 2와 정합
    assert message_matches_conversation_turn(2, "assistant", 3, 2)
    assert not message_matches_conversation_turn(2, "assistant", 3, 1)


def test_extract_turn_pair_mismatched_tags_uses_index_fallback():
    """session_6 유형: user turn=2, ai turn=3 (conv 2) — strict 매칭만으로는 AI 누락."""
    messages = [
        {"role": "user", "turn": 1, "content": "t1u"},
        {"role": "assistant", "turn": 1, "content": "t1a"},
        {"role": "user", "turn": 2, "content": "t2u"},
        {"role": "assistant", "turn": 3, "content": "t2a"},
        {"role": "user", "turn": 4, "content": "t3u"},
        {"role": "assistant", "turn": 5, "content": "t3a"},
    ]
    human, ai, src = extract_turn_pair_from_state_messages(messages, 2)
    assert src == "state_index"
    assert human == "t2u"
    assert ai == "t2a"

    human3, ai3, src3 = extract_turn_pair_from_state_messages(messages, 3)
    assert src3 == "state_index"
    assert human3 == "t3u"
    assert ai3 == "t3a"


@pytest.mark.asyncio
async def test_resolve_turn_pair_pg_fallback_when_state_empty():
    from app.domain.langgraph.utils import turn_messages as tm

    with patch.object(
        tm,
        "fetch_turn_pair_from_prompt_messages",
        new_callable=AsyncMock,
        return_value=("pg_human", "pg_ai"),
    ):
        human, ai, src = await resolve_turn_pair_for_eval([], "session_6", 2)

    assert src == "pg"
    assert human == "pg_human"
    assert ai == "pg_ai"


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
async def test_n4_phase2_not_triggered_after_save_then_guardrail():
    """SAVE → GR → normal: 3번째 턴 is_phase2_first_turn=False (리뷰 #1)."""
    from app.domain.langgraph.nodes.eval import n4_eval_turn_guard as n4

    state = {
        "session_id": "session_1",
        "current_turn": 4,
        "guardrail_flag_turns": [2],
        "guardrail_turn_reasons": {"2": "OFF_TOPIC"},
        "messages": [
            {"role": "user", "turn": 1, "content": "SAVE"},
            {"role": "assistant", "turn": 1, "content": "saved"},
            {"role": "user", "turn": 2, "content": "bad"},
            {"role": "assistant", "turn": 2, "content": format_guardrail_user_message()},
            {"role": "user", "turn": 3, "content": "normal q"},
            {"role": "assistant", "turn": 3, "content": "normal a"},
        ],
        "problem_context": {},
    }

    phase2_flags = []

    async def fake_eval_sync(*args, **kwargs):
        if kwargs.get("is_guardrail_failed"):
            return {"turn_score": 0.0, "intent_type": "GUARDRAIL_BLOCKED"}
        phase2_flags.append((kwargs["turn"], kwargs.get("is_phase2_first_turn")))
        return {
            "turn_score": 70.0,
            "intent_type": "CREATION",
            "request_one_liner": "n",
            "llm_answer_summary": "a",
        }

    with patch.object(n4, "_evaluate_turn_sync", side_effect=fake_eval_sync):
        with patch.object(
            n4.redis_client, "get_all_turn_logs", new_callable=AsyncMock, return_value={}
        ):
            await n4.eval_turn_submit_guard(state)

    assert 2 not in [t for t, _ in phase2_flags]
    turn3 = next((p2 for t, p2 in phase2_flags if t == 3), None)
    assert turn3 is False


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
