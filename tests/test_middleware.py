"""
Middleware 테스트
Rate Limiting, Retry, Logging Middleware의 동작을 검증합니다.
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Dict, Any

from langchain_core.runnables import RunnableLambda
from langchain_core.runnables.utils import Input, Output

from app.domain.langgraph.middleware import (
    RateLimitingMiddleware,
    RetryMiddleware,
    LoggingMiddleware
)


class TestRateLimitingMiddleware:
    """Rate Limiting Middleware 테스트"""
    
    @pytest.mark.asyncio
    async def test_rate_limiting_basic(self):
        """기본 Rate Limiting 동작 테스트"""
        # Mock Chain 생성
        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(return_value="result")
        
        # Rate Limiting Middleware 적용 (5초에 2회 제한)
        rate_limiter = RateLimitingMiddleware(max_calls=2, period=5.0)
        wrapped_chain = rate_limiter.wrap(mock_chain)
        
        # 첫 번째 호출 (즉시 실행)
        start_time = time.time()
        result1 = await wrapped_chain.ainvoke({"input": "test1"})
        elapsed1 = time.time() - start_time
        
        assert result1 == "result"
        assert elapsed1 < 0.5  # 즉시 실행되어야 함
        assert mock_chain.ainvoke.call_count == 1
        
        # 두 번째 호출 (즉시 실행)
        start_time = time.time()
        result2 = await wrapped_chain.ainvoke({"input": "test2"})
        elapsed2 = time.time() - start_time
        
        assert result2 == "result"
        assert elapsed2 < 0.5  # 즉시 실행되어야 함
        assert mock_chain.ainvoke.call_count == 2
        
        # 세 번째 호출 (Rate Limit 초과 - 대기 필요)
        start_time = time.time()
        result3 = await wrapped_chain.ainvoke({"input": "test3"})
        elapsed3 = time.time() - start_time
        
        assert result3 == "result"
        # 대기 시간이 있어야 함 (최소 4초 이상)
        assert elapsed3 > 3.0
        assert mock_chain.ainvoke.call_count == 3
    
    @pytest.mark.asyncio
    async def test_rate_limiting_key_based(self):
        """키 기반 Rate Limiting 테스트"""
        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(return_value="result")
        
        # 키 기반 Rate Limiting
        def key_func(inputs: Input) -> str:
            return str(inputs.get("user_id", "default"))
        
        rate_limiter = RateLimitingMiddleware(
            max_calls=1,
            period=2.0,
            key_func=key_func
        )
        wrapped_chain = rate_limiter.wrap(mock_chain)
        
        # 다른 키로 호출 (각각 독립적으로 제한)
        result1 = await wrapped_chain.ainvoke({"user_id": "user1", "input": "test1"})
        result2 = await wrapped_chain.ainvoke({"user_id": "user2", "input": "test2"})
        
        assert result1 == "result"
        assert result2 == "result"
        assert mock_chain.ainvoke.call_count == 2


class TestRetryMiddleware:
    """Retry Middleware 테스트"""
    
    @pytest.mark.asyncio
    async def test_retry_success_on_second_attempt(self):
        """재시도 성공 테스트"""
        mock_chain = AsyncMock()
        
        # 첫 번째 호출 실패, 두 번째 호출 성공
        mock_chain.ainvoke = AsyncMock(side_effect=[
            Exception("Rate limit exceeded"),
            "result"
        ])
        
        retry_middleware = RetryMiddleware(
            max_retries=3,
            initial_delay=0.1,  # 빠른 테스트를 위해 짧은 대기 시간
            backoff_strategy="fixed"
        )
        wrapped_chain = retry_middleware.wrap(mock_chain)
        
        result = await wrapped_chain.ainvoke({"input": "test"})
        
        assert result == "result"
        assert mock_chain.ainvoke.call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """재시도 모두 실패 테스트"""
        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(side_effect=Exception("Persistent error"))
        
        retry_middleware = RetryMiddleware(
            max_retries=2,
            initial_delay=0.1,
            backoff_strategy="fixed"
        )
        wrapped_chain = retry_middleware.wrap(mock_chain)
        
        with pytest.raises(Exception, match="Persistent error"):
            await wrapped_chain.ainvoke({"input": "test"})
        
        # 최대 재시도 횟수 + 1 (초기 시도) = 3번 호출
        assert mock_chain.ainvoke.call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_exponential_backoff(self):
        """Exponential backoff 테스트"""
        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(side_effect=Exception("Error"))
        
        retry_middleware = RetryMiddleware(
            max_retries=2,
            initial_delay=0.1,
            backoff_strategy="exponential"
        )
        wrapped_chain = retry_middleware.wrap(mock_chain)
        
        start_time = time.time()
        with pytest.raises(Exception):
            await wrapped_chain.ainvoke({"input": "test"})
        elapsed = time.time() - start_time
        
        # Exponential backoff: 0.1초, 0.2초 대기
        # 최소 대기 시간 확인 (약간의 여유를 두고)
        assert elapsed > 0.25
        assert mock_chain.ainvoke.call_count == 3


class TestLoggingMiddleware:
    """Logging Middleware 테스트"""
    
    @pytest.mark.asyncio
    async def test_logging_middleware_basic(self, caplog):
        """기본 Logging 동작 테스트"""
        import logging
        caplog.set_level(logging.INFO)
        
        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(return_value="result")
        
        logging_middleware = LoggingMiddleware(
            log_level=logging.INFO,
            log_input=True,
            log_output=True,
            log_timing=True
        )
        wrapped_chain = logging_middleware.wrap(mock_chain, name="TestChain")
        
        result = await wrapped_chain.ainvoke({"input": "test"})
        
        assert result == "result"
        assert mock_chain.ainvoke.call_count == 1
        
        # 로그 확인
        log_messages = [record.message for record in caplog.records]
        assert any("[TestChain]" in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_logging_middleware_error(self, caplog):
        """에러 로깅 테스트"""
        import logging
        caplog.set_level(logging.ERROR)
        
        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(side_effect=Exception("Test error"))
        
        logging_middleware = LoggingMiddleware(
            log_level=logging.ERROR,
            log_timing=True
        )
        wrapped_chain = logging_middleware.wrap(mock_chain, name="TestChain")
        
        with pytest.raises(Exception, match="Test error"):
            await wrapped_chain.ainvoke({"input": "test"})
        
        # 에러 로그 확인
        error_logs = [record for record in caplog.records if record.levelno >= logging.ERROR]
        assert len(error_logs) > 0
        assert any("[TestChain]" in record.message for record in error_logs)


class TestMiddlewareIntegration:
    """Middleware 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_middleware_chain_order(self):
        """Middleware 적용 순서 테스트"""
        call_order = []
        
        # Mock Chain 생성
        async def mock_chain_func(inputs: Input, config=None):
            call_order.append("chain")
            return "result"
        
        mock_chain = Mock()
        mock_chain.ainvoke = AsyncMock(side_effect=mock_chain_func)
        
        # Middleware 생성 (순서 확인용)
        rate_limiter = RateLimitingMiddleware(max_calls=10, period=1.0)
        retry_middleware = RetryMiddleware(max_retries=1, initial_delay=0.01)
        logging_middleware = LoggingMiddleware()
        
        # Middleware 적용 (순서: Rate Limiting -> Retry -> Logging -> Chain)
        wrapped_chain = rate_limiter.wrap(
            retry_middleware.wrap(
                logging_middleware.wrap(mock_chain, name="TestChain")
            )
        )
        
        result = await wrapped_chain.ainvoke({"input": "test"})
        
        assert result == "result"
        assert "chain" in call_order
    
    @pytest.mark.asyncio
    async def test_middleware_with_actual_chain(self):
        """실제 Chain과 Middleware 통합 테스트"""
        # 간단한 Chain 생성
        async def add_one(inputs: Input):
            return inputs.get("value", 0) + 1
        
        chain = RunnableLambda(add_one)
        
        # Middleware 적용
        rate_limiter = RateLimitingMiddleware(max_calls=10, period=1.0)
        retry_middleware = RetryMiddleware(max_retries=1, initial_delay=0.01)
        logging_middleware = LoggingMiddleware()
        
        wrapped_chain = rate_limiter.wrap(
            retry_middleware.wrap(
                logging_middleware.wrap(chain, name="AddOneChain")
            )
        )
        
        result = await wrapped_chain.ainvoke({"value": 5})
        
        assert result == 6





