"""
메시지 저장 서비스
PostgreSQL 먼저 저장 → Redis 체크포인트 업데이트

[목적]
- Spring Boot에서 받은 메시지를 PostgreSQL과 Redis에 저장
- 저장 순서: PostgreSQL → Redis (데이터 무결성 보장)

[플로우]
1. exam_id, participant_id로 세션 조회/생성
2. PostgreSQL에 메시지 저장
3. Redis 체크포인트 업데이트
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.repositories.session_repository import SessionRepository
from app.infrastructure.repositories.exam_repository import ExamRepository
from app.infrastructure.persistence.models.sessions import PromptSession, PromptMessage
from app.infrastructure.persistence.models.enums import PromptRoleEnum
from app.infrastructure.cache.redis_client import RedisClient
from app.infrastructure.repositories.state_repository import StateRepository

logger = logging.getLogger(__name__)


class MessageStorageService:
    """메시지 저장 서비스"""
    
    def __init__(self, db: AsyncSession, redis: RedisClient):
        """
        Args:
            db: PostgreSQL 세션
            redis: Redis 클라이언트
        """
        self.db = db
        self.redis = redis
        self.session_repo = SessionRepository(db)
        self.state_repo = StateRepository(redis)
    
    async def save_message(
        self,
        exam_id: int,
        participant_id: int,
        turn: Optional[int],
        role: str,
        content: str,
        token_count: Optional[int] = None,
        meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        메시지 저장 (PostgreSQL 먼저 → Redis 업데이트)
        
        [저장 순서]
        1. PostgreSQL에 먼저 저장 (데이터 무결성)
        2. 성공하면 Redis 체크포인트 업데이트
        
        [Atomic Increment 방식]
        - turn=None일 경우: DB에서 자동으로 MAX(turn) + 1 계산하여 저장
        - turn이 지정된 경우: 지정된 turn 번호로 저장 (중복 체크 수행)
        
        ⚠️ **중요**: turn=None은 파라미터 의미일 뿐, DB에는 항상 정수값이 저장됩니다.
        - DB 스키마: `turn INTEGER NOT NULL` (NULL 불가능)
        - SQL 서브쿼리: `COALESCE(MAX(turn), 0) + 1` → 항상 정수 반환 (최소 1)
        - 따라서 실제 저장되는 turn 값은 절대 NULL이 아닙니다.
        
        [호출 시점]
        - Spring Boot에서 SaveChatMessageRequest 받을 때
        - 매 메시지마다 호출 (USER, AI 모두)
        
        Args:
            exam_id: 시험 ID
            participant_id: 참가자 ID
            turn: 턴 번호 
                - None: DB에서 자동 계산 (MAX(turn) + 1, 최소 1)
                - int: 지정된 번호로 저장
                - ⚠️ 실제 DB 저장값은 항상 정수 (NULL 불가능)
            role: 역할 ('user' 또는 'assistant'/'ai')
            content: 메시지 내용
            token_count: 토큰 사용량 (선택)
            meta: 메타데이터 (선택)
        
        Returns:
            {
                "session_id": int,
                "message_id": int,
                "turn": int,  # 실제 저장된 turn 번호 (항상 정수, NULL 아님)
                "success": bool
            }
        
        Raises:
            ValueError: exam_participants가 없거나 spec_id가 없을 때
        """
        try:
            # 1. 세션 조회 또는 생성
            session = await self.session_repo.get_or_create_session(
                exam_id=exam_id,
                participant_id=participant_id
            )
            
            logger.info(
                f"[MessageStorage] 세션 확인/생성 완료 - "
                f"session_id: {session.id}, exam_id: {exam_id}, participant_id: {participant_id}"
            )
            
            # 2. Role 변환 ('user' → PromptRoleEnum.USER, 'assistant'/'ai' → PromptRoleEnum.AI)
            role_enum = self._convert_role(role)
            
            # 3. 중복 체크: turn이 지정된 경우에만 수행 (turn=None이면 DB에서 자동 계산하므로 불필요)
            if turn is not None:
                from sqlalchemy import select
                check_query = select(PromptMessage).where(
                    PromptMessage.session_id == session.id,
                    PromptMessage.turn == turn,
                    PromptMessage.role == role_enum
                )
                check_result = await self.db.execute(check_query)
                existing_msg = check_result.scalar_one_or_none()
                
                if existing_msg:
                    logger.warning(
                        f"[MessageStorage] 메시지가 이미 존재함 (건너뜀) - "
                        f"session_id: {session.id}, turn: {turn}, role: {role_enum.value}"
                    )
                    return {
                        "session_id": session.id,
                        "message_id": existing_msg.id,
                        "turn": existing_msg.turn,
                        "success": True
                    }
            
            # 4. PostgreSQL에 메시지 저장 (먼저)
            # turn=None이면 DB에서 자동으로 다음 turn 번호 계산
            message = await self.session_repo.add_message(
                session_id=session.id,
                turn=turn,  # None이면 DB에서 자동 계산
                role=role_enum,
                content=content,
                token_count=token_count or 0,
                meta=meta
            )
            
            # 커밋 (PostgreSQL 저장 완료)
            await self.db.commit()
            
            logger.info(
                f"[MessageStorage] PostgreSQL 저장 완료 - "
                f"session_id: {session.id}, message_id: {message.id}, turn: {turn}, role: {role}"
            )
            
            # 4. Redis 체크포인트 업데이트 (PostgreSQL 성공 후)
            # 실제 저장된 turn 값 사용 (turn=None이면 DB에서 자동 계산된 값)
            actual_turn = message.turn
            try:
                await self._update_redis_checkpoint(
                    session_id=session.id,
                    turn=actual_turn,
                    role=role,
                    content=content,
                    token_count=token_count
                )
                logger.info(
                    f"[MessageStorage] Redis 체크포인트 업데이트 완료 - "
                    f"session_id: {session.id}, turn: {turn}"
                )
            except Exception as redis_error:
                # Redis 실패해도 PostgreSQL은 저장되었으므로 경고만
                logger.warning(
                    f"[MessageStorage] Redis 업데이트 실패 (PostgreSQL은 저장됨) - "
                    f"session_id: {session.id}, error: {str(redis_error)}"
                )
            
            return {
                "session_id": session.id,
                "message_id": message.id,
                "turn": message.turn,  # 실제 저장된 turn 번호 반환
                "success": True
            }
            
        except Exception as e:
            # PostgreSQL 실패 시 롤백
            await self.db.rollback()
            logger.error(
                f"[MessageStorage] 메시지 저장 실패 - "
                f"exam_id: {exam_id}, participant_id: {participant_id}, turn: {turn}, error: {str(e)}"
            )
            raise
    
    def _convert_role(self, role: str) -> PromptRoleEnum:
        """역할 문자열을 PromptRoleEnum으로 변환"""
        role_lower = role.lower()
        if role_lower == "user":
            return PromptRoleEnum.USER
        elif role_lower in ["assistant", "ai", "model"]:
            return PromptRoleEnum.AI  # DB ENUM 정의에 맞춰 'AI' 사용
        else:
            # 기본값은 USER
            logger.warning(f"[MessageStorage] 알 수 없는 role: {role}, USER로 처리")
            return PromptRoleEnum.USER
    
    async def _update_redis_checkpoint(
        self,
        session_id: int,
        turn: int,
        role: str,
        content: str,
        token_count: Optional[int] = None
    ):
        """
        Redis 체크포인트 업데이트
        
        [업데이트 내용]
        - LangGraph State에 메시지 추가
        - turn_logs 업데이트 (선택적)
        """
        # Redis session_id는 문자열 형식 (예: "session_123")
        redis_session_id = f"session_{session_id}"
        
        # 기존 상태 로드
        state = await self.state_repo.get_state(redis_session_id)
        
        if not state:
            # 상태가 없으면 초기 상태 생성
            state = {
                "session_id": redis_session_id,
                "messages": [],
                "turn": 0,
            }
        
        # 메시지 추가 (LangChain 형식으로 변환 필요)
        # 현재는 간단히 메시지 리스트에 추가
        if "messages" not in state:
            state["messages"] = []
        
        # 메시지 형식: {"role": "user", "content": "...", "turn": 1}
        message_data = {
            "role": role,
            "content": content,
            "turn": turn,
        }
        if token_count:
            message_data["token_count"] = token_count
        
        state["messages"].append(message_data)
        state["turn"] = max(state.get("turn", 0), turn)
        
        # 상태 저장
        await self.state_repo.save_state(redis_session_id, state)
    
    async def save_messages_batch(
        self,
        exam_id: int,
        participant_id: int,
        messages: list[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        여러 메시지 일괄 저장
        
        Args:
            exam_id: 시험 ID
            participant_id: 참가자 ID
            messages: 메시지 리스트 [{"turn": 1, "role": "user", "content": "...", ...}, ...]
        
        Returns:
            {
                "session_id": int,
                "saved_count": int,
                "success": bool
            }
        """
        try:
            # 세션 조회 또는 생성
            session = await self.session_repo.get_or_create_session(
                exam_id=exam_id,
                participant_id=participant_id
            )
            
            saved_count = 0
            
            for msg in messages:
                role_enum = self._convert_role(msg.get("role", "user"))
                
                message = await self.session_repo.add_message(
                    session_id=session.id,
                    turn=msg.get("turn", 1),
                    role=role_enum,
                    content=msg.get("content", ""),
                    token_count=msg.get("token_count", 0),
                    meta=msg.get("meta")
                )
                saved_count += 1
            
            # 일괄 커밋
            await self.db.commit()
            
            logger.info(
                f"[MessageStorage] 일괄 저장 완료 - "
                f"session_id: {session.id}, saved_count: {saved_count}"
            )
            
            return {
                "session_id": session.id,
                "saved_count": saved_count,
                "success": True
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[MessageStorage] 일괄 저장 실패: {str(e)}")
            raise


