"""
LangSmith 추적 유틸리티
State 기반으로 LangSmith 추적을 제어합니다.

[구조]
- 상수: LangSmith 관련 설정 상수
- 유틸리티 함수: 추적 활성화/비활성화 제어
- 래퍼 함수: 노드 함수를 LangSmith 추적과 함께 실행
"""

import logging
import os
from functools import wraps
from typing import Any, Callable, Dict, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# ===== 상수 =====

# LangSmith 추적 태그
TAG_EVALUATION = "evaluation"
TAG_NODE_6A = "node_6a"
TAG_NODE_6C = "node_6c"
TAG_NODE_6D = "node_6d"
TAG_HOLISTIC = "holistic"
TAG_CHAINING = "chaining"
TAG_PERFORMANCE = "performance"
TAG_CORRECTNESS = "correctness"
TAG_CODE = "code"

# 노드별 추적 이름
TRACE_NAME_HOLISTIC_FLOW = "eval_holistic_flow"
TRACE_NAME_CODE_PERFORMANCE = "eval_code_performance"  # deprecated
TRACE_NAME_CODE_CORRECTNESS = "eval_code_correctness"  # deprecated
TRACE_NAME_CODE_EXECUTION = "eval_code_execution"  # 새로운 통합 노드

# 노드별 태그 설정
NODE_TAGS = {
    TRACE_NAME_HOLISTIC_FLOW: [TAG_EVALUATION, TAG_NODE_6A, TAG_HOLISTIC, TAG_CHAINING],
    TRACE_NAME_CODE_PERFORMANCE: [
        TAG_EVALUATION,
        TAG_NODE_6C,
        TAG_PERFORMANCE,
        TAG_CODE,
    ],  # deprecated
    TRACE_NAME_CODE_CORRECTNESS: [
        TAG_EVALUATION,
        TAG_NODE_6D,
        TAG_CORRECTNESS,
        TAG_CODE,
    ],  # deprecated
    TRACE_NAME_CODE_EXECUTION: [
        TAG_EVALUATION,
        TAG_NODE_6C,
        TAG_PERFORMANCE,
        TAG_CORRECTNESS,
        TAG_CODE,
    ],
}


def should_enable_langsmith(state: Optional[dict] = None) -> bool:
    """
    LangSmith 추적 활성화 여부 결정

    우선순위:
    1. State의 enable_langsmith_tracing (명시적 설정)
    2. 환경 변수 LANGCHAIN_TRACING_V2 (기본값)

    Args:
        state: MainGraphState (Optional)

    Returns:
        bool: LangSmith 추적 활성화 여부
    """
    # State에서 명시적으로 설정된 경우
    if state and "enable_langsmith_tracing" in state:
        enable = state.get("enable_langsmith_tracing")
        if enable is not None:
            return bool(enable)

    # 환경 변수 기본값 사용
    return bool(settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY)


def get_traceable_decorator(state: Optional[dict] = None):
    """
    LangSmith traceable 데코레이터 반환

    Args:
        state: MainGraphState (Optional)

    Returns:
        traceable 데코레이터 또는 더미 데코레이터
    """
    if should_enable_langsmith(state):
        try:
            from langsmith import traceable

            # 환경 변수 설정 (LangSmith 자동 인식)
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
            os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
            os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT

            return traceable
        except ImportError:
            logger.warning("[LangSmith] langsmith 패키지가 설치되지 않았습니다.")
            return _dummy_traceable
    else:
        return _dummy_traceable


def _dummy_traceable(*args, **kwargs):
    """LangSmith 비활성화 시 사용하는 더미 데코레이터"""

    def decorator(func: Callable) -> Callable:
        return func

    return decorator


# ===== 유틸리티 함수 =====


def create_conditional_traceable(
    name: str, tags: list[str], state: Optional[dict] = None
) -> Callable:
    """
    조건부 traceable 데코레이터 생성

    Args:
        name: 추적 이름
        tags: 추적 태그
        state: MainGraphState (Optional)

    Returns:
        데코레이터 함수 (함수에 적용 가능)
        예: traced_func = create_conditional_traceable(...)(original_func)
    """
    traceable_decorator = get_traceable_decorator(state)

    # traceable 데코레이터를 설정과 함께 반환
    if should_enable_langsmith(state):
        return traceable_decorator(
            name=name, tags=tags, project_name=settings.LANGCHAIN_PROJECT
        )
    else:
        return _dummy_traceable()


def wrap_node_with_tracing(
    node_name: str, impl_func: Callable, state: Dict[str, Any]
) -> Callable:
    """
    노드 함수를 LangSmith 추적과 함께 래핑

    Args:
        node_name: 노드 이름 (TRACE_NAME_* 상수 사용)
        impl_func: 내부 구현 함수
        state: MainGraphState

    Returns:
        래핑된 함수 (호출 가능)
    """
    if should_enable_langsmith(state):
        # 추적 활성화: 래핑된 함수 사용
        tags = NODE_TAGS.get(node_name, [TAG_EVALUATION])
        traceable_decorator = create_conditional_traceable(
            name=node_name, tags=tags, state=state
        )
        traced_func = traceable_decorator(impl_func)
        return traced_func
    else:
        # 추적 비활성화: 원본 함수 사용
        return impl_func
