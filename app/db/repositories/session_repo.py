"""
프롬프트 세션 Repository
PostgreSQL에서 세션 정보를 조회하고 관리
"""
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.sessions import PromptSession, PromptMessage
from app.db.models.enums import PromptRoleEnum


class SessionRepository:
    """프롬프트 세션 데이터 접근 계층"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_session_by_id(
        self, 
        session_id: int,
        include_messages: bool = False
    ) -> Optional[PromptSession]:
        """세션 ID로 조회"""
        query = select(PromptSession).where(PromptSession.id == session_id)
        
        if include_messages:
            query = query.options(selectinload(PromptSession.messages))
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_active_session(
        self,
        exam_id: int,
        participant_id: int
    ) -> Optional[PromptSession]:
        """활성 세션 조회 (ended_at이 None인 세션)"""
        query = select(PromptSession).where(
            and_(
                PromptSession.exam_id == exam_id,
                PromptSession.participant_id == participant_id,
                PromptSession.ended_at.is_(None)
            )
        ).options(selectinload(PromptSession.messages))
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_session_messages(
        self,
        session_id: int,
        limit: Optional[int] = None
    ) -> List[PromptMessage]:
        """세션의 메시지 목록 조회"""
        query = select(PromptMessage).where(
            PromptMessage.session_id == session_id
        ).order_by(PromptMessage.turn.asc())
        
        if limit:
            query = query.limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_last_n_messages(
        self,
        session_id: int,
        n: int = 10
    ) -> List[PromptMessage]:
        """세션의 마지막 N개 메시지 조회"""
        query = select(PromptMessage).where(
            PromptMessage.session_id == session_id
        ).order_by(PromptMessage.turn.desc()).limit(n)
        
        result = await self.db.execute(query)
        messages = list(result.scalars().all())
        return list(reversed(messages))  # 시간순으로 다시 정렬
    
    async def add_message(
        self,
        session_id: int,
        turn: int,
        role: PromptRoleEnum,
        content: str,
        token_count: int = 0,
        meta: Optional[dict] = None
    ) -> PromptMessage:
        """메시지 추가"""
        message = PromptMessage(
            session_id=session_id,
            turn=turn,
            role=role,
            content=content,
            token_count=token_count,
            meta=meta,
            created_at=datetime.utcnow()
        )
        self.db.add(message)
        await self.db.flush()
        return message
    
    async def update_session_tokens(
        self,
        session_id: int,
        additional_tokens: int
    ) -> None:
        """세션 토큰 사용량 업데이트"""
        session = await self.get_session_by_id(session_id)
        if session:
            session.total_tokens += additional_tokens
            await self.db.flush()
    
    async def end_session(
        self,
        session_id: int
    ) -> None:
        """세션 종료"""
        session = await self.get_session_by_id(session_id)
        if session:
            session.ended_at = datetime.utcnow()
            await self.db.flush()
    
    async def get_conversation_history(
        self,
        session_id: int
    ) -> List[dict]:
        """대화 히스토리를 LangChain 형식으로 반환"""
        messages = await self.get_session_messages(session_id)
        return [
            {
                "role": msg.role.value,
                "content": msg.content,
                "turn": msg.turn,
                "token_count": msg.token_count
            }
            for msg in messages
        ]



