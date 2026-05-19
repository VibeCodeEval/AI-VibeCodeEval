"""Writer·handle_failure 공통 — state.messages용 턴 쌍(Human+AI)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List

from langchain_core.messages import AIMessage, HumanMessage


def build_turn_message_pair(
    human_content: str,
    ai_content: str,
    current_turn: int,
) -> List[Any]:
    """
    N4 eval_turn_guard가 기대하는 형식: conversation turn + role + content.
    LangChain 메시지에 turn/role/timestamp 속성 부여 (Redis 직렬화 시 보존).
    """
    human_msg = HumanMessage(content=human_content or "")
    human_msg.turn = int(current_turn)
    human_msg.role = "user"
    human_msg.timestamp = datetime.utcnow().isoformat()

    ai_msg = AIMessage(content=ai_content or "")
    ai_msg.turn = int(current_turn)
    ai_msg.role = "assistant"
    ai_msg.timestamp = datetime.utcnow().isoformat()

    return [human_msg, ai_msg]
