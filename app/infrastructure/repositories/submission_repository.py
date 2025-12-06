"""
제출 관련 Repository
"""
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.persistence.models.submissions import Submission, SubmissionRun, Score
from app.infrastructure.persistence.models.enums import SubmissionStatusEnum, VerdictEnum


class SubmissionRepository:
    """제출 데이터 접근 계층"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_submission_by_id(
        self,
        submission_id: int,
        include_runs: bool = False,
        include_score: bool = False
    ) -> Optional[Submission]:
        """제출 ID로 조회"""
        query = select(Submission).where(Submission.id == submission_id)
        
        if include_runs:
            query = query.options(selectinload(Submission.runs))
        if include_score:
            query = query.options(selectinload(Submission.score))
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_participant_submissions(
        self,
        exam_id: int,
        participant_id: int
    ) -> List[Submission]:
        """참가자의 모든 제출 조회"""
        query = select(Submission).where(
            and_(
                Submission.exam_id == exam_id,
                Submission.participant_id == participant_id
            )
        ).order_by(Submission.created_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_latest_submission(
        self,
        exam_id: int,
        participant_id: int
    ) -> Optional[Submission]:
        """가장 최근 제출 조회"""
        query = select(Submission).where(
            and_(
                Submission.exam_id == exam_id,
                Submission.participant_id == participant_id
            )
        ).order_by(Submission.created_at.desc()).limit(1)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def create_submission(
        self,
        exam_id: int,
        participant_id: int,
        spec_id: int,
        lang: str,
        code_inline: str,
        code_sha256: Optional[str] = None,
        code_bytes: Optional[int] = None,
        code_loc: Optional[int] = None
    ) -> Submission:
        """제출 생성"""
        submission = Submission(
            exam_id=exam_id,
            participant_id=participant_id,
            spec_id=spec_id,
            lang=lang,
            status=SubmissionStatusEnum.QUEUED,
            code_inline=code_inline,
            code_sha256=code_sha256,
            code_bytes=code_bytes or len(code_inline.encode('utf-8')),
            code_loc=code_loc or len(code_inline.splitlines()),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(submission)
        await self.db.flush()
        return submission
    
    async def update_submission_status(
        self,
        submission_id: int,
        status: SubmissionStatusEnum
    ) -> Optional[Submission]:
        """제출 상태 업데이트"""
        submission = await self.get_submission_by_id(submission_id)
        if submission:
            submission.status = status
            submission.updated_at = datetime.utcnow()
            await self.db.flush()
        return submission
    
    async def add_submission_run(
        self,
        submission_id: int,
        case_index: int,
        grp: str,
        verdict: VerdictEnum,
        time_ms: Optional[int] = None,
        mem_kb: Optional[int] = None,
        stdout_bytes: Optional[int] = None,
        stderr_bytes: Optional[int] = None
    ) -> SubmissionRun:
        """제출 실행 결과 추가"""
        from app.infrastructure.persistence.models.enums import TestRunGrpEnum
        
        run = SubmissionRun(
            submission_id=submission_id,
            case_index=case_index,
            grp=TestRunGrpEnum(grp),
            verdict=verdict,
            time_ms=time_ms,
            mem_kb=mem_kb,
            stdout_bytes=stdout_bytes,
            stderr_bytes=stderr_bytes,
            created_at=datetime.utcnow()
        )
        self.db.add(run)
        await self.db.flush()
        return run
    
    async def create_or_update_score(
        self,
        submission_id: int,
        prompt_score: Optional[Decimal] = None,
        perf_score: Optional[Decimal] = None,
        correctness_score: Optional[Decimal] = None,
        total_score: Optional[Decimal] = None,
        rubric_json: Optional[dict] = None
    ) -> Score:
        """점수 생성 또는 업데이트"""
        # 기존 점수 조회
        query = select(Score).where(Score.submission_id == submission_id)
        result = await self.db.execute(query)
        score = result.scalar_one_or_none()
        
        if score:
            # 업데이트
            if prompt_score is not None:
                score.prompt_score = prompt_score
            if perf_score is not None:
                score.perf_score = perf_score
            if correctness_score is not None:
                score.correctness_score = correctness_score
            if total_score is not None:
                score.total_score = total_score
            if rubric_json is not None:
                score.rubric_json = rubric_json
        else:
            # 생성
            score = Score(
                submission_id=submission_id,
                prompt_score=prompt_score,
                perf_score=perf_score,
                correctness_score=correctness_score,
                total_score=total_score,
                rubric_json=rubric_json,
                created_at=datetime.utcnow()
            )
            self.db.add(score)
        
        await self.db.flush()
        return score
    
    async def get_submission_runs(
        self,
        submission_id: int
    ) -> List[SubmissionRun]:
        """제출 실행 결과 목록 조회"""
        query = select(SubmissionRun).where(
            SubmissionRun.submission_id == submission_id
        ).order_by(SubmissionRun.case_index)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())



