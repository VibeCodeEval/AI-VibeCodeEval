"""
Rate Limiting Middleware

LLM 호출 전에 Rate Limit을 체크하여 비용을 절감합니다.
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional
from collections import defaultdict
from datetime import datetime, timedelta

from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.runnables.utils import Input, Output

logger = logging.getLogger(__name__)


class RateLimitingMiddleware:
    """
    Rate Limiting Middleware
    
    LLM 호출 전에 Rate Limit을 체크하여 비용을 절감합니다.
    
    사용 예시:
        ```python
        rate_limiter = RateLimitingMiddleware(max_calls=15, period=60.0)
        chain_with_rate_limit = rate_limiter.wrap(chain)
        ```
    """
    
    def __init__(
        self,
        max_calls: int = 15,
        period: float = 60.0,
        key_func: Optional[callable] = None
    ):
        """
        Args:
            max_calls: 주어진 기간 내 최대 호출 횟수
            period: 기간 (초)
            key_func: Rate limit 키를 생성하는 함수 (기본값: None - 전역 제한)
        """
        self.max_calls = max_calls
        self.period = period
        self.key_func = key_func
        
        # 호출 기록: {key: [timestamp1, timestamp2, ...]}
        self._call_history: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    def _get_key(self, inputs: Input) -> str:
        """Rate limit 키 생성"""
        if self.key_func:
            return str(self.key_func(inputs))
        return "global"
    
    def _clean_old_calls(self, key: str, now: float):
        """오래된 호출 기록 제거"""
        cutoff_time = now - self.period
        self._call_history[key] = [
            timestamp for timestamp in self._call_history[key]
            if timestamp > cutoff_time
        ]
    
    async def _check_rate_limit(self, key: str) -> float:
        """
        Rate limit 체크 및 대기 시간 계산
        
        Returns:
            대기 시간 (초)
        """
        async with self._lock:
            now = time.time()
            self._clean_old_calls(key, now)
            
            current_calls = len(self._call_history[key])
            
            if current_calls >= self.max_calls:
                # 가장 오래된 호출이 만료될 때까지 대기
                oldest_call = min(self._call_history[key])
                wait_time = self.period - (now - oldest_call)
                
                if wait_time > 0:
                    logger.warning(
                        f"[Rate Limiting] Rate limit 초과 - 대기 시간: {wait_time:.2f}초 "
                        f"(현재: {current_calls}/{self.max_calls} 호출)"
                    )
                    return wait_time
            
            # 호출 기록 추가
            self._call_history[key].append(now)
            return 0.0
    
    def wrap(self, chain: Runnable) -> Runnable:
        """
        Chain을 Rate Limiting Middleware로 래핑
        
        Args:
            chain: 래핑할 Chain
            
        Returns:
            Rate Limiting이 적용된 Chain
        """
        async def rate_limited_chain(inputs: Input, config: Optional[RunnableConfig] = None) -> Output:
            """Rate limit 체크 후 Chain 실행"""
            key = self._get_key(inputs)
            wait_time = await self._check_rate_limit(key)
            
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            
            return await chain.ainvoke(inputs, config)
        
        # Runnable 인터페이스 구현
        class RateLimitedRunnable(Runnable):
            def __init__(self, chain: Runnable, middleware: 'RateLimitingMiddleware'):
                self.chain = chain
                self.middleware = middleware
            
            async def ainvoke(self, inputs: Input, config: Optional[RunnableConfig] = None) -> Output:
                return await rate_limited_chain(inputs, config)
            
            def invoke(self, inputs: Input, config: Optional[RunnableConfig] = None) -> Output:
                # 동기 호출은 지원하지 않음 (비동기 전용)
                raise NotImplementedError("RateLimitingMiddleware는 비동기 호출만 지원합니다.")
        
        return RateLimitedRunnable(chain, self)
    
    def __call__(self, chain: Runnable) -> Runnable:
        """직접 호출 가능하도록 지원"""
        return self.wrap(chain)


