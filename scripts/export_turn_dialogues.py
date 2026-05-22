#!/usr/bin/env python
"""
exam × participant 조합의 대화 턴( conversation turn ) USER/AI 본문만 JSON으로보냅니다.

기본: exam_id=1, participant 1~6, conversation turn 1·2
저장: data/{exam_id}_participants_{from}-{to}_turns_{t1}_{t2}_dialogues.json

사용 예:
  uv run python scripts/export_turn_dialogues.py
  uv run python scripts/export_turn_dialogues.py --exam-id 1 --from 4 --to 6 --turns 1 2
  uv run python scripts/export_turn_dialogues.py --participant-id 5 --exam-id 1 -o data/custom.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

logger = logging.getLogger(__name__)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _message_side(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "storage_turn": row["turn"],
        "role": row["role"],
        "content": row["content"],
        "token_count": row["token_count"],
        "meta": row["meta"],
        "created_at": row["created_at"],
    }


def _extract_conversation_turn_pair(
    messages: List[Dict[str, Any]],
    conversation_turn: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], str]:
    """storage turn(2N-1/2N) 우선, 실패 시 (2N-2, 2N-1) 인덱스 fallback."""
    from app.infrastructure.persistence.models.enums import PromptRoleEnum
    from app.infrastructure.repositories.session_repository import (
        conversation_turn_to_storage_slot,
    )

    user_slot = conversation_turn_to_storage_slot(conversation_turn, PromptRoleEnum.USER)
    ai_slot = conversation_turn_to_storage_slot(conversation_turn, PromptRoleEnum.AI)

    user_row: Optional[Dict[str, Any]] = None
    ai_row: Optional[Dict[str, Any]] = None
    for m in messages:
        role_u = str(m.get("role") or "").upper()
        if m["turn"] == user_slot and role_u == "USER":
            user_row = m
        elif m["turn"] == ai_slot and role_u == "AI":
            ai_row = m

    if user_row and ai_row:
        return (
            _message_side(user_row),
            _message_side(ai_row),
            "storage_slot",
        )

    start = (conversation_turn - 1) * 2
    if start + 1 < len(messages):
        u, a = messages[start], messages[start + 1]
        ru = str(u.get("role") or "").upper()
        ra = str(a.get("role") or "").upper()
        out_u = _message_side(u) if ru == "USER" else None
        out_a = _message_side(a) if ra == "AI" else None
        if out_u or out_a:
            return out_u, out_a, "index_fallback"

    return (
        _message_side(user_row) if user_row else None,
        _message_side(ai_row) if ai_row else None,
        "partial",
    )


async def _find_session_id(participant_id: int, exam_id: int) -> Optional[int]:
    from sqlalchemy import select

    from app.infrastructure.persistence.models.sessions import PromptSession
    from app.infrastructure.persistence.session import get_db_context

    async with get_db_context() as db:
        sid = await db.scalar(
            select(PromptSession.id)
            .where(
                PromptSession.participant_id == participant_id,
                PromptSession.exam_id == exam_id,
            )
            .order_by(PromptSession.id.asc())
            .limit(1)
        )
        return int(sid) if sid is not None else None


async def _fetch_messages(session_id: int) -> List[Dict[str, Any]]:
    from sqlalchemy import text

    from app.infrastructure.persistence.session import get_db_context

    async with get_db_context() as db:
        result = await db.execute(
            text(
                """
                SELECT id, session_id, turn, role::text AS role, content,
                       token_count, meta, created_at
                FROM prompt_messages
                WHERE session_id = :sid
                ORDER BY turn, id
                """
            ),
            {"sid": session_id},
        )
        return [
            {
                "id": r["id"],
                "session_id": r["session_id"],
                "turn": r["turn"],
                "role": r["role"],
                "content": r["content"],
                "token_count": r["token_count"],
                "meta": r["meta"],
                "created_at": r["created_at"],
            }
            for r in result.mappings().all()
        ]


async def _export_participant_dialogues(
    exam_id: int,
    participant_id: int,
    conversation_turns: List[int],
) -> Optional[Dict[str, Any]]:
    session_id = await _find_session_id(participant_id, exam_id)
    if session_id is None:
        logger.warning("세션 없음 exam=%s participant=%s", exam_id, participant_id)
        return None

    messages = await _fetch_messages(session_id)
    turns_out: List[Dict[str, Any]] = []
    for ct in conversation_turns:
        user_side, ai_side, source = _extract_conversation_turn_pair(messages, ct)
        turns_out.append(
            {
                "conversation_turn": ct,
                "pair_source": source,
                "user": user_side,
                "ai": ai_side,
            }
        )

    return {
        "exam_id": exam_id,
        "participant_id": participant_id,
        "session_id": session_id,
        "message_count": len(messages),
        "turns": turns_out,
    }


async def _async_main() -> int:
    parser = argparse.ArgumentParser(description="대화 턴 USER/AI 본문 JSON 추출")
    parser.add_argument("--exam-id", type=int, default=1)
    parser.add_argument("--from", dest="from_pid", type=int, default=1, help="participant 시작")
    parser.add_argument("--to", dest="to_pid", type=int, default=6, help="participant 끝")
    parser.add_argument(
        "--turns",
        type=int,
        nargs="+",
        default=[1, 2],
        help="conversation turn 번호 (기본 1 2)",
    )
    parser.add_argument(
        "--participant-id",
        type=int,
        action="append",
        dest="participant_ids",
        help="지정 시 --from/--to 대신 이 ID만 (복수 가능)",
    )
    parser.add_argument("-o", "--output", type=str, default="")
    parser.add_argument("--stdout", action="store_true")
    parser.add_argument("--no-pretty", action="store_true")
    args = parser.parse_args()

    if args.participant_ids:
        pids = sorted(set(args.participant_ids))
    else:
        lo, hi = min(args.from_pid, args.to_pid), max(args.from_pid, args.to_pid)
        pids = list(range(lo, hi + 1))

    conversation_turns = sorted(set(args.turns))
    sessions: List[Dict[str, Any]] = []
    missing: List[int] = []

    for pid in pids:
        row = await _export_participant_dialogues(
            args.exam_id, pid, conversation_turns
        )
        if row is None:
            missing.append(pid)
        else:
            sessions.append(row)

    turn_slug = "_".join(str(t) for t in conversation_turns)
    pid_slug = (
        str(pids[0])
        if len(pids) == 1
        else f"{pids[0]}-{pids[-1]}"
    )
    default_name = (
        f"{args.exam_id}_participants_{pid_slug}_turns_{turn_slug}_dialogues.json"
    )

    payload: Dict[str, Any] = {
        "meta": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "exam_id": args.exam_id,
            "participant_ids": pids,
            "conversation_turns": conversation_turns,
            "description": (
                "conversation turn N = prompt_messages storage USER(2N-1) + AI(2N). "
                "평가·코드 점수 제외, 대화 본문만."
            ),
            "missing_participant_ids": missing,
        },
        "sessions": sessions,
    }

    indent = None if args.no_pretty else 2
    text = json.dumps(payload, ensure_ascii=False, indent=indent, default=_json_default)

    if args.stdout:
        print(text)
        return 0 if not missing else 1

    data_dir = os.path.join(project_root, "data")
    os.makedirs(data_dir, exist_ok=True)
    out_path = args.output or os.path.join(data_dir, default_name)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"저장 완료: {out_path}", file=sys.stderr)
    if missing:
        print(f"세션 없음 participant_ids={missing}", file=sys.stderr)
    return 0 if sessions else 1


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(asyncio.run(_async_main()))


if __name__ == "__main__":
    main()
