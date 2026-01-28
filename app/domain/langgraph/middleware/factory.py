"""
Middleware Factory
Middleware 생성 및 Chain 래핑을 위한 공통 함수
"""

import logging
from typing import Tuple

from langchain_core.runnables import Runnable

from app.core.config import settings
from app.domain.langgraph.middleware.logging import LoggingMiddleware
from app.domain.langgraph.middleware.rate_limiting import RateLimitingMiddleware
from app.domain.langgraph.middleware.retry import RetryMiddleware


def create_middleware_stack() -> (
    Tuple[RateLimitingMiddleware, RetryMiddleware, LoggingMiddleware]
):
    """
    Middleware 스택 생성 (공통)

    Returns:
        (RateLimitingMiddleware, RetryMiddleware, LoggingMiddleware) 튜플
    """
    rate_limiter = RateLimitingMiddleware(
        max_calls=settings.MIDDLEWARE_RATE_LIMIT_MAX_CALLS,
        period=settings.MIDDLEWARE_RATE_LIMIT_PERIOD,
    )

    retry_middleware = RetryMiddleware(
        max_retries=settings.MIDDLEWARE_RETRY_MAX_RETRIES,
        initial_delay=settings.MIDDLEWARE_RETRY_INITIAL_DELAY,
        max_delay=settings.MIDDLEWARE_RETRY_MAX_DELAY,
        backoff_strategy=settings.MIDDLEWARE_RETRY_BACKOFF_STRATEGY,
    )

    logging_middleware = LoggingMiddleware(
        log_level=(
            logging.INFO if settings.MIDDLEWARE_LOGGING_ENABLED else logging.DEBUG
        ),
        log_input=True,
        log_output=True,
        log_timing=True,
    )

    return rate_limiter, retry_middleware, logging_middleware


def wrap_chain_with_middleware(chain: Runnable, name: str = "Chain") -> Runnable:
    """
    Chain에 Middleware 적용 (공통)

    적용 순서: Rate Limiting -> Retry -> Logging -> Chain

    Args:
        chain: 래핑할 Chain
        name: Chain 이름 (로깅용)

    Returns:
        Middleware가 적용된 Chain
    """
    rate_limiter, retry_middleware, logging_middleware = create_middleware_stack()

    return rate_limiter.wrap(
        retry_middleware.wrap(logging_middleware.wrap(chain, name=name))
    )
