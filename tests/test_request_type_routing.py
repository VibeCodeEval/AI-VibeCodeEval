from app.domain.langgraph.nodes.chat.routers import intent_router, main_router
from app.infrastructure.persistence.models.enums import IntentAnalyzerStatus


def test_intent_router_submission_request_type_takes_priority():
    state = {
        "request_type": "SUBMISSION",
        "is_submitted": False,
        "intent_status": IntentAnalyzerStatus.PASSED_HINT.value,
    }
    assert intent_router(state) == "eval_turn_guard"


def test_intent_router_chat_uses_intent_status():
    state = {
        "request_type": "CHAT",
        "is_submitted": False,
        "intent_status": IntentAnalyzerStatus.PASSED_HINT.value,
    }
    assert intent_router(state) == "writer"


def test_main_router_submission_request_type():
    state = {"request_type": "SUBMISSION", "is_submitted": False}
    assert main_router(state) == "eval_holistic_flow"

