"""
토큰 사용량 추적 유틸리티

[목적]
- LLM 응답에서 토큰 사용량 추출
- 채팅 검사 토큰과 평가 토큰 분리 추적
- State에 누적 저장
- Core 백엔드로 전달할 형식으로 변환
"""
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


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
        if hasattr(response, 'usage_metadata'):
            usage = response.usage_metadata
            if usage:
                # dict인 경우
                if isinstance(usage, dict):
                    logger.debug(f"[Token Tracking] usage_metadata 발견 (dict) - {usage}")
                    return {
                        "prompt_tokens": usage.get("input_tokens", 0),
                        "completion_tokens": usage.get("output_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    }
                else:
                    # 객체인 경우
                    logger.debug(f"[Token Tracking] usage_metadata 발견 (객체) - {usage}")
                    return {
                        "prompt_tokens": getattr(usage, "input_tokens", 0) or 0,
                        "completion_tokens": getattr(usage, "output_tokens", 0) or 0,
                        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
                    }
        
        # 방법 2: response_metadata에서 추출 (다른 LLM용)
        if hasattr(response, 'response_metadata'):
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
                            "prompt_tokens": usage.get("prompt_token_count", usage.get("prompt_tokens", 0)),
                            "completion_tokens": usage.get("candidates_token_count", usage.get("completion_tokens", 0)),
                            "total_tokens": usage.get("total_token_count", usage.get("total_tokens", 0)),
                        }
        
        # 방법 3: dict 형태의 response
        if isinstance(response, dict):
            usage = response.get("usage_metadata", {})
            if usage:
                return {
                    "prompt_tokens": usage.get("input_tokens", usage.get("prompt_tokens", 0)),
                    "completion_tokens": usage.get("output_tokens", usage.get("completion_tokens", 0)),
                    "total_tokens": usage.get("total_tokens", 0),
                }
        
        logger.warning(f"[Token Tracking] 토큰 사용량 추출 실패 - response 타입: {type(response)}")
        return None
        
    except Exception as e:
        logger.warning(f"[Token Tracking] 토큰 사용량 추출 중 오류: {str(e)}")
        return None


def accumulate_tokens(
    state: Dict[str, Any],
    new_tokens: Optional[Dict[str, int]],
    token_type: str = "chat"  # "chat" 또는 "eval"
) -> Dict[str, Any]:
    """
    State에 토큰 사용량 누적
    
    Args:
        state: MainGraphState 또는 EvalTurnState
        new_tokens: 새로 추출한 토큰 사용량
        token_type: "chat" (채팅 검사) 또는 "eval" (평가)
    
    Returns:
        업데이트된 State (토큰 누적)
    """
    if not new_tokens:
        return state
    
    # 기존 토큰 사용량 가져오기
    if token_type == "chat":
        existing = state.get("chat_tokens", {}) or {}
    else:  # eval
        existing = state.get("eval_tokens", {}) or {}
    
    # 누적
    accumulated = {
        "prompt_tokens": existing.get("prompt_tokens", 0) + new_tokens.get("prompt_tokens", 0),
        "completion_tokens": existing.get("completion_tokens", 0) + new_tokens.get("completion_tokens", 0),
        "total_tokens": existing.get("total_tokens", 0) + new_tokens.get("total_tokens", 0),
    }
    
    # State 업데이트
    if token_type == "chat":
        state["chat_tokens"] = accumulated
    else:  # eval
        state["eval_tokens"] = accumulated
    
    logger.debug(f"[Token Tracking] 토큰 누적 완료 - type: {token_type}, accumulated: {accumulated}")
    
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
    eval_tokens: Optional[Dict[str, int]] = None
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
        "completion_tokens": chat.get("completion_tokens", 0) + eval.get("completion_tokens", 0),
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
