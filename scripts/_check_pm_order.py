"""prompt_messages turn 순서·Redis state messages 비교."""
import asyncio
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy import text

from app.infrastructure.cache.redis_client import redis_client
from app.infrastructure.persistence.session import get_db_context
from app.infrastructure.repositories.session_repository import storage_slot_to_conversation_turn


async def main():
    for session_id in (2, 3):
        await dump_session(session_id)


async def dump_session(session_id: int):
    print("\n" + "=" * 60)
    async with get_db_context() as db:
        r = await db.execute(
            text(
                """
                SELECT id, turn, role::text AS role,
                       left(content, 50) AS head, created_at,
                       meta
                FROM prompt_messages
                WHERE session_id = :sid
                ORDER BY turn, id
                """
            ),
            {"sid": session_id},
        )
        rows = list(r.mappings().all())
        print(f"DB prompt_messages session_id={session_id} count={len(rows)}")
        for row in rows:
            conv = storage_slot_to_conversation_turn(row["turn"])
            meta = row["meta"] if isinstance(row["meta"], dict) else {}
            gr = meta.get("is_guardrail_failed")
            print(
                f"  id={row['id']} storage_turn={row['turn']} conv={conv} "
                f"role={row['role']} gr={gr} created={row['created_at']}"
            )
            print(f"    head={row['head']!r}")

    await redis_client.connect()
    state = await redis_client.get_graph_state(f"session_{session_id}")
    await redis_client.close()
    msgs = (state or {}).get("messages") or []
    print(f"\nRedis graph_state messages count={len(msgs)}")
    print(f"  current_turn={state.get('current_turn') if state else None}")
    print(f"  guardrail_flag_turns={state.get('guardrail_flag_turns') if state else None}")
    for i, m in enumerate(msgs):
        if isinstance(m, dict):
            print(
                f"  [{i}] turn={m.get('turn')} storage_turn={m.get('storage_turn')} "
                f"role={m.get('role')} len={len(str(m.get('content','')))}"
            )
        else:
            print(f"  [{i}] type={type(m).__name__} turn={getattr(m,'turn',None)}")


if __name__ == "__main__":
    asyncio.run(main())
