"""
Retry Middleware

Rate limit, timeout 등의 에러에 대해 자동 재시도를 수행합니다.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Tuple, Type

from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.runnables.utils import Input, Output

logger = logging.getLogger(__name__)


class RetryMiddleware:
    """
    Retry Middleware

    Rate limit, timeout 등의 에러에 대해 자동 재시도를 수행합니다.

    사용 예시:
        ```python
        retry_middleware = RetryMiddleware(
            max_retries=3,
            retry_exceptions=(RateLimitError, TimeoutError),
            backoff_strategy="exponential"
        )
        chain_with_retry = retry_middleware.wrap(chain)
        ```
    """

    def __init__(
        self,
        max_retries: int = 3,
        retry_exceptions: Tuple[Type[Exception], ...] = None,
        backoff_strategy: str = "exponential",
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        retry_condition: Optional[Callable[[Exception], bool]] = None,
    ):
        """
        Args:
            max_retries: 최대 재시도 횟수
            retry_exceptions: 재시도할 예외 타입 (기본값: Rate limit, Timeout 관련)
            backoff_strategy: 백오프 전략 ("exponential", "linear", "fixed")
            initial_delay: 초기 대기 시간 (초)
            max_delay: 최대 대기 시간 (초)
            retry_condition: 재시도 조건 함수 (예외를 받아 bool 반환)
        """
        self.max_retries = max_retries
        self.retry_exceptions = retry_exceptions or (Exception,)  # 기본값: 모든 예외
        self.backoff_strategy = backoff_strategy
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.retry_condition = retry_condition

    def _should_retry(self, exception: Exception, attempt: int) -> bool:
        """재시도 여부 판단"""
        # 최대 재시도 횟수 초과
        if attempt >= self.max_retries:
            return False

        # 재시도 조건 함수가 있으면 사용
        if self.retry_condition:
            return self.retry_condition(exception)

        # 예외 타입 체크
        if not isinstance(exception, self.retry_exceptions):
            # 예외 메시지로 Rate limit, Timeout 체크
            error_msg = str(exception).lower()
            if "rate" in error_msg or "quota" in error_msg or "timeout" in error_msg:
                return True
            return False

        return True

    def _calculate_delay(self, attempt: int) -> float:
        """백오프 전략에 따른 대기 시간 계산"""
        if self.backoff_strategy == "exponential":
            delay = self.initial_delay * (2**attempt)
        elif self.backoff_strategy == "linear":
            delay = self.initial_delay * (attempt + 1)
        elif self.backoff_strategy == "fixed":
            delay = self.initial_delay
        else:
            delay = self.initial_delay

        # 최대 대기 시간 제한
        return min(delay, self.max_delay)

    def wrap(self, chain: Runnable) -> Runnable:
        """
        Chain을 Retry Middleware로 래핑

        Args:
            chain: 래핑할 Chain

        Returns:
            Retry가 적용된 Chain
        """

        async def retry_chain(
            inputs: Input, config: Optional[RunnableConfig] = None
        ) -> Output:
            """재시도 로직이 적용된 Chain 실행"""
            last_exception = None

            for attempt in range(self.max_retries + 1):
                try:
                    result = await chain.ainvoke(inputs, config)
                    if attempt > 0:
                        logger.info(f"[Retry] 재시도 성공 - 시도 횟수: {attempt + 1}")
                    return result

                except Exception as e:
                    last_exception = e

                    if not self._should_retry(e, attempt):
                        logger.error(
                            f"[Retry] 재시도 중단 - 시도 횟수: {attempt + 1}, 에러: {str(e)}"
                        )
                        raise

                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"[Retry] 재시도 대기 - 시도 횟수: {attempt + 1}/{self.max_retries + 1}, "
                        f"대기 시간: {delay:.2f}초, 에러: {str(e)[:100]}"
                    )

                    await asyncio.sleep(delay)

            # 모든 재시도 실패
            logger.error(f"[Retry] 모든 재시도 실패 - 최종 에러: {str(last_exception)}")
            raise last_exception

        # Runnable 인터페이스 구현
        class RetryRunnable(Runnable):
            def __init__(self, chain: Runnable, middleware: "RetryMiddleware"):
                self.chain = chain
                self.middleware = middleware

            async def ainvoke(
                self, inputs: Input, config: Optional[RunnableConfig] = None
            ) -> Output:
                return await retry_chain(inputs, config)

            def invoke(
                self, inputs: Input, config: Optional[RunnableConfig] = None
            ) -> Output:
                # 동기 호출은 지원하지 않음 (비동기 전용)
                raise NotImplementedError("RetryMiddleware는 비동기 호출만 지원합니다.")

        return RetryRunnable(chain, self)

    def __call__(self, chain: Runnable) -> Runnable:
        """직접 호출 가능하도록 지원"""
        return self.wrap(chain)
