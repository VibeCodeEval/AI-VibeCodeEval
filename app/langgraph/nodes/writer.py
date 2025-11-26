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
    is_guardrail_failed = state.get("is_guardrail_failed", False)
    guardrail_message = state.get("guardrail_message", "")
    
    logger.info(f"[Writer LLM] 답변 생성 시작 - message: {human_message[:100]}..., guardrail_failed: {is_guardrail_failed}")
    
    llm = get_llm()
    
    # 시스템 프롬프트 구성 (가드레일 여부에 따라 다름)
    if is_guardrail_failed:
        # 가드레일 위반 시: 교육적 거절 메시지
        system_prompt = f"""당신은 AI 코딩 테스트의 보안 관리자(Gatekeeper)입니다.

# 🛡️ 상황
사용자의 요청이 테스트 정책에 위반되었습니다.
위반 이유: {guardrail_message or "부적절한 요청"}

# ✋ 거절 메시지 생성 규칙
1. **정중하게 거절**: "해당 요청은 테스트 정책상 답변할 수 없습니다."
2. **이유 간단 설명**: 왜 거절하는지 1-2줄로 설명
3. **대안 제시**: 대신 **개념(Concept)** 수준에서 학습 방향 제시
4. **소크라테스식 반문**: 질문을 던져 스스로 생각하게 유도

# 📜 응답 형식 예시
```
죄송합니다만, 해당 요청은 문제의 정답과 직결되어 있어 직접 답변드리기 어렵습니다.

대신, 다음 개념들을 공부해보시는 건 어떨까요?
- 비트마스킹으로 상태 표현하기
- 동적 계획법의 메모이제이션

스스로 생각해보세요: "모든 도시를 방문했는지 어떻게 확인할 수 있을까요?"
```

**톤**: 엄격하지만 교육적, 격려하는 태도
"""
    else:
        # 정상 요청 시: 소크라테스식 튜터
        system_prompt = """당신은 소크라테스식 교육법을 지향하는 AI 코딩 튜터입니다.

# 🎯 역할
사용자의 알고리즘 문제 해결을 돕되, **정답을 직접 주지 않고** 스스로 깨닫도록 유도합니다.

# ✍️ 답변 규칙
1. **정답 코드 지양**: 핵심 알고리즘 로직은 직접 주지 않음
2. **답변 형식**:
   - `[Syntax]`: 순수 문법 예시 (문제와 무관)
   - `[Concept]`: 개념적 설명
   - `[Roadmap]`: 단계별 접근법
   - `[Question]`: 반문으로 유도

3. **예시 코드**: 문제와 직접 관련 없는 일반적 상황만
   ```python
   # 비트 연산 예시
   visited = 0
   visited |= (1 << 3)  # 3번 방문 표시
   ```

4. **톤**: 친절하고 격려하되, 스스로 생각하도록 유도

# 규칙
1. 실행 가능한 코드와 설명 제공
2. 적절한 주석 포함
3. 효율적인 알고리즘 권장
4. 에지 케이스 고려
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
        
        # 현재 턴 번호 가져오기
        current_turn = state.get("current_turn", 0)
        session_id = state.get("session_id", "unknown")
        
        # 기존 messages 배열 길이 확인 (새 메시지 인덱스 계산용)
        existing_messages = state.get("messages", [])
        start_msg_idx = len(existing_messages)
        end_msg_idx = start_msg_idx + 1
        
        # Redis에 턴-메시지 매핑 저장
        try:
            from app.db.redis_client import redis_client
            import asyncio
            
            # 비동기로 턴 매핑 저장 (실패해도 메인 플로우 중단 안 함)
            asyncio.create_task(
                redis_client.save_turn_mapping(
                    session_id=session_id,
                    turn=current_turn,
                    start_msg_idx=start_msg_idx,
                    end_msg_idx=end_msg_idx
                )
            )
            logger.info(f"[Writer LLM] 턴 매핑 저장 시작 - turn: {current_turn}, indices: [{start_msg_idx}, {end_msg_idx}]")
        except Exception as e:
            logger.warning(f"[Writer LLM] 턴 매핑 저장 실패 (무시): {str(e)}")
        
        # messages 배열에 turn 정보 포함 (백그라운드 4번 평가를 위해)
        new_messages = [
            {
                "turn": current_turn,
                "role": "user",
                "content": human_message,
                "timestamp": datetime.utcnow().isoformat()
            },
            {
                "turn": current_turn,
                "role": "assistant", 
                "content": ai_content,
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
        
        return {
            "ai_message": ai_content,
            "messages": new_messages,
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


