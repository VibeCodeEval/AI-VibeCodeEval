"""
PostgreSQL 세션 관리 (SQLAlchemy Async)
Spring Boot와 테이블을 공유하므로 읽기 위주 작업
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


# Async 엔진 생성
engine = create_async_engine(
    settings.POSTGRES_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# 세션 팩토리
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 베이스 클래스"""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 의존성 주입용 DB 세션 제공"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """서비스에서 사용할 DB 컨텍스트 매니저"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """DB 연결 초기화 및 테스트"""
    from sqlalchemy import text
    async with engine.begin() as conn:
        # Spring Boot가 테이블을 관리하므로 여기서는 테이블 생성하지 않음
        # 연결 테스트만 수행
        await conn.execute(text("SELECT 1"))


async def close_db():
    """DB 연결 종료"""
    await engine.dispose()


