"""
시험 관련 테이블 모델
exams, exam_participants, exam_statistics, entry_codes
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.session import Base
from app.infrastructure.persistence.models.enums import ExamStateEnum, ExamParticipantStateEnum


class Exam(Base):
    """시험 테이블"""
    __tablename__ = "exams"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[ExamStateEnum] = mapped_column(
        Enum(ExamStateEnum, name="ai_vibe_coding_test.exam_state_enum"),
        nullable=False,
        default=ExamStateEnum.DRAFT
    )
    problem_set_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("problem_sets.id"),
        nullable=True
    )
    starts_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
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
    participants: Mapped[List["ExamParticipant"]] = relationship(
        "ExamParticipant",
        back_populates="exam"
    )
    statistics: Mapped[Optional["ExamStatistics"]] = relationship(
        "ExamStatistics",
        back_populates="exam",
        uselist=False
    )


class ExamParticipant(Base):
    """시험 참가자 테이블"""
    __tablename__ = "exam_participants"
    
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
    state: Mapped[ExamParticipantStateEnum] = mapped_column(
        Enum(ExamParticipantStateEnum, name="ai_vibe_coding_test.exam_state_enum"),
        nullable=False,
        default=ExamParticipantStateEnum.REGISTERED
    )
    token_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    spec_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("problem_specs.id"),
        nullable=True
    )
    joined_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Relationships
    exam: Mapped["Exam"] = relationship("Exam", back_populates="participants")
    participant: Mapped["Participant"] = relationship("Participant")


class ExamStatistics(Base):
    """시험 통계 테이블"""
    __tablename__ = "exam_statistics"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("exams.id"),
        nullable=False,
        unique=True
    )
    bucket_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    bucket_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    active_examinees: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ws_connections: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    judge_queue_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_wait_sec: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 3),
        nullable=True
    )
    avg_run_time_ms: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 3),
        nullable=True
    )
    errors_rate_1m: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 3),
        nullable=True
    )
    submissions_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    submissions_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pass_rate_weighted: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 4),
        nullable=True
    )
    avg_prompt_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )
    avg_perf_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )
    avg_correctness_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )
    avg_total_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )
    token_used_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    token_used_avg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 3),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )
    
    # Relationships
    exam: Mapped["Exam"] = relationship("Exam", back_populates="statistics")


class EntryCode(Base):
    """입장 코드 테이블"""
    __tablename__ = "entry_codes"
    
    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    exam_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("exams.id"),
        nullable=True
    )
    problem_set_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("problem_sets.id"),
        nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    max_uses: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )


# Import for type hints
from app.infrastructure.persistence.models.participants import Participant



