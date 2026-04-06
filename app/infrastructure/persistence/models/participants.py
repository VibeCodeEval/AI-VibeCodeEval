"""
참가자 테이블 모델
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.infrastructure.persistence.session import Base


class Participant(Base):
    """참가자 테이블 (물리 이름은 VIBECODE_PARTICIPANT_TABLE, 예: users)"""

    @declared_attr
    def __tablename__(cls) -> str:  # noqa: N805
        from app.core.config import get_settings

        return get_settings().VIBECODE_PARTICIPANT_TABLE

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
