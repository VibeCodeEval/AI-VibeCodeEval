"""
N8 debate_log Redis — CLI 덤프(dump_debate_redis)와 평가 JSON보내기에서 공통 사용.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def normalize_langgraph_session_id(raw: str) -> str:
    s = raw.strip()
    if s.isdigit():
        return f"session_{s}"
    return s


async def async_fetch_debate_log_json(
    langgraph_session_id: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    dump_debate_redis.py 가 파일에 쓰는 본문과 동일한 dict 를 반환.

    Returns:
        (payload, unavailable_reason)
        payload 가 None 이면 unavailable_reason 에 사유(또는 Redis 오류).
    """
    from app.core.config import get_settings
    from app.infrastructure.cache.redis_client import redis_client

    settings = get_settings()
    redis_key = f"debate_log:{langgraph_session_id}"

    try:
        await redis_client.connect()
    except Exception as e:
        return None, f"Redis 연결 실패: {e}"

    try:
        data = await redis_client.get_debate_log(langgraph_session_id)
    finally:
        await redis_client.close()

    if not data:
        return None, (
            f"Redis에 {redis_key} 가 없습니다. "
            f"DEBATE_LOG_TO_REDIS=true 였는지, TTL({settings.CHECKPOINT_TTL_SECONDS}s ≈ "
            f"{settings.CHECKPOINT_TTL_SECONDS // 3600}h) 내에 조회했는지 확인하세요."
        )

    meta = {
        "redis_key": redis_key,
        "checkpoint_ttl_seconds": settings.CHECKPOINT_TTL_SECONDS,
        "note": "N8 저장 시점부터 위 TTL 동안 키가 유지됩니다.",
    }
    payload: Dict[str, Any] = {"_dump_meta": meta, **data}
    return payload, None


async def async_debate_redis_section_for_prompt_session(
    prompt_session_id: int,
) -> Dict[str, Any]:
    """
    export_evaluation_json 번들에 넣을 debate_redis 섹션 (항상 동일 키).
    """
    sid = f"session_{prompt_session_id}"
    dump, reason = await async_fetch_debate_log_json(sid)
    return {
        "description": (
            "N8 다중 에이전트 토론 Redis 스냅샷 (scripts/dump_debate_redis.py 본문과 동일). "
            "DEBATE_LOG_TO_REDIS=true 일 때만 N8이 기록합니다."
        ),
        "langgraph_session_id": sid,
        "redis_key": f"debate_log:{sid}",
        "dump": dump,
        "unavailable_reason": reason,
    }
