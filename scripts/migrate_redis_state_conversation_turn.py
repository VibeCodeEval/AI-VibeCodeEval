#!/usr/bin/env python
"""
Redis langgraph state의 conversation / storage turn 정규화 (일회성 마이그레이션).

대상 키: langgraph:state:session_{id}  (RedisClient._state_key)

사용 예:
  uv run python scripts/migrate_redis_state_conversation_turn.py
  uv run python scripts/migrate_redis_state_conversation_turn.py --apply
  uv run python scripts/migrate_redis_state_conversation_turn.py --session-id 42
  uv run python scripts/migrate_redis_state_conversation_turn.py --apply -o data/redis_migrate_report.jsonl

기본은 --dry-run (Redis 변경 없음).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

logger = logging.getLogger(__name__)

STATE_KEY_PREFIX = "langgraph:state:"


def _state_changed(before: Dict[str, Any], after: Dict[str, Any]) -> bool:
    return json.dumps(before, sort_keys=True, default=str) != json.dumps(
        after, sort_keys=True, default=str
    )


def _migrate_one_state(state: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    from app.domain.langgraph.utils.guardrail_turns import normalize_state_turn_fields

    before = deepcopy(state)
    after = normalize_state_turn_fields(deepcopy(state))
    meta = {
        "before_current_turn": before.get("current_turn"),
        "after_current_turn": after.get("current_turn"),
        "before_guardrail_flag_turns": before.get("guardrail_flag_turns"),
        "after_guardrail_flag_turns": after.get("guardrail_flag_turns"),
        "message_count": len(before.get("messages") or []),
    }
    return after, meta


async def _run(
    apply: bool,
    session_filter: Optional[str],
    output_path: Optional[str],
) -> int:
    from app.core.config import settings
    from app.infrastructure.cache.redis_client import RedisClient

    redis = RedisClient()
    await redis.connect()

    pattern = f"{STATE_KEY_PREFIX}*"
    if session_filter:
        sid = session_filter if session_filter.startswith("session_") else f"session_{session_filter}"
        keys = [f"{STATE_KEY_PREFIX}{sid}"]
    else:
        keys = []
        async for key in redis.client.scan_iter(match=pattern, count=200):
            keys.append(key)

    report_lines: List[Dict[str, Any]] = []
    changed_count = 0
    error_count = 0

    for key in sorted(keys):
        session_id = key.removeprefix(STATE_KEY_PREFIX)
        try:
            state = await redis.get_graph_state(session_id)
            if not state:
                continue
            state.pop("_meta", None)
            after, meta = _migrate_one_state(state)
            changed = _state_changed(state, after)
            line = {
                "session_id": session_id,
                "redis_key": key,
                "changed": changed,
                **meta,
                "ts": datetime.utcnow().isoformat(),
            }
            report_lines.append(line)

            if changed:
                changed_count += 1
                if apply:
                    ttl = await redis.client.ttl(key)
                    ok = await redis.save_graph_state(
                        session_id,
                        after,
                        ttl_seconds=ttl if ttl and ttl > 0 else None,
                    )
                    line["applied"] = ok
                    logger.info("APPLY %s current_turn %s -> %s", session_id, meta["before_current_turn"], meta["after_current_turn"])
                else:
                    logger.info(
                        "DRY-RUN %s current_turn %s -> %s",
                        session_id,
                        meta["before_current_turn"],
                        meta["after_current_turn"],
                    )
        except Exception as e:
            error_count += 1
            report_lines.append(
                {
                    "session_id": session_id,
                    "redis_key": key,
                    "error": str(e),
                    "ts": datetime.utcnow().isoformat(),
                }
            )
            logger.exception("Failed %s", key)

    await redis.close()

    summary = {
        "mode": "apply" if apply else "dry-run",
        "scanned": len(keys),
        "changed": changed_count,
        "errors": error_count,
        "redis_url_host": getattr(settings, "REDIS_HOST", "from REDIS_URL"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    out = output_path or os.path.join(
        project_root,
        "data",
        f"redis_migrate_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jsonl",
    )
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for line in report_lines:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    print(f"Report: {out}", file=sys.stderr)

    return 1 if error_count else 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Redis graph state turn migration")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="실제 Redis에 저장 (기본: dry-run)",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="단일 세션 (예: 42 또는 session_42)",
    )
    parser.add_argument("-o", "--output", type=str, default=None, help="jsonl 리포트 경로")
    args = parser.parse_args()
    return asyncio.run(_run(args.apply, args.session_id, args.output))


if __name__ == "__main__":
    raise SystemExit(main())
