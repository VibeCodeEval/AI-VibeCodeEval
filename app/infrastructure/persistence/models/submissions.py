"""
제출 관련 테이블 모델
submissions, submission_runs, scores
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    BigInteger,
    CHAR,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.session import Base
from app.infrastructure.persistence.models.enums import SubmissionStatusEnum, TestRunGrpEnum, VerdictEnum


class Submission(Base):
    """제출 테이블"""
    __tablename__ = "submissions"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("exams.id"),
        nullable=False
    )
    participant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("participants.id"),
        nullable=False
    )
    spec_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("problem_specs.spec_id"),
        nullable=False
    )
    lang: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[SubmissionStatusEnum] = mapped_column(
        Enum(SubmissionStatusEnum, name="submission_status_enum", schema="ai_vibe_coding_test"),
        nullable=False,
        default=SubmissionStatusEnum.QUEUED
    )
    code_inline: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    code_sha256: Mapped[Optional[str]] = mapped_column(CHAR(64), nullable=True)
    code_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    code_loc: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Relationships
    runs: Mapped[List["SubmissionRun"]] = relationship(
        "SubmissionRun",
        back_populates="submission"
    )
    score: Mapped[Optional["Score"]] = relationship(
        "Score",
        back_populates="submission",
        uselist=False
    )


class SubmissionRun(Base):
    """제출 실행 테이블 (Judge0 결과)"""
    __tablename__ = "submission_runs"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("submissions.id"),
        nullable=False
    )
    case_index: Mapped[int] = mapped_column(Integer, nullable=False)
    grp: Mapped[TestRunGrpEnum] = mapped_column(
        Enum(TestRunGrpEnum, name="ai_vibe_coding_test.test_run_grp_enum"),
        nullable=False
    )
    verdict: Mapped[VerdictEnum] = mapped_column(
        Enum(VerdictEnum, name="verdict_enum", schema="ai_vibe_coding_test"),
        nullable=False,
        default=VerdictEnum.AC
    )
    time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mem_kb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stdout_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stderr_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )
    
    # Relationships
    submission: Mapped["Submission"] = relationship(
        "Submission",
        back_populates="runs"
    )


class Score(Base):
    """점수 테이블"""
    __tablename__ = "scores"
    
    # DB 스키마에 따르면 submission_id가 PRIMARY KEY
    submission_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("submissions.id"),
        primary_key=True,
        nullable=False
    )
    prompt_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )
    perf_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )
    correctness_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )
    total_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )
    rubric_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )
    
    # Relationships
    submission: Mapped["Submission"] = relationship(
        "Submission",
        back_populates="score"
    )


