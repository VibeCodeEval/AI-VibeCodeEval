"""제출 평가 E2E 타임아웃 추적."""

import asyncio

import pytest

from app.domain.langgraph.eval_timeout_tracking import (
    begin_eval_tracking,
    end_eval_tracking,
    get_eval_current_node,
    log_evaluation_timeout,
    set_eval_current_node,
    wrap_eval_node_tracking,
)


def test_node_tracking_context():
    begin_eval_tracking(submission_id=99, session_id="session_1")
    try:
        assert get_eval_current_node() == "eval_process_start"
        set_eval_current_node("eval_turn_guard")
        assert get_eval_current_node() == "eval_turn_guard"
    finally:
        end_eval_tracking()
    assert get_eval_current_node() == "unknown"


@pytest.mark.asyncio
async def test_wrap_eval_node_tracking_sets_node():
    async def impl(state):
        return {"ok": True, "node": get_eval_current_node()}

    wrapped = wrap_eval_node_tracking("eval_code_execution", impl)
    begin_eval_tracking(submission_id=1)
    try:
        out = await wrapped({})
        assert out["node"] == "eval_code_execution"
    finally:
        end_eval_tracking()


def test_log_evaluation_timeout_message(caplog):
    import logging

    begin_eval_tracking(submission_id=42)
    set_eval_current_node("holistic_debate")
    try:
        with caplog.at_level(logging.ERROR):
            node = log_evaluation_timeout()
        assert node == "holistic_debate"
        assert "ai-evaluation-timeout[holistic_debate]" in caplog.text
        assert "submission_id=42" in caplog.text
    finally:
        end_eval_tracking()
