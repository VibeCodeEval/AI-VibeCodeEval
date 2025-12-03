"""
Middleware 사용 예시

이 파일은 Middleware를 Chain에 적용하는 방법을 보여줍니다.
실제 노드에 적용할 때는 이 예시를 참고하여 구현하세요.
"""

import logging
from langchain_core.runnables import RunnableLambda
from langchain_core.prompts import ChatPromptTemplate

from app.domain.langgraph.middleware import (
    RateLimitingMiddleware,
    RetryMiddleware,
    LoggingMiddleware
)


# ===== 예시 1: Intent Analyzer Chain에 Middleware 적용 =====

def example_intent_analyzer_with_middleware():
    """
    Intent Analyzer Chain에 Middleware 적용 예시
    
    적용 순서:
    1. Rate Limiting (LLM 호출 전)
    2. Retry (에러 발생 시)
    3. Logging (실행 전후)
    """
    from app.domain.langgraph.nodes.intent_analyzer import (
        intent_analysis_prompt,
        get_llm,
        IntentAnalysisResult
    )
    
    # 1. 기본 Chain 구성
    llm = get_llm()
    structured_llm = llm.with_structured_output(IntentAnalysisResult)
    
    base_chain = (
        intent_analysis_prompt
        | structured_llm
    )
    
    # 2. Middleware 적용
    rate_limiter = RateLimitingMiddleware(max_calls=15, period=60.0)
    retry_middleware = RetryMiddleware(
        max_retries=3,
        backoff_strategy="exponential",
        initial_delay=1.0
    )
    logging_middleware = LoggingMiddleware(
        log_level=logging.INFO,
        log_input=True,
        log_output=True,
        log_timing=True
    )
    
    # 3. Middleware를 Chain에 적용 (순서 중요!)
    # Rate Limiting -> Retry -> Logging -> Chain
    chain_with_middleware = (
        rate_limiter.wrap(
            retry_middleware.wrap(
                logging_middleware.wrap(base_chain, name="Intent Analyzer")
            )
        )
    )
    
    return chain_with_middleware


# ===== 예시 2: Writer Chain에 Middleware 적용 =====

def example_writer_with_middleware():
    """
    Writer Chain에 Middleware 적용 예시
    """
    from app.domain.langgraph.nodes.writer import (
        prepare_writer_input,
        format_writer_messages,
        get_llm
    )
    from langchain_core.runnables import RunnableLambda
    
    # 1. 기본 Chain 구성
    llm = get_llm()
    
    base_chain = (
        RunnableLambda(prepare_writer_input)
        | RunnableLambda(format_writer_messages)
        | llm
        | RunnableLambda(lambda x: x.content if hasattr(x, 'content') else str(x))
    )
    
    # 2. Middleware 적용
    rate_limiter = RateLimitingMiddleware(max_calls=15, period=60.0)
    retry_middleware = RetryMiddleware(
        max_retries=3,
        backoff_strategy="exponential"
    )
    logging_middleware = LoggingMiddleware(name="Writer LLM")
    
    # 3. Middleware를 Chain에 적용
    chain_with_middleware = (
        rate_limiter.wrap(
            retry_middleware.wrap(
                logging_middleware.wrap(base_chain, name="Writer LLM")
            )
        )
    )
    
    return chain_with_middleware


# ===== 예시 3: 간단한 사용법 (함수형) =====

def example_simple_usage():
    """
    간단한 사용법 - 함수형으로 Middleware 적용
    """
    from app.domain.langgraph.nodes.intent_analyzer import intent_analysis_chain
    
    # Middleware 생성
    rate_limiter = RateLimitingMiddleware(max_calls=15, period=60.0)
    retry_middleware = RetryMiddleware(max_retries=3)
    logging_middleware = LoggingMiddleware(name="Intent Analyzer")
    
    # Chain에 Middleware 적용 (체이닝)
    chain_with_middleware = rate_limiter(
        retry_middleware(
            logging_middleware(intent_analysis_chain, name="Intent Analyzer")
        )
    )
    
    return chain_with_middleware


# ===== 예시 4: 조건부 Middleware 적용 =====

def example_conditional_middleware(enable_rate_limiting: bool = True):
    """
    조건부로 Middleware 적용
    """
    from app.domain.langgraph.nodes.intent_analyzer import intent_analysis_chain
    
    chain = intent_analysis_chain
    
    # Rate Limiting은 조건부로 적용
    if enable_rate_limiting:
        rate_limiter = RateLimitingMiddleware(max_calls=15, period=60.0)
        chain = rate_limiter.wrap(chain)
    
    # Retry와 Logging은 항상 적용
    retry_middleware = RetryMiddleware(max_retries=3)
    logging_middleware = LoggingMiddleware(name="Intent Analyzer")
    
    chain = retry_middleware.wrap(chain)
    chain = logging_middleware.wrap(chain, name="Intent Analyzer")
    
    return chain


# ===== 실제 사용 예시 (노드 함수에서) =====

async def example_node_function_with_middleware(state):
    """
    실제 노드 함수에서 Middleware 사용 예시
    """
    from app.domain.langgraph.nodes.intent_analyzer import (
        prepare_input,
        intent_analysis_prompt,
        get_llm,
        IntentAnalysisResult,
        process_output
    )
    from langchain_core.runnables import RunnableLambda
    
    # 1. 기본 Chain 구성
    llm = get_llm()
    structured_llm = llm.with_structured_output(IntentAnalysisResult)
    
    base_chain = (
        RunnableLambda(prepare_input)
        | intent_analysis_prompt
        | structured_llm
        | RunnableLambda(process_output)
    )
    
    # 2. Middleware 적용
    rate_limiter = RateLimitingMiddleware(max_calls=15, period=60.0)
    retry_middleware = RetryMiddleware(max_retries=3)
    logging_middleware = LoggingMiddleware(name="Intent Analyzer")
    
    chain_with_middleware = rate_limiter.wrap(
        retry_middleware.wrap(
            logging_middleware.wrap(base_chain, name="Intent Analyzer")
        )
    )
    
    # 3. Chain 실행
    human_message = state.get("human_message", "")
    result = await chain_with_middleware.ainvoke({
        "human_message": human_message
    })
    
    return result

