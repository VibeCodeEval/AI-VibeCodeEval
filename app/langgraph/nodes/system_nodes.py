"""
시스템 노드들
- Handle Failure: 오류 및 경고 메시지 생성
- Summarize Memory: 메모리 요약
"""
from typing import Dict, Any
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI

from app.langgraph.states import MainGraphState
from app.core.config import settings


def get_llm():
    """LLM 인스턴스 생성"""
    return ChatGoogleGenerativeAI(
        model=settings.DEFAULT_LLM_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.3,
    )


async def handle_failure(state: MainGraphState) -> Dict[str, Any]:
    """
    오류 및 경고 메시지 생성
    
    상황별 메시지:
    - 가드레일 위반: 경고 메시지
    - 기술적 오류: 재시도 안내
    - Rate limit: 잠시 후 재시도 안내
    """
    writer_status = state.get("writer_status")
    intent_status = state.get("intent_status")
    writer_error = state.get("writer_error")
    guardrail_message = state.get("guardrail_message")
    retry_count = state.get("retry_count", 0)
    
    # 가드레일 위반
    if state.get("is_guardrail_failed") or intent_status == "FAILED_GUARDRAIL":
        message = guardrail_message or "요청이 가이드라인을 위반했습니다. 다른 방식으로 질문해 주세요."
        return {
            "ai_message": message,
            "messages": [{"role": "assistant", "content": message}],
            "error_message": None,
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    # Rate limit
    if "RATE_LIMIT" in (writer_status or "") or "RATE_LIMIT" in (intent_status or ""):
        message = "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요."
        return {
            "ai_message": message,
            "messages": [{"role": "assistant", "content": message}],
            "retry_count": retry_count + 1,
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    # 기술적 오류
    message = "죄송합니다. 일시적인 오류가 발생했습니다. 다시 시도해 주세요."
    if writer_error:
        # 개발 모드에서는 상세 에러 표시
        if settings.DEBUG:
            message += f"\n\n디버그 정보: {writer_error}"
    
    return {
        "ai_message": message,
        "messages": [{"role": "assistant", "content": message}],
        "error_message": writer_error,
        "retry_count": retry_count + 1,
        "updated_at": datetime.utcnow().isoformat(),
    }


async def summarize_memory(state: MainGraphState) -> Dict[str, Any]:
    """
    메모리 요약
    
    대화 히스토리가 길어지면 요약하여 토큰 절약
    """
    messages = state.get("messages", [])
    existing_summary = state.get("memory_summary", "")
    
    if len(messages) < 10:
        # 메시지가 적으면 요약 불필요
        return {
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    llm = get_llm()
    
    # 요약할 메시지 준비 (최근 것 제외)
    messages_to_summarize = messages[:-4] if len(messages) > 4 else messages
    
    conversation_text = ""
    for msg in messages_to_summarize:
        if hasattr(msg, 'content'):
            role = getattr(msg, 'type', 'user')
            if role == 'human':
                role = 'User'
            elif role == 'ai':
                role = 'Assistant'
            conversation_text += f"{role}: {msg.content}\n\n"
    
    system_prompt = """당신은 대화 요약 전문가입니다.
주어진 대화 내용을 핵심만 담아 간결하게 요약해주세요.

요약 시 포함할 내용:
1. 사용자가 해결하려는 문제
2. 이미 시도한 접근 방법
3. 현재 코드 상태의 핵심
4. 남은 과제나 이슈

기존 요약이 있다면 그것도 고려하여 통합 요약을 만드세요."""

    prompt = f"기존 요약:\n{existing_summary}\n\n새로운 대화:\n{conversation_text}"
    
    try:
        response = await llm.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])
        
        new_summary = response.content
        
        return {
            "memory_summary": new_summary,
            # 오래된 메시지 정리 (최근 4개만 유지)
            "messages": messages[-4:] if len(messages) > 4 else messages,
            "updated_at": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        # 요약 실패 시 기존 상태 유지
        return {
            "error_message": f"메모리 요약 실패: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }



