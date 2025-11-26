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
            await self._client.aclose()
        if self._pool:
            await self._pool.aclose()
    
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
    
    # ===== 턴별 평가 로그 관리 =====
    
    def _turn_log_key(self, session_id: str, turn: int) -> str:
        """턴 로그 키 생성"""
        return f"turn_logs:{session_id}:{turn}"
    
    def _turn_mapping_key(self, session_id: str) -> str:
        """턴 매핑 키 생성"""
        return f"turn_mapping:{session_id}"
    
    async def save_turn_log(
        self, 
        session_id: str, 
        turn: int, 
        turn_log: dict,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """
        턴별 평가 로그 저장
        
        turn_log 구조:
        {
            "turn_number": 5,
            "user_prompt_summary": "...",
            "prompt_evaluation_details": {
                "intent": "OPTIMIZATION_REQUEST",
                "score": 90,
                "rubrics": [...]
            },
            "llm_answer_summary": "...",
            "llm_answer_reasoning": "..."
        }
        """
        key = self._turn_log_key(session_id, turn)
        ttl = ttl_seconds or settings.CHECKPOINT_TTL_SECONDS
        return await self.set_json(key, turn_log, ttl)
    
    async def get_turn_log(self, session_id: str, turn: int) -> Optional[dict]:
        """특정 턴의 평가 로그 조회"""
        key = self._turn_log_key(session_id, turn)
        return await self.get_json(key)
    
    async def get_all_turn_logs(self, session_id: str) -> dict:
        """
        세션의 모든 턴 로그 조회
        
        Returns:
            {"1": {...}, "2": {...}, ...}
        """
        pattern = f"turn_logs:{session_id}:*"
        
        # Redis SCAN으로 키 조회
        cursor = 0
        keys = []
        while True:
            cursor, partial_keys = await self.client.scan(
                cursor=cursor,
                match=pattern,
                count=100
            )
            keys.extend(partial_keys)
            if cursor == 0:
                break
        
        # 각 키에서 턴 로그 조회
        logs = {}
        for key in keys:
            # key 형식: "turn_logs:session_id:turn_number"
            turn_num = key.split(":")[-1]
            log = await self.get_json(key)
            if log:
                logs[turn_num] = log
        
        return logs
    
    # ===== 턴-메시지 매핑 관리 =====
    
    async def save_turn_mapping(
        self,
        session_id: str,
        turn: int,
        start_msg_idx: int,
        end_msg_idx: int,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """
        특정 턴의 메시지 인덱스 매핑 저장
        
        Args:
            session_id: 세션 ID
            turn: 턴 번호
            start_msg_idx: messages 배열에서 user 메시지 인덱스
            end_msg_idx: messages 배열에서 assistant 메시지 인덱스
            ttl_seconds: TTL (기본값: 3600초)
        
        Returns:
            저장 성공 여부
        """
        ttl = ttl_seconds or 3600
        key = self._turn_mapping_key(session_id)
        
        # 기존 매핑 로드
        existing_mapping = await self.get_json(key) or {}
        
        # 새 턴 매핑 추가
        existing_mapping[str(turn)] = {
            "start_msg_idx": start_msg_idx,
            "end_msg_idx": end_msg_idx
        }
        
        # 저장
        return await self.set_json(key, existing_mapping, ttl)
    
    async def get_turn_mapping(self, session_id: str) -> Optional[dict]:
        """
        세션의 모든 턴-메시지 매핑 조회
        
        Returns:
            {
                "1": {"start_msg_idx": 0, "end_msg_idx": 1},
                "2": {"start_msg_idx": 2, "end_msg_idx": 3},
                ...
            }
        """
        key = self._turn_mapping_key(session_id)
        return await self.get_json(key)
    
    async def get_turn_message_indices(
        self, 
        session_id: str, 
        turn: int
    ) -> Optional[dict]:
        """
        특정 턴의 메시지 인덱스 조회
        
        Returns:
            {"start_msg_idx": 0, "end_msg_idx": 1} or None
        """
        mapping = await self.get_turn_mapping(session_id)
        if mapping:
            return mapping.get(str(turn))
        return None
    
    async def delete_all_turn_logs(self, session_id: str) -> int:
        """세션의 모든 턴 로그 삭제"""
        pattern = f"turn_logs:{session_id}:*"
        
        cursor = 0
        deleted_count = 0
        while True:
            cursor, keys = await self.client.scan(
                cursor=cursor,
                match=pattern,
                count=100
            )
            if keys:
                deleted_count += await self.client.delete(*keys)
            if cursor == 0:
                break
        
        return deleted_count


# 싱글톤 인스턴스
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """FastAPI 의존성 주입용"""
    return redis_client



