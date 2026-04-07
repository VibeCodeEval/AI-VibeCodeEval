"""
토큰 사용량 추적 유틸리티

[목적]
- LLM 응답에서 토큰 사용량 추출
- 채팅 검사 토큰과 평가 토큰 분리 추적
- State에 누적 저장
- Core 백엔드로 전달할 형식으로 변환
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def estimate_user_text_tokens(text: str) -> int:
    """
    사용자 작성 텍스트만 대략적인 토큰 수 추정 (시스템 프롬프트 제외용).
    API 라우트의 SendMessages와 동일하게 cl100k_base 사용.
    """
    if not text or not str(text).strip():
        return 0
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(str(text)))
    except Exception as e:
        logger.warning(
            f"[Token Tracking] tiktoken 추정 실패, 문자 길이 기반 대체: {e}"
        )
        return max(1, len(str(text)) // 3)


def extract_token_usage(response: Any) -> Optional[Dict[str, int]]:
    """
    LLM 응답에서 토큰 사용량 추출

    [LangChain 응답 구조]
    - response.response_metadata.get("usage_metadata")
    - 또는 response.usage_metadata (직접 접근)

    Args:
        response: LangChain LLM 응답 객체

    Returns:
        {
            "prompt_tokens": int,
            "completion_tokens": int,
            "total_tokens": int
        } 또는 None
    """
    try:
        # Gemini API의 실제 키 이름 사용
        # usage_metadata: {'input_tokens': 13, 'output_tokens': 22, 'total_tokens': 35, ...}

        # 방법 1: 직접 usage_metadata 속성 접근 (Gemini API)
        if hasattr(response, "usage_metadata"):
            usage = response.usage_metadata
            if usage:
                # dict인 경우
                if isinstance(usage, dict):
                    logger.debug(
                        f"[Token Tracking] usage_metadata 발견 (dict) - {usage}"
                    )
                    return {
                        "prompt_tokens": usage.get("input_tokens", 0),
                        "completion_tokens": usage.get("output_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    }
                else:
                    # 객체인 경우
                    logger.debug(
                        f"[Token Tracking] usage_metadata 발견 (객체) - {usage}"
                    )
                    return {
                        "prompt_tokens": getattr(usage, "input_tokens", 0) or 0,
                        "completion_tokens": getattr(usage, "output_tokens", 0) or 0,
                        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
                    }

        # 방법 2: response_metadata에서 추출 (다른 LLM용)
        if hasattr(response, "response_metadata"):
            metadata = response.response_metadata
            if metadata:
                # dict인 경우
                if isinstance(metadata, dict):
                    usage = metadata.get("usage_metadata")
                    if usage:
                        # Gemini 형식
                        if "input_tokens" in usage or "output_tokens" in usage:
                            return {
                                "prompt_tokens": usage.get("input_tokens", 0),
                                "completion_tokens": usage.get("output_tokens", 0),
                                "total_tokens": usage.get("total_tokens", 0),
                            }
                        # 다른 형식 (OpenAI 등)
                        return {
                            "prompt_tokens": usage.get(
                                "prompt_token_count", usage.get("prompt_tokens", 0)
                            ),
                            "completion_tokens": usage.get(
                                "candidates_token_count",
                                usage.get("completion_tokens", 0),
                            ),
                            "total_tokens": usage.get(
                                "total_token_count", usage.get("total_tokens", 0)
                            ),
                        }

        # 방법 3: dict 형태의 response
        if isinstance(response, dict):
            usage = response.get("usage_metadata", {})
            if usage:
                return {
                    "prompt_tokens": usage.get(
                        "input_tokens", usage.get("prompt_tokens", 0)
                    ),
                    "completion_tokens": usage.get(
                        "output_tokens", usage.get("completion_tokens", 0)
                    ),
                    "total_tokens": usage.get("total_tokens", 0),
                }

        # 방법 4: response_metadata 최상위 키 직접 탐색 (Gemini AI Studio 변형)
        if hasattr(response, "response_metadata"):
            metadata = response.response_metadata
            if isinstance(metadata, dict):
                # Gemini가 usage_metadata 대신 최상위에 token count 키를 두는 경우
                prompt_tokens = (
                    metadata.get("prompt_token_count")
                    or metadata.get("input_tokens")
                    or metadata.get("prompt_tokens")
                    or 0
                )
                completion_tokens = (
                    metadata.get("candidates_token_count")
                    or metadata.get("output_tokens")
                    or metadata.get("completion_tokens")
                    or 0
                )
                total_tokens = (
                    metadata.get("total_token_count")
                    or metadata.get("total_tokens")
                    or (prompt_tokens + completion_tokens)
                )
                if prompt_tokens or completion_tokens:
                    logger.debug(
                        f"[Token Tracking] 방법 4(response_metadata 직접 탐색)로 추출: "
                        f"prompt={prompt_tokens}, completion={completion_tokens}"
                    )
                    return {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                    }

        logger.warning(
            f"[Token Tracking] 토큰 사용량 추출 실패 - response 타입: {type(response)}, "
            f"usage_metadata: {getattr(response, 'usage_metadata', 'N/A')}, "
            f"response_metadata keys: {list(getattr(response, 'response_metadata', {}).keys()) if hasattr(response, 'response_metadata') else 'N/A'}"
        )
        return None

    except Exception as e:
        logger.warning(f"[Token Tracking] 토큰 사용량 추출 중 오류: {str(e)}")
        return None


def accumulate_tokens(
    state: Dict[str, Any],
    new_tokens: Optional[Dict[str, int]],
    token_type: str = "chat",  # "chat" 또는 "eval"
    *,
    chat_prompt_token_override: Optional[int] = None,
) -> Dict[str, Any]:
    """
    State에 토큰 사용량 누적

    Args:
        state: MainGraphState 또는 EvalTurnState
        new_tokens: 새로 추출한 토큰 사용량
        token_type: "chat" (채팅 검사) 또는 "eval" (평가)
        chat_prompt_token_override: chat일 때만 사용. 지정 시 API의 input(prompt) 대신
            이 값을 이번 호출의 prompt_tokens로 누적 (시스템 프롬프트 제외·사용자 문장만 반영).

    Returns:
        업데이트된 State (토큰 누적)
    """
    if not new_tokens:
        return state

    merged = dict(new_tokens)
    if token_type == "chat" and chat_prompt_token_override is not None:
        ct = int(new_tokens.get("completion_tokens", 0) or 0)
        pt = int(chat_prompt_token_override)
        merged["prompt_tokens"] = pt
        merged["completion_tokens"] = ct
        merged["total_tokens"] = pt + ct

    # 기존 토큰 사용량 가져오기
    if token_type == "chat":
        existing = state.get("chat_tokens", {}) or {}
    else:  # eval
        existing = state.get("eval_tokens", {}) or {}

    # 누적
    accumulated = {
        "prompt_tokens": existing.get("prompt_tokens", 0)
        + merged.get("prompt_tokens", 0),
        "completion_tokens": existing.get("completion_tokens", 0)
        + merged.get("completion_tokens", 0),
        "total_tokens": existing.get("total_tokens", 0)
        + merged.get("total_tokens", 0),
    }

    # State 업데이트
    if token_type == "chat":
        state["chat_tokens"] = accumulated
    else:  # eval
        state["eval_tokens"] = accumulated

    logger.debug(
        f"[Token Tracking] 토큰 누적 완료 - type: {token_type}, accumulated: {accumulated}"
    )

    return state


def get_token_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    State에서 토큰 사용량 요약 반환

    Args:
        state: MainGraphState 또는 EvalTurnState

    Returns:
        {
            "chat_tokens": {...},
            "eval_tokens": {...}
        }
    """
    return {
        "chat_tokens": state.get("chat_tokens", {}),
        "eval_tokens": state.get("eval_tokens", {}),
    }


def format_tokens_for_core(
    chat_tokens: Optional[Dict[str, int]] = None,
    eval_tokens: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """
    Core 백엔드로 전달할 토큰 사용량 형식으로 변환

    [Core 전달 형식]
    {
        "chat_tokens": {
            "prompt_tokens": int,
            "completion_tokens": int,
            "total_tokens": int
        },
        "eval_tokens": {
            "prompt_tokens": int,
            "completion_tokens": int,
            "total_tokens": int
        },
        "total_tokens": {
            "prompt_tokens": int,  # chat + eval 합계
            "completion_tokens": int,  # chat + eval 합계
            "total_tokens": int  # chat + eval 합계
        }
    }

    Args:
        chat_tokens: 채팅 검사 토큰 사용량
        eval_tokens: 평가 토큰 사용량

    Returns:
        Core 전달용 토큰 사용량 딕셔너리
    """
    # 기본값 설정
    chat = chat_tokens or {}
    eval = eval_tokens or {}

    # 합계 계산
    total = {
        "prompt_tokens": chat.get("prompt_tokens", 0) + eval.get("prompt_tokens", 0),
        "completion_tokens": chat.get("completion_tokens", 0)
        + eval.get("completion_tokens", 0),
        "total_tokens": chat.get("total_tokens", 0) + eval.get("total_tokens", 0),
    }

    result = {
        "total_tokens": total,
    }

    # 값이 있는 경우에만 포함
    if chat and any(chat.values()):
        result["chat_tokens"] = chat

    if eval and any(eval.values()):
        result["eval_tokens"] = eval

    return result
