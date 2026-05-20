"""Redis 키 패턴 점검 (일회성)."""
import asyncio
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


async def main() -> None:
    from app.core.config import settings
    from app.infrastructure.cache.redis_client import RedisClient

    print(f"REDIS_HOST={settings.REDIS_HOST} REDIS_PORT={settings.REDIS_PORT} REDIS_DB={settings.REDIS_DB}")
    r = RedisClient()
    await r.connect()
    print("ping:", await r.client.ping())

    patterns = [
        "langgraph:state:*",
        "langgraph:*",
        "turn_logs:*",
        "debate_log:*",
        "graph_state:*",
        "*state*session*",
    ]
    for pat in patterns:
        keys = []
        async for k in r.client.scan_iter(match=pat, count=500):
            keys.append(k)
        print(f"{pat!r} -> {len(keys)} keys")
        for k in keys[:3]:
            print(f"  sample: {k}")

    all_keys = []
    async for k in r.client.scan_iter(count=500):
        all_keys.append(k)
    print(f"total keys: {len(all_keys)}")
    for k in sorted(all_keys):
        print(f"  {k}")
    await r.close()


if __name__ == "__main__":
    asyncio.run(main())
