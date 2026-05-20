"""Writer·handle_failure·N4 공통 — state.messages / PG 턴 쌍(Human+AI)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List, Optional, Tuple

from langchain_core.messages import AIMessage, HumanMessage

from app.domain.langgraph.utils.guardrail_turns import api_turn_to_conversation_turn

logger = logging.getLogger(__name__)

_USER_ROLES = frozenset({"user", "human"})
_AI_ROLES = frozenset({"assistant", "ai"})


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


def parse_message_fields(msg: Any) -> Tuple[Optional[Any], str, str]:
    """(raw_turn, normalized_role, content) — role은 user|assistant|other."""
    if isinstance(msg, dict):
        raw_turn = msg.get("turn")
        role_raw = msg.get("role") or msg.get("type") or ""
        content = str(msg.get("content") or "")
    else:
        raw_turn = getattr(msg, "turn", None)
        role_raw = getattr(msg, "role", None) or getattr(msg, "type", None) or ""
        if hasattr(msg, "content"):
            content = str(msg.content or "")
        else:
            content = str(msg)

    role_s = str(role_raw).lower()
    if role_s in _USER_ROLES or role_s == "human":
        norm = "user"
    elif role_s in _AI_ROLES or role_s == "ai":
        norm = "assistant"
    else:
        norm = "other"
    return raw_turn, norm, content


def message_matches_conversation_turn(
    raw_turn: Any,
    role: str,
    message_index: int,
    conversation_turn: int,
) -> bool:
    """
    Redis message의 turn(storage slot·conv 혼재)을 conversation turn과 동치 비교.
    raw_turn이 없으면 메시지 순서 (0,1)=턴1 로 추론.
    """
    if conversation_turn < 1:
        return False

    if raw_turn is not None:
        try:
            if api_turn_to_conversation_turn(raw_turn, role) == conversation_turn:
                return True
        except (TypeError, ValueError):
            pass
        try:
            if int(raw_turn) == conversation_turn:
                return True
        except (TypeError, ValueError):
            pass

    if raw_turn is None and message_index >= 0:
        inferred = (message_index // 2) + 1
        return inferred == conversation_turn

    return False


def _pair_by_message_index(
    messages: List[Any], conversation_turn: int
) -> Tuple[Optional[str], Optional[str]]:
    """turn 태그가 어긋나도 [u,a,u,a,...] 순서로 쌍 복원."""
    base = (conversation_turn - 1) * 2
    if base + 1 >= len(messages):
        return None, None
    _, r0, c0 = parse_message_fields(messages[base])
    _, r1, c1 = parse_message_fields(messages[base + 1])
    human = c0 if r0 == "user" else None
    ai = c1 if r1 == "assistant" else None
    if human is None and r0 == "assistant":
        ai = c0
    if ai is None and r1 == "user":
        human = c1
    return human, ai


def extract_turn_pair_from_state_messages(
    messages: List[Any], conversation_turn: int
) -> Tuple[Optional[str], Optional[str], str]:
    """
    State.messages에서 conversation turn의 user/ai 본문 추출.

    Returns:
        (human_content, ai_content, source)
        source: state_turn | state_index | none
    """
    human_msg: Optional[str] = None
    ai_msg: Optional[str] = None

    for idx, msg in enumerate(messages):
        raw_turn, role, content = parse_message_fields(msg)
        if not message_matches_conversation_turn(raw_turn, role, idx, conversation_turn):
            continue
        if role == "user":
            human_msg = content
        elif role == "assistant":
            ai_msg = content

    if human_msg and ai_msg:
        return human_msg, ai_msg, "state_turn"

    h2, a2 = _pair_by_message_index(messages, conversation_turn)
    if h2 and a2:
        return h2, a2, "state_index"

    return human_msg, ai_msg, "none"


def _postgres_session_id(session_id: str) -> Optional[int]:
    if not session_id:
        return None
    if session_id.startswith("session_"):
        try:
            return int(session_id.replace("session_", "", 1))
        except ValueError:
            return None
    try:
        return int(session_id)
    except (TypeError, ValueError):
        return None


async def fetch_turn_pair_from_prompt_messages(
    session_id: str, conversation_turn: int
) -> Tuple[Optional[str], Optional[str]]:
    """
    Redis state에 쌍이 없을 때 PG prompt_messages(storage turn)에서 USER/AI 조회.
    """
    pg_sid = _postgres_session_id(session_id)
    if pg_sid is None or conversation_turn < 1:
        return None, None

    from app.infrastructure.persistence.models.enums import PromptRoleEnum
    from app.infrastructure.persistence.session import get_db_context
    from app.infrastructure.repositories.session_repository import (
        SessionRepository,
        conversation_turn_to_storage_slot,
    )

    user_slot = conversation_turn_to_storage_slot(conversation_turn, PromptRoleEnum.USER)
    ai_slot = conversation_turn_to_storage_slot(conversation_turn, PromptRoleEnum.AI)

    try:
        async with get_db_context() as db:
            repo = SessionRepository(db)
            rows = await repo.get_session_messages(pg_sid)
            human: Optional[str] = None
            ai: Optional[str] = None
            for row in rows:
                if row.turn == user_slot and row.role == PromptRoleEnum.USER:
                    human = row.content
                elif row.turn == ai_slot and row.role == PromptRoleEnum.AI:
                    ai = row.content

            if human and ai:
                return human, ai

            # storage turn이 어긋난 경우: turn 오름차순 상 (2n-1,2n) 위치 fallback
            start = (conversation_turn - 1) * 2
            if len(rows) >= start + 2:
                u_row, a_row = rows[start], rows[start + 1]
                if u_row.role == PromptRoleEnum.USER:
                    human = human or u_row.content
                if a_row.role == PromptRoleEnum.AI:
                    ai = ai or a_row.content

            return human, ai
    except Exception as e:
        logger.warning(
            "[TurnMessages] PG fallback 실패 session_id=%s turn=%s error=%s",
            session_id,
            conversation_turn,
            e,
        )
        return None, None


async def resolve_turn_pair_for_eval(
    messages: List[Any],
    session_id: str,
    conversation_turn: int,
) -> Tuple[Optional[str], Optional[str], str]:
    """
    N4용: state 우선 → 부족하면 PG fallback.
    source: state_turn | state_index | pg | partial | none
    """
    human, ai, src = extract_turn_pair_from_state_messages(messages, conversation_turn)
    if human and ai:
        return human, ai, src

    pg_human, pg_ai = await fetch_turn_pair_from_prompt_messages(
        session_id, conversation_turn
    )
    if pg_human and pg_ai:
        logger.info(
            "[TurnMessages] 턴 %s — Redis 불완전, PG prompt_messages에서 쌍 복원 (session=%s)",
            conversation_turn,
            session_id,
        )
        return pg_human, pg_ai, "pg"

    if human or ai:
        return (
            human or pg_human,
            ai or pg_ai,
            "partial",
        )

    if pg_human or pg_ai:
        return pg_human, pg_ai, "partial_pg"

    return None, None, "none"
