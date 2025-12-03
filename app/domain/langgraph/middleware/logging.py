"""
Logging Middleware

Chain 실행 전후로 일관된 로깅을 제공합니다.
"""

import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.runnables.utils import Input, Output

logger = logging.getLogger(__name__)


class LoggingMiddleware:
    """
    Logging Middleware
    
    Chain 실행 전후로 일관된 로깅을 제공합니다.
    
    사용 예시:
        ```python
        logging_middleware = LoggingMiddleware(
            log_level=logging.INFO,
            log_input=True,
            log_output=True
        )
        chain_with_logging = logging_middleware.wrap(chain)
        ```
    """
    
    def __init__(
        self,
        log_level: int = logging.INFO,
        log_input: bool = True,
        log_output: bool = True,
        log_timing: bool = True,
        input_truncate_length: int = 100,
        output_truncate_length: int = 100
    ):
        """
        Args:
            log_level: 로그 레벨
            log_input: 입력 로깅 여부
            log_output: 출력 로깅 여부
            log_timing: 실행 시간 로깅 여부
            input_truncate_length: 입력 로그 최대 길이
            output_truncate_length: 출력 로그 최대 길이
        """
        self.log_level = log_level
        self.log_input = log_input
        self.log_output = log_output
        self.log_timing = log_timing
        self.input_truncate_length = input_truncate_length
        self.output_truncate_length = output_truncate_length
    
    def _truncate(self, value: Any, max_length: int) -> str:
        """값을 문자열로 변환하고 길이 제한"""
        str_value = str(value)
        if len(str_value) > max_length:
            return str_value[:max_length] + "..."
        return str_value
    
    def wrap(self, chain: Runnable, name: str = "Chain") -> Runnable:
        """
        Chain을 Logging Middleware로 래핑
        
        Args:
            chain: 래핑할 Chain
            name: Chain 이름 (로깅용)
            
        Returns:
            Logging이 적용된 Chain
        """
        async def logged_chain(inputs: Input, config: Optional[RunnableConfig] = None) -> Output:
            """로깅이 적용된 Chain 실행"""
            start_time = time.time()
            
            # 입력 로깅
            if self.log_input:
                input_str = self._truncate(inputs, self.input_truncate_length)
                logger.log(
                    self.log_level,
                    f"[{name}] 입력 - {input_str}"
                )
            
            try:
                # Chain 실행
                result = await chain.ainvoke(inputs, config)
                
                # 실행 시간 계산
                elapsed_time = time.time() - start_time
                
                # 출력 로깅
                if self.log_output:
                    output_str = self._truncate(result, self.output_truncate_length)
                    logger.log(
                        self.log_level,
                        f"[{name}] 출력 - {output_str}"
                    )
                
                # 실행 시간 로깅
                if self.log_timing:
                    logger.log(
                        self.log_level,
                        f"[{name}] 실행 시간 - {elapsed_time:.3f}초"
                    )
                
                return result
            
            except Exception as e:
                # 에러 로깅
                elapsed_time = time.time() - start_time
                logger.error(
                    f"[{name}] 에러 발생 - 실행 시간: {elapsed_time:.3f}초, "
                    f"에러: {str(e)}",
                    exc_info=True
                )
                raise
        
        # Runnable 인터페이스 구현
        class LoggedRunnable(Runnable):
            def __init__(self, chain: Runnable, middleware: 'LoggingMiddleware', name: str):
                self.chain = chain
                self.middleware = middleware
                self.name = name
            
            async def ainvoke(self, inputs: Input, config: Optional[RunnableConfig] = None) -> Output:
                return await logged_chain(inputs, config)
            
            def invoke(self, inputs: Input, config: Optional[RunnableConfig] = None) -> Output:
                # 동기 호출은 지원하지 않음 (비동기 전용)
                raise NotImplementedError("LoggingMiddleware는 비동기 호출만 지원합니다.")
        
        return LoggedRunnable(chain, self, name)
    
    def __call__(self, chain: Runnable, name: str = "Chain") -> Runnable:
        """직접 호출 가능하도록 지원"""
        return self.wrap(chain, name)


