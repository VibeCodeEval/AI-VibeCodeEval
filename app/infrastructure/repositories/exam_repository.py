"""
시험 관련 Repository
"""
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.persistence.models.exams import Exam, ExamParticipant, ExamStatistics
from app.infrastructure.persistence.models.problems import ProblemSpec
from app.infrastructure.persistence.models.enums import ExamStateEnum, ExamParticipantStateEnum


class ExamRepository:
    """시험 데이터 접근 계층"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_exam_by_id(self, exam_id: int) -> Optional[Exam]:
        """시험 ID로 조회"""
        query = select(Exam).where(Exam.id == exam_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_running_exams(self) -> List[Exam]:
        """진행 중인 시험 목록 조회"""
        query = select(Exam).where(Exam.state == ExamStateEnum.RUNNING)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_exam_participant(
        self,
        exam_id: int,
        participant_id: int
    ) -> Optional[ExamParticipant]:
        """시험 참가자 조회"""
        query = select(ExamParticipant).where(
            and_(
                ExamParticipant.exam_id == exam_id,
                ExamParticipant.participant_id == participant_id
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_problem_spec(self, spec_id: int) -> Optional[ProblemSpec]:
        """문제 스펙 조회 (spec_id로 조회)"""
        # DB 스키마에서 spec_id가 PRIMARY KEY이므로 id 필드로 조회
        query = select(ProblemSpec).where(ProblemSpec.id == spec_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_problem_spec_with_problem(self, spec_id: int) -> Optional[ProblemSpec]:
        """문제 스펙과 문제 정보를 함께 조회"""
        query = select(ProblemSpec).options(
            selectinload(ProblemSpec.problem)
        ).where(ProblemSpec.id == spec_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def update_participant_state(
        self,
        exam_id: int,
        participant_id: int,
        state: ExamParticipantStateEnum
    ) -> Optional[ExamParticipant]:
        """참가자 상태 업데이트"""
        participant = await self.get_exam_participant(exam_id, participant_id)
        if participant:
            participant.state = state
            await self.db.flush()
        return participant
    
    async def update_participant_tokens(
        self,
        exam_id: int,
        participant_id: int,
        additional_tokens: int
    ) -> Optional[ExamParticipant]:
        """참가자 토큰 사용량 업데이트"""
        participant = await self.get_exam_participant(exam_id, participant_id)
        if participant:
            participant.token_used += additional_tokens
            await self.db.flush()
        return participant
    
    async def check_token_limit(
        self,
        exam_id: int,
        participant_id: int,
        required_tokens: int = 0
    ) -> bool:
        """토큰 한도 확인"""
        participant = await self.get_exam_participant(exam_id, participant_id)
        if participant is None:
            return False
        
        if participant.token_limit is None:
            return True  # 제한 없음
        
        return (participant.token_used + required_tokens) <= participant.token_limit
    
    async def get_exam_statistics(self, exam_id: int) -> Optional[ExamStatistics]:
        """시험 통계 조회"""
        query = select(ExamStatistics).where(ExamStatistics.exam_id == exam_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()



