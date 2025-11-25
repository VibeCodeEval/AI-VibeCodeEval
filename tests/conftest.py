"""
Pytest 설정 및 Fixtures
"""
import asyncio
import pytest
from typing import Generator

# Event loop fixture
@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """세션 범위의 이벤트 루프 생성"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


# 테스트용 환경 변수 설정
@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """테스트 환경 변수 설정"""
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

