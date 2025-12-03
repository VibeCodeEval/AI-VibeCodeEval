"""
Pytest 설정 및 Fixtures
"""
import pytest
import sys
import asyncio

# Windows에서 SelectorEventLoop 사용 (gRPC 호환성)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Event loop fixture 제거
# pytest-asyncio가 기본적으로 각 테스트마다 새로운 event loop를 생성하도록 함
# scope="session"으로 설정하면 LLM 호출 중 event loop가 닫히는 문제 발생 가능

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
    # LangSmith 추적 비활성화 (테스트에서 토큰 절약)
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)  # API 키 제거

