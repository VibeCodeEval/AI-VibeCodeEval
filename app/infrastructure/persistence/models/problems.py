"""
문제 관련 테이블 모델
problems, problem_specs, problem_sets, problem_set_items
"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.session import Base
from app.infrastructure.persistence.models.enums import DifficultyEnum, ProblemStatusEnum


class Problem(Base):
    """문제 테이블"""
    __tablename__ = "problems"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    difficulty: Mapped[DifficultyEnum] = mapped_column(
        Enum(DifficultyEnum, name="ai_vibe_coding_test.difficulty_enum"),
        nullable=False
    )
    tags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[ProblemStatusEnum] = mapped_column(
        Enum(ProblemStatusEnum, name="ai_vibe_coding_test.problem_status_enum"),
        nullable=False,
        default=ProblemStatusEnum.DRAFT
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False,
        default=datetime.utcnow
    )
    current_spec_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("problem_specs.id"),
        nullable=True
    )
    
    # Relationships
    specs: Mapped[List["ProblemSpec"]] = relationship(
        "ProblemSpec",
        back_populates="problem",
        foreign_keys="ProblemSpec.problem_id"
    )
    current_spec: Mapped[Optional["ProblemSpec"]] = relationship(
        "ProblemSpec",
        foreign_keys=[current_spec_id],
        post_update=True
    )


class ProblemSpec(Base):
    """문제 스펙 테이블 (버전 관리)"""
    __tablename__ = "problem_specs"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    problem_id: Mapped[int] = mapped_column(
        BigInteger, 
        ForeignKey("problems.id"), 
        nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checker_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    rubric_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    changelog_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), 
        nullable=True
    )
    
    # Relationships
    problem: Mapped["Problem"] = relationship(
        "Problem",
        back_populates="specs",
        foreign_keys=[problem_id]
    )


class ProblemSet(Base):
    """문제 세트 테이블"""
    __tablename__ = "problem_sets"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )
    
    # Relationships
    items: Mapped[List["ProblemSetItem"]] = relationship(
        "ProblemSetItem",
        back_populates="problem_set"
    )


class ProblemSetItem(Base):
    """문제 세트 항목 테이블"""
    __tablename__ = "problem_set_items"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    problem_set_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("problem_sets.id"),
        nullable=False
    )
    problem_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("problems.id"),
        nullable=False
    )
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # Relationships
    problem_set: Mapped["ProblemSet"] = relationship(
        "ProblemSet",
        back_populates="items"
    )
    problem: Mapped["Problem"] = relationship("Problem")



