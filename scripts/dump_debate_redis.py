#!/usr/bin/env python
"""
Redis에 남아 있는 N8 토론 로그를 JSON 파일로 덤프합니다.

사전 조건:
  - 평가 실행 시 환경 변수 DEBATE_LOG_TO_REDIS=true (또는 .env 동일) 로 N8이
    debate_log:{session_id} 키를 저장했을 것.

실행이 끝난 뒤에도 Redis 키가 TTL 안에 있으면 조회 가능합니다.
  - TTL 기본값: CHECKPOINT_TTL_SECONDS = 86400 초 (24시간, app/core/config.py)

사용 예:
  set DEBATE_LOG_TO_REDIS=true
  # ... 제출 평가 실행 ...
  uv run python scripts/dump_debate_redis.py --session-id 42
  uv run python scripts/dump_debate_redis.py --session-id session_42 -o data/debate_42.json

환경: REDIS_URL 또는 REDIS_HOST/REDIS_PORT (앱과 동일), .env 로드

데이터 형식은 app.infrastructure.cache.debate_redis_dump 및
scripts/export_evaluation_json.py 의 debate_redis.dump 와 동일합니다.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Any, Optional

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

logger = logging.getLogger(__name__)


async def _dump(session_id: str, output_path: Optional[str], stdout: bool) -> int:
    from app.infrastructure.cache.debate_redis_dump import async_fetch_debate_log_json

    payload, err = await async_fetch_debate_log_json(session_id)

    if not payload:
        print(err or "Redis에서 debate_log 를 가져오지 못했습니다.", file=sys.stderr)
        return 1

    text = json.dumps(payload, ensure_ascii=False, indent=2)

    if stdout:
        print(text)
        return 0

    out = output_path or os.path.join(
        project_root, "data", f"debate_{session_id.replace(':', '_')}.json"
    )
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"저장: {out}")
    return 0


def main() -> None:
    from app.infrastructure.cache.debate_redis_dump import normalize_langgraph_session_id

    parser = argparse.ArgumentParser(description="Redis N8 debate_log → JSON 파일")
    parser.add_argument(
        "--session-id",
        required=True,
        help="LangGraph session_id (예: 42 또는 session_42)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="출력 JSON 경로 (기본: data/debate_{session_id}.json)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="파일 대신 표준 출력",
    )
    args = parser.parse_args()
    sid = normalize_langgraph_session_id(args.session_id)
    rc = asyncio.run(_dump(sid, args.output, args.stdout))
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
