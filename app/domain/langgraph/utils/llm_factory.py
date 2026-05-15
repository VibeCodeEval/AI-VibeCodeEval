"""
LLM Factory Pattern
여러 LLM 타입을 지원하고, 노드별 설정을 관리하는 Factory

[목적]
- 여러 LLM 타입 지원 (Gemini, OpenAI, Claude 등)
- 노드별로 다른 LLM 설정 사용 가능
- 인스턴스 재사용 (싱글톤 패턴)
- 확장 가능한 구조
"""

import logging
from functools import lru_cache
from typing import Any, Dict, Literal, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai import ChatVertexAI
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.vertex_auth import load_vertex_credentials, resolve_vertex_project_id

# from langchain_anthropic import ChatAnthropic  # 필요시 추가


logger = logging.getLogger(__name__)

# LLM 타입 정의
LLMType = Literal["gemini", "openai", "anthropic"]

# 노드별 기본 설정
NODE_DEFAULT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "intent_analyzer": {
        "llm_type": "gemini",
        "temperature": 0.3,
        "model": settings.DEFAULT_LLM_MODEL,
    },
    "writer": {
        "llm_type": "gemini",
        "temperature": getattr(settings, "LLM_TEMPERATURE", 0.7),
        "model": settings.DEFAULT_LLM_MODEL,
        "max_tokens": getattr(settings, "LLM_MAX_TOKENS", None),
    },
    "turn_evaluator": {
        "llm_type": "gemini",
        "temperature": 0.1,
        "model": settings.DEFAULT_LLM_MODEL,
    },
    "holistic_evaluator": {
        "llm_type": "gemini",
        "temperature": 0.1,
        "model": settings.DEFAULT_LLM_MODEL,
    },
    "system_nodes": {
        "llm_type": "gemini",
        "temperature": 0.3,
        "model": settings.DEFAULT_LLM_MODEL,
    },
}

# LLM 인스턴스 캐시 (노드별 + 설정별)
_llm_cache: Dict[str, Any] = {}


def _create_cache_key(node_name: str, llm_type: str, **kwargs) -> str:
    """캐시 키 생성"""
    # 설정값을 포함한 고유 키 생성
    config_str = "_".join(
        f"{k}:{v}" for k, v in sorted(kwargs.items()) if v is not None
    )
    return f"{node_name}_{llm_type}_{config_str}"


def create_gemini_llm(
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_output_tokens: Optional[int] = None,
    api_key: Optional[str] = None,
) -> Any:
    """
    Gemini 호출용 LLM (USE_VERTEX_AI 시 Vertex, 아니면 AI Studio API Key).
    """
    selected_model = model or settings.DEFAULT_LLM_MODEL

    if settings.USE_VERTEX_AI:
        return ChatVertexAI(
            model=selected_model,
            project=resolve_vertex_project_id(),
            location=settings.GOOGLE_LOCATION,
            credentials=load_vertex_credentials(),
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    thinking_budget = settings.LLM_THINKING_BUDGET
    # gemini-2.5-pro 계열은 thinking 모드가 필수인 경우가 있어
    # budget=0을 강제하면 400(Budget 0 is invalid) 오류가 발생할 수 있음.
    if (
        isinstance(selected_model, str)
        and "gemini-2.5-pro" in selected_model.lower()
        and thinking_budget == 0
    ):
        thinking_budget = None

    return ChatGoogleGenerativeAI(
        model=selected_model,
        google_api_key=api_key or settings.GEMINI_API_KEY,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        thinking_budget=thinking_budget,
        timeout=settings.LLM_REQUEST_TIMEOUT,
    )


def _create_gemini_llm(**kwargs) -> Any:
    """Gemini LLM 생성 (Vertex 또는 AI Studio)"""
    return create_gemini_llm(
        model=kwargs.get("model"),
        temperature=kwargs.get("temperature", 0.3),
        max_output_tokens=kwargs.get("max_tokens"),
        api_key=kwargs.get("api_key"),
    )


def _create_openai_llm(**kwargs) -> ChatOpenAI:
    """OpenAI LLM 생성"""
    return ChatOpenAI(
        model=kwargs.get("model", "gpt-4"),
        api_key=kwargs.get("api_key", getattr(settings, "OPENAI_API_KEY", None)),
        temperature=kwargs.get("temperature", 0.3),
        max_tokens=kwargs.get("max_tokens"),
    )


# def _create_anthropic_llm(**kwargs) -> ChatAnthropic:
#     """Anthropic LLM 생성"""
#     return ChatAnthropic(
#         model=kwargs.get("model", "claude-3-opus-20240229"),
#         api_key=kwargs.get("api_key", getattr(settings, "ANTHROPIC_API_KEY", None)),
#         temperature=kwargs.get("temperature", 0.3),
#         max_tokens=kwargs.get("max_tokens"),
#     )


def get_llm(
    node_name: str,
    llm_type: Optional[LLMType] = None,
    temperature: Optional[float] = None,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    api_key: Optional[str] = None,
    **kwargs,
) -> Any:
    """
    노드별 LLM 인스턴스 생성 (싱글톤 패턴)

    Args:
        node_name: 노드 이름 (예: "intent_analyzer", "writer")
        llm_type: LLM 타입 ("gemini", "openai", "anthropic")
        temperature: 온도 설정 (노드 기본값 사용)
        model: 모델 이름 (노드 기본값 사용)
        max_tokens: 최대 토큰 수
        api_key: API 키 (설정에서 자동으로 가져옴)
        **kwargs: 추가 설정

    Returns:
        캐싱된 LLM 인스턴스

    Examples:
        # 기본 사용 (노드 기본 설정 사용)
        llm = get_llm("intent_analyzer")

        # 커스텀 설정
        llm = get_llm("writer", temperature=0.9, max_tokens=2000)

        # 다른 LLM 타입 사용
        llm = get_llm("writer", llm_type="openai", model="gpt-4")
    """
    # 노드 기본 설정 가져오기
    node_config = NODE_DEFAULT_CONFIGS.get(node_name, {})

    # 설정 병합 (인자 > 노드 기본값)
    final_config = {
        "llm_type": llm_type or node_config.get("llm_type", "gemini"),
        "temperature": (
            temperature
            if temperature is not None
            else node_config.get("temperature", 0.3)
        ),
        "model": model or node_config.get("model", settings.DEFAULT_LLM_MODEL),
        "max_tokens": (
            max_tokens if max_tokens is not None else node_config.get("max_tokens")
        ),
        "api_key": api_key,  # None이면 각 LLM 생성 함수에서 설정에서 가져옴
        **kwargs,
    }

    # 캐시 키 생성
    cache_key = _create_cache_key(node_name, **final_config)

    # 캐시에 있으면 재사용
    if cache_key in _llm_cache:
        logger.debug(
            f"[LLM Factory] 캐시된 LLM 재사용 - node: {node_name}, key: {cache_key}"
        )
        return _llm_cache[cache_key]

    # 새 LLM 인스턴스 생성
    llm_type = final_config["llm_type"]

    if llm_type == "gemini":
        llm = _create_gemini_llm(**final_config)
    elif llm_type == "openai":
        llm = _create_openai_llm(**final_config)
    # elif llm_type == "anthropic":
    #     llm = _create_anthropic_llm(**final_config)
    else:
        raise ValueError(f"지원하지 않는 LLM 타입: {llm_type}")

    # 캐시에 저장
    _llm_cache[cache_key] = llm
    logger.debug(
        f"[LLM Factory] 새 LLM 인스턴스 생성 - node: {node_name}, type: {llm_type}, key: {cache_key}"
    )

    return llm


def clear_llm_cache():
    """LLM 캐시 초기화 (테스트용)"""
    global _llm_cache
    _llm_cache.clear()
    logger.info("[LLM Factory] LLM 캐시 초기화 완료")


def get_cache_info() -> Dict[str, Any]:
    """캐시 정보 반환 (디버깅용)"""
    return {
        "cache_size": len(_llm_cache),
        "cached_keys": list(_llm_cache.keys()),
    }
