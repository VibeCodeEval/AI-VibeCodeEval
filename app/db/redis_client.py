"""
Redis 클라이언트 관리
LangGraph 상태 및 세션 관리에 사용
"""
import json
from typing import Any, Optional
from datetime import timedelta

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

from app.core.config import settings


class RedisClient:
    """Redis 비동기 클라이언트 래퍼"""
    
    def __init__(self):
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Redis 연결 초기화"""
        self._pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=20,
            decode_responses=True,
        )
        self._client = redis.Redis(connection_pool=self._pool)
        # 연결 테스트
        await self._client.ping()
    
    async def close(self):
        """Redis 연결 종료"""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
    
    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError("Redis client not initialized. Call connect() first.")
        return self._client
    
    # ===== 기본 Key-Value 연산 =====
    
    async def get(self, key: str) -> Optional[str]:
        """키 값 조회"""
        return await self.client.get(key)
    
    async def set(
        self, 
        key: str, 
        value: str, 
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """키 값 설정"""
        if ttl_seconds:
            return await self.client.setex(key, ttl_seconds, value)
        return await self.client.set(key, value)
    
    async def delete(self, key: str) -> int:
        """키 삭제"""
        return await self.client.delete(key)
    
    async def exists(self, key: str) -> bool:
        """키 존재 여부 확인"""
        return await self.client.exists(key) > 0
    
    async def expire(self, key: str, ttl_seconds: int) -> bool:
        """키 TTL 설정"""
        return await self.client.expire(key, ttl_seconds)
    
    # ===== JSON 데이터 연산 =====
    
    async def get_json(self, key: str) -> Optional[dict]:
        """JSON 데이터 조회"""
        data = await self.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def set_json(
        self, 
        key: str, 
        value: dict, 
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """JSON 데이터 저장"""
        return await self.set(key, json.dumps(value, ensure_ascii=False), ttl_seconds)
    
    # ===== LangGraph 상태 관리 =====
    
    def _state_key(self, session_id: str) -> str:
        """LangGraph 상태 키 생성"""
        return f"langgraph:state:{session_id}"
    
    def _checkpoint_key(self, session_id: str, checkpoint_id: str) -> str:
        """체크포인트 키 생성"""
        return f"langgraph:checkpoint:{session_id}:{checkpoint_id}"
    
    async def save_graph_state(
        self, 
        session_id: str, 
        state: dict,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """LangGraph 상태 저장"""
        ttl = ttl_seconds or settings.CHECKPOINT_TTL_SECONDS
        return await self.set_json(self._state_key(session_id), state, ttl)
    
    async def get_graph_state(self, session_id: str) -> Optional[dict]:
        """LangGraph 상태 조회"""
        return await self.get_json(self._state_key(session_id))
    
    async def delete_graph_state(self, session_id: str) -> int:
        """LangGraph 상태 삭제"""
        return await self.delete(self._state_key(session_id))
    
    async def save_checkpoint(
        self,
        session_id: str,
        checkpoint_id: str,
        checkpoint_data: dict,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """체크포인트 저장"""
        ttl = ttl_seconds or settings.CHECKPOINT_TTL_SECONDS
        return await self.set_json(
            self._checkpoint_key(session_id, checkpoint_id), 
            checkpoint_data, 
            ttl
        )
    
    async def get_checkpoint(
        self, 
        session_id: str, 
        checkpoint_id: str
    ) -> Optional[dict]:
        """체크포인트 조회"""
        return await self.get_json(self._checkpoint_key(session_id, checkpoint_id))
    
    # ===== 세션 활성 상태 관리 =====
    
    def _active_session_key(self, exam_id: int, participant_id: int) -> str:
        """활성 세션 키 생성"""
        return f"session:active:{exam_id}:{participant_id}"
    
    async def set_session_active(
        self, 
        exam_id: int, 
        participant_id: int,
        session_id: str,
        ttl_seconds: int = 3600
    ) -> bool:
        """세션 활성 상태 설정"""
        key = self._active_session_key(exam_id, participant_id)
        return await self.set(key, session_id, ttl_seconds)
    
    async def get_active_session(
        self, 
        exam_id: int, 
        participant_id: int
    ) -> Optional[str]:
        """활성 세션 ID 조회"""
        key = self._active_session_key(exam_id, participant_id)
        return await self.get(key)
    
    async def is_session_active(
        self, 
        exam_id: int, 
        participant_id: int
    ) -> bool:
        """세션 활성 여부 확인"""
        key = self._active_session_key(exam_id, participant_id)
        return await self.exists(key)


# 싱글톤 인스턴스
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """FastAPI 의존성 주입용"""
    return redis_client



