"""
프롬프트 세션 및 메시지 테이블 모델
prompt_sessions, prompt_messages
"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.session import Base
from app.infrastructure.persistence.models.enums import PromptRoleEnum, EvaluationTypeEnum


class PromptSession(Base):
    """프롬프트 세션 테이블"""
    __tablename__ = "prompt_sessions"
    
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
    spec_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("problem_specs.id"),
        nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Relationships
    messages: Mapped[List["PromptMessage"]] = relationship(
        "PromptMessage",
        back_populates="session",
        order_by="PromptMessage.turn"
    )
    
    # 평가 결과와의 관계
    evaluations: Mapped[List["PromptEvaluation"]] = relationship(
        "PromptEvaluation",
        foreign_keys="PromptEvaluation.session_id",
        back_populates="session"
    )


class PromptMessage(Base):
    """프롬프트 메시지 테이블"""
    __tablename__ = "prompt_messages"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("prompt_sessions.id"),
        nullable=False
    )
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[PromptRoleEnum] = mapped_column(
        Enum(PromptRoleEnum, name="prompt_role_enum", schema="ai_vibe_coding_test"),
        nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    meta: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )
    # Full-text search vector (PostgreSQL 전용)
    # fts: Mapped[Optional[str]] = mapped_column(TSVECTOR, nullable=True)
    
    # Relationships
    session: Mapped["PromptSession"] = relationship(
        "PromptSession",
        back_populates="messages"
    )
    
    # 평가 결과와의 관계 (turn별 평가)
    evaluations: Mapped[List["PromptEvaluation"]] = relationship(
        "PromptEvaluation",
        foreign_keys="[PromptEvaluation.session_id, PromptEvaluation.turn]",
        primaryjoin="and_(PromptMessage.session_id == PromptEvaluation.session_id, PromptMessage.turn == PromptEvaluation.turn)",
        viewonly=True
    )


class PromptEvaluation(Base):
    """프롬프트 평가 결과 테이블 (4번, 6.a 노드 평가 결과)"""
    __tablename__ = "prompt_evaluations"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("prompt_sessions.id", ondelete="CASCADE"),
        nullable=False
    )
    turn: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True  # NULL이면 세션 전체 평가 (HOLISTIC_FLOW)
    )
    evaluation_type: Mapped[EvaluationTypeEnum] = mapped_column(
        Enum(
            EvaluationTypeEnum, 
            name="evaluation_type_enum", 
            schema="ai_vibe_coding_test",
            create_type=False,  # 기존 ENUM 타입 사용 (DB에 이미 존재)
            native_enum=True   # PostgreSQL 네이티브 ENUM 사용
        ),
        nullable=False
    )  # 'TURN_EVAL', 'HOLISTIC_FLOW'
    details: Mapped[dict] = mapped_column(JSONB, nullable=False)  # 모든 평가 데이터(점수, 분석 내용 등) 저장
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )
    
    # Composite Foreign Key (turn이 NULL이 아닐 때만 적용)
    # SQLAlchemy에서는 부분 FK를 직접 지원하지 않으므로, 
    # 애플리케이션 레벨에서 검증하거나 DB 트리거 사용
    __table_args__ = (
        UniqueConstraint('session_id', 'turn', 'evaluation_type', name='prompt_evaluations_session_turn_type_unique'),
    )
    
    # Relationships
    session: Mapped["PromptSession"] = relationship(
        "PromptSession",
        foreign_keys=[session_id],
        back_populates="evaluations"
    )
    
    # turn이 NULL이 아닐 때만 message와 관계
    # SQLAlchemy에서는 조건부 relationship을 직접 지원하지 않으므로 viewonly로 처리
    message: Mapped[Optional["PromptMessage"]] = relationship(
        "PromptMessage",
        foreign_keys="[PromptMessage.session_id, PromptMessage.turn]",
        primaryjoin="and_(PromptEvaluation.session_id == PromptMessage.session_id, PromptEvaluation.turn == PromptMessage.turn)",
        viewonly=True
    )

