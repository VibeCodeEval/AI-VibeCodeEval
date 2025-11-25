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
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.models.enums import PromptRoleEnum


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
        Enum(PromptRoleEnum, name="ai_vibe_coding_test.prompt_role_enum"),
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


