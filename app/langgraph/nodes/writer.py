"""
노드 3: Writer LLM
AI 답변 생성
"""
from typing import Dict, Any
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI

from app.langgraph.states import MainGraphState
from app.core.config import settings
from app.db.models.enums import WriterResponseStatus


def get_llm():
    """LLM 인스턴스 생성"""
    return ChatGoogleGenerativeAI(
        model=settings.DEFAULT_LLM_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
    )


async def writer_llm(state: MainGraphState) -> Dict[str, Any]:
    """
    AI 답변 생성
    
    역할:
    - 사용자 요청에 대한 코드 작성
    - 힌트 제공
    - 디버깅 도움
    - 설명 제공
    """
    import logging
    logger = logging.getLogger(__name__)
    
    human_message = state.get("human_message", "")
    messages = state.get("messages", [])
    memory_summary = state.get("memory_summary", "")
    
    logger.info(f"[Writer LLM] 답변 생성 시작 - message: {human_message[:100]}...")
    
    llm = get_llm()
    
    # 시스템 프롬프트 구성
    system_prompt = """당신은 AI 코딩 테스트를 돕는 전문 코딩 어시스턴트입니다.

역할:
- 사용자의 코딩 요청에 대해 정확하고 효율적인 코드를 작성합니다
- 코드에 대한 설명을 제공합니다
- 디버깅을 돕습니다
- 힌트와 가이드를 제공합니다

규칙:
1. 코드는 항상 실행 가능해야 합니다
2. 적절한 주석을 포함하세요
3. 효율적인 알고리즘을 사용하세요
4. 에지 케이스를 고려하세요
5. 코드 스타일 가이드를 따르세요
"""
    
    if memory_summary:
        system_prompt += f"\n\n이전 대화 요약:\n{memory_summary}"
    
    # 메시지 히스토리 구성
    chat_messages = [{"role": "system", "content": system_prompt}]
    
    # 최근 메시지 추가 (최대 10개)
    recent_messages = messages[-10:] if len(messages) > 10 else messages
    for msg in recent_messages:
        if hasattr(msg, 'content'):
            role = getattr(msg, 'type', 'user')
            if role == 'human':
                role = 'user'
            elif role == 'ai':
                role = 'assistant'
            chat_messages.append({"role": role, "content": msg.content})
    
    # 현재 메시지 추가
    chat_messages.append({"role": "user", "content": human_message})
    
    try:
        response = await llm.ainvoke(chat_messages)
        ai_content = response.content
        
        logger.info(f"[Writer LLM] 답변 생성 성공 - 길이: {len(ai_content)} 문자")
        
        # 일반 채팅인 경우 4번 노드(Eval Turn)를 백그라운드로 실행하기 위해 플래그 설정
        # (실제 백그라운드 실행은 eval_service에서 처리)
        
        return {
            "ai_message": ai_content,
            "messages": [{"role": "assistant", "content": ai_content}],
            "writer_status": WriterResponseStatus.SUCCESS.value,
            "writer_error": None,
            "updated_at": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"[Writer LLM] 에러 발생: {str(e)}", exc_info=True)
        error_msg = str(e).lower()
        
        # 에러 유형 분류
        if "rate" in error_msg or "quota" in error_msg:
            status = WriterResponseStatus.FAILED_RATE_LIMIT.value
            logger.warning(f"[Writer LLM] Rate limit 초과")
        elif "context" in error_msg or "token" in error_msg:
            status = WriterResponseStatus.FAILED_THRESHOLD.value
            logger.warning(f"[Writer LLM] 토큰 임계값 초과")
        else:
            status = WriterResponseStatus.FAILED_TECHNICAL.value
            logger.error(f"[Writer LLM] 기술적 오류: {str(e)}")
        
        return {
            "ai_message": None,
            "writer_status": status,
            "writer_error": str(e),
            "error_message": f"답변 생성 중 오류가 발생했습니다: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }


