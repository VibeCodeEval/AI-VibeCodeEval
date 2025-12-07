"""
LangGraph 상태 Repository
Redis를 이용한 그래프 상태 관리
"""
from typing import Optional, Any
from datetime import datetime
import json

from app.infrastructure.cache.redis_client import RedisClient
from app.core.config import settings


class StateRepository:
    """LangGraph 상태 관리 데이터 접근 계층"""
    
    def __init__(self, redis: RedisClient):
        self.redis = redis
    
    # ===== 그래프 상태 관리 =====
    
    def _serialize_messages(self, messages: list) -> list:
        """
        LangChain 메시지 객체를 JSON 직렬화 가능한 dict로 변환
        """
        serialized = []
        for msg in messages:
            if hasattr(msg, '__dict__'):
                # LangChain BaseMessage 객체
                serialized_msg = {
                    "type": getattr(msg, 'type', 'unknown'),
                    "content": getattr(msg, 'content', ''),
                }
                # turn, role, timestamp 등 추가 속성 보존
                if isinstance(msg, dict):
                    serialized_msg.update(msg)
                elif hasattr(msg, '__dict__'):
                    for key in ['turn', 'role', 'timestamp']:
                        if hasattr(msg, key):
                            serialized_msg[key] = getattr(msg, key)
            elif isinstance(msg, dict):
                # 이미 dict 형태
                serialized_msg = msg
            else:
                # 기타
                serialized_msg = {"content": str(msg)}
            
            serialized.append(serialized_msg)
        
        return serialized
    
    async def save_state(
        self,
        session_id: str,
        state: dict,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """그래프 상태 저장"""
        # messages 직렬화
        state_copy = {**state}
        if 'messages' in state_copy and isinstance(state_copy['messages'], list):
            state_copy['messages'] = self._serialize_messages(state_copy['messages'])
        
        state_with_meta = {
            **state_copy,
            "_meta": {
                "updated_at": datetime.utcnow().isoformat(),
                "session_id": session_id
            }
        }
        return await self.redis.save_graph_state(
            session_id, 
            state_with_meta,
            ttl_seconds
        )
    
    def _deserialize_messages(self, messages: list) -> list:
        """
        Redis dict를 LangChain BaseMessage 객체로 역직렬화
        
        Redis에서 가져온 dict 형태의 messages를 LangGraph가 사용하는
        LangChain BaseMessage 객체로 변환합니다.
        """
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        
        deserialized = []
        for msg in messages:
            if isinstance(msg, dict):
                # Redis에서 가져온 dict 형태
                msg_type = msg.get("type", "unknown")
                content = msg.get("content", "")
                
                # LangChain BaseMessage 객체 생성
                if msg_type == "human" or msg.get("role") == "user":
                    langchain_msg = HumanMessage(content=content)
                elif msg_type == "ai" or msg.get("role") in ["assistant", "ai"]:
                    langchain_msg = AIMessage(content=content)
                elif msg_type == "system" or msg.get("role") == "system":
                    langchain_msg = SystemMessage(content=content)
                else:
                    # 기본값: HumanMessage
                    langchain_msg = HumanMessage(content=content)
                
                # 커스텀 속성 추가 (turn, timestamp 등)
                if "turn" in msg:
                    langchain_msg.turn = msg["turn"]
                if "timestamp" in msg:
                    langchain_msg.timestamp = msg["timestamp"]
                if "role" in msg:
                    langchain_msg.role = msg["role"]
                
                deserialized.append(langchain_msg)
            elif hasattr(msg, 'content'):
                # 이미 LangChain BaseMessage 객체인 경우
                deserialized.append(msg)
            else:
                # 기타: 문자열 등
                deserialized.append(HumanMessage(content=str(msg)))
        
        return deserialized
    
    async def get_state(self, session_id: str) -> Optional[dict]:
        """
        그래프 상태 조회 (Redis → LangGraph State 변환)
        
        Redis에서 가져온 dict를 LangGraph가 사용할 수 있는 형태로 변환합니다.
        - messages: dict → LangChain BaseMessage 객체로 역직렬화
        - 기타 필드: 그대로 유지
        """
        state = await self.redis.get_graph_state(session_id)
        
        if state is None:
            return None
        
        # messages 역직렬화 (dict → LangChain BaseMessage 객체)
        if 'messages' in state and isinstance(state['messages'], list):
            state['messages'] = self._deserialize_messages(state['messages'])
        
        return state
    
    async def delete_state(self, session_id: str) -> bool:
        """그래프 상태 삭제"""
        result = await self.redis.delete_graph_state(session_id)
        return result > 0
    
    async def update_state_field(
        self,
        session_id: str,
        field: str,
        value: Any
    ) -> bool:
        """그래프 상태의 특정 필드 업데이트"""
        state = await self.get_state(session_id)
        if state is None:
            return False
        
        state[field] = value
        return await self.save_state(session_id, state)
    
    # ===== 체크포인트 관리 =====
    
    async def save_checkpoint(
        self,
        session_id: str,
        checkpoint_id: str,
        checkpoint_data: dict,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """체크포인트 저장"""
        return await self.redis.save_checkpoint(
            session_id,
            checkpoint_id,
            checkpoint_data,
            ttl_seconds
        )
    
    async def get_checkpoint(
        self,
        session_id: str,
        checkpoint_id: str
    ) -> Optional[dict]:
        """체크포인트 조회"""
        return await self.redis.get_checkpoint(session_id, checkpoint_id)
    
    # ===== 턴 데이터 관리 =====
    
    def _turn_key(self, session_id: str, turn: int) -> str:
        """턴 데이터 키 생성"""
        return f"turn:data:{session_id}:{turn}"
    
    async def save_turn_data(
        self,
        session_id: str,
        turn: int,
        turn_data: dict,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """턴 데이터 저장"""
        ttl = ttl_seconds or settings.CHECKPOINT_TTL_SECONDS
        key = self._turn_key(session_id, turn)
        return await self.redis.set_json(key, turn_data, ttl)
    
    async def get_turn_data(
        self,
        session_id: str,
        turn: int
    ) -> Optional[dict]:
        """턴 데이터 조회"""
        key = self._turn_key(session_id, turn)
        return await self.redis.get_json(key)
    
    # ===== 평가 점수 관리 =====
    
    def _score_key(self, session_id: str) -> str:
        """점수 데이터 키 생성"""
        return f"eval:scores:{session_id}"
    
    async def save_turn_scores(
        self,
        session_id: str,
        turn: int,
        scores: dict
    ) -> bool:
        """턴별 점수 저장"""
        key = self._score_key(session_id)
        existing = await self.redis.get_json(key) or {"turns": {}}
        existing["turns"][str(turn)] = scores
        existing["updated_at"] = datetime.utcnow().isoformat()
        return await self.redis.set_json(key, existing, settings.CHECKPOINT_TTL_SECONDS)
    
    async def get_all_turn_scores(self, session_id: str) -> Optional[dict]:
        """모든 턴 점수 조회"""
        key = self._score_key(session_id)
        return await self.redis.get_json(key)
    
    async def save_final_scores(
        self,
        session_id: str,
        final_scores: dict
    ) -> bool:
        """최종 점수 저장"""
        key = self._score_key(session_id)
        existing = await self.redis.get_json(key) or {"turns": {}}
        existing["final"] = final_scores
        existing["completed_at"] = datetime.utcnow().isoformat()
        return await self.redis.set_json(key, existing, settings.CHECKPOINT_TTL_SECONDS * 2)
    
    # ===== 메모리 요약 관리 =====
    
    def _memory_key(self, session_id: str) -> str:
        """메모리 요약 키 생성"""
        return f"memory:summary:{session_id}"
    
    async def save_memory_summary(
        self,
        session_id: str,
        summary: str,
        context: Optional[dict] = None
    ) -> bool:
        """메모리 요약 저장"""
        key = self._memory_key(session_id)
        data = {
            "summary": summary,
            "context": context or {},
            "updated_at": datetime.utcnow().isoformat()
        }
        return await self.redis.set_json(key, data, settings.CHECKPOINT_TTL_SECONDS)
    
    async def get_memory_summary(self, session_id: str) -> Optional[dict]:
        """메모리 요약 조회"""
        key = self._memory_key(session_id)
        return await self.redis.get_json(key)



