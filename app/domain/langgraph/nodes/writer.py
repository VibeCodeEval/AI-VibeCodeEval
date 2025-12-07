"""
노드 3: Writer LLM
AI 답변 생성 (Runnable & Chain 구조)
"""

from typing import Dict, Any, Optional
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai import ChatVertexAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.domain.langgraph.states import MainGraphState
from app.core.config import settings
from app.infrastructure.persistence.models.enums import WriterResponseStatus
from app.domain.langgraph.middleware import wrap_chain_with_middleware
from app.domain.langgraph.utils.token_tracking import extract_token_usage, accumulate_tokens


def get_llm():
    """LLM 인스턴스 생성 (Vertex AI 또는 AI Studio)"""
    if settings.USE_VERTEX_AI:
        # Vertex AI 사용 (GCP 크레딧 사용)
        import json
        from google.oauth2 import service_account
        
        credentials = None
        if settings.GOOGLE_SERVICE_ACCOUNT_JSON:
            service_account_info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info
            )
        
        return ChatVertexAI(
            model=settings.DEFAULT_LLM_MODEL,
            project=settings.GOOGLE_PROJECT_ID,
            location=settings.GOOGLE_LOCATION,
            credentials=credentials,
            temperature=settings.LLM_TEMPERATURE,
            max_output_tokens=settings.LLM_MAX_TOKENS,
        )
    else:
        # AI Studio 사용 (API Key 방식, Free Tier)
        return ChatGoogleGenerativeAI(
            model=settings.DEFAULT_LLM_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=settings.LLM_TEMPERATURE,
            max_output_tokens=settings.LLM_MAX_TOKENS,
        )


# 시스템 프롬프트 템플릿
GUARDRAIL_SYSTEM_PROMPT_TEMPLATE = """당신은 AI 코딩 테스트의 보안 관리자(Gatekeeper)입니다.

# 🛡️ 상황
사용자의 요청이 테스트 정책에 위반되었습니다.
위반 이유: {guardrail_message}

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

def create_normal_system_prompt(
    status: str,
    guide_strategy: str,
    keywords: str,
    memory_summary: str,
    problem_context: Optional[Dict[str, Any]] = None,
    is_code_generation_request: bool = False
) -> str:
    """
    Writer LLM 시스템 프롬프트 생성 (문제 정보 포함)
    
    Args:
        status: 안전 상태 (SAFE)
        guide_strategy: 가이드 전략 (SYNTAX_GUIDE | LOGIC_HINT | ROADMAP)
        keywords: 핵심 키워드
        memory_summary: 이전 대화 요약
        problem_context: 문제 정보 딕셔너리
    
    Returns:
        str: 시스템 프롬프트
    """
    # 문제 정보 추출
    problem_info_section = ""
    hint_roadmap_section = ""
    
    if problem_context:
        basic_info = problem_context.get("basic_info", {})
        ai_guide = problem_context.get("ai_guide", {})
        hint_roadmap = ai_guide.get("hint_roadmap", {})
        
        problem_title = basic_info.get("title", "알 수 없음")
        problem_id = basic_info.get("problem_id", "")
        key_algorithms = ai_guide.get("key_algorithms", [])
        algorithms_text = ", ".join(key_algorithms) if key_algorithms else "없음"
        
        problem_info_section = f"""
[문제 정보]
- 문제: {problem_title} ({problem_id})
- 필수 알고리즘: {algorithms_text}

"""
        
        # 힌트 로드맵이 있는 경우 추가
        if hint_roadmap:
            hint_roadmap_section = f"""
[힌트 로드맵 참고]
- 1단계: {hint_roadmap.get("step_1_concept", "")}
- 2단계: {hint_roadmap.get("step_2_state", "")}
- 3단계: {hint_roadmap.get("step_3_transition", "")}
- 4단계: {hint_roadmap.get("step_4_base_case", "")}

"""
    else:
        problem_info_section = ""
        hint_roadmap_section = ""
    
    # SYNTAX_GUIDE 규칙 미리 계산 (에러 체크 및 디버깅 용이)
    syntax_guide_rule = (
        f"- {problem_title} 문제의 정답 코드는 절대 제공하지 않음"
        if problem_context
        else "- 문제의 정답 코드는 절대 제공하지 않음"
    )
    
    # 코드 생성 요청인 경우 추가 안내
    code_generation_section = ""
    if is_code_generation_request:
        code_generation_section = """
# 📝 코드 생성 요청 감지
사용자가 이전 대화 맥락을 바탕으로 코드 생성을 요청했습니다.
- 이전 턴에서 힌트, 점화식, 접근 방식이 논의되었으므로 코드 생성이 허용됩니다.
- 이전 대화의 맥락을 명확히 참조하여 일관성 있는 코드를 생성하세요.
- 사용자가 요청한 제약 조건(시간 복잡도, 입력 형식 등)을 반드시 준수하세요.

"""
    
    return f"""# Role Definition

너는 소크라테스식 교육법을 지향하는 알고리즘 튜터 '바이브코딩'이다.

{problem_info_section}Node 2의 분석 결과:
- Status: {status} (SAFE)
- Guide Strategy: {guide_strategy} (SYNTAX_GUIDE | LOGIC_HINT | ROADMAP | GENERATION)
- Keywords: {keywords}
{code_generation_section}{hint_roadmap_section}

# 🎯 Guide Strategy별 답변 규칙

## SYNTAX_GUIDE인 경우:
- **[Syntax Example]** 형식 필수
- 문제와 무관한 순수 문법 예시만 제공
{syntax_guide_rule}

예시:
```
[Syntax Example]
비트마스킹의 기본 문법 예시 (문제와 무관):

```python
# 비트 시프트 연산 예시
a = 1
print(a << 3)  # 2^3 = 8 출력

# 비트 OR 연산 예시
visited = 0
visited |= (1 << 3)  # 3번 방문 표시
```
```

## LOGIC_HINT인 경우:
- **[Concept]** 형식 필수
- 일반적인 알고리즘 개념 설명
- **힌트 요청 시**: 구체적이고 실용적인 힌트 제공 (회피적이지 않게)
- **점화식 힌트 요청 시**: 점화식의 구조와 접근 방식을 구체적으로 안내
- 문제 특정 완전한 정답 코드는 제외하되, 힌트는 충분히 제공

예시 (일반 개념 질문):
```
[Concept]
동적 계획법은 큰 문제를 작은 하위 문제로 나누어 해결하는 기법입니다.
- 메모이제이션: 계산 결과를 저장하여 중복 계산 방지
- 점화식: 하위 문제 간의 관계를 수식으로 표현

[Question]
스스로 생각해보세요: "이 문제에서 어떤 하위 문제들이 있을까요?"
```

예시 (점화식 힌트 요청):
```
[Concept]
`dp[current_city][visited_bitmask]` 상태에서 점화식을 수립할 때:

1. **현재 상태**: `current_city`에 있고, `visited_bitmask`에 해당하는 도시들을 방문한 상태
2. **다음 단계**: 아직 방문하지 않은 도시 `next_city`로 이동
3. **점화식 구조**: 
   - `dp[current][visited] = min(모든 next_city에 대해, cost(current, next) + dp[next][visited | (1<<next)])`
   - 현재 도시에서 다음 도시로 이동하는 비용 + 다음 도시에서 나머지를 방문하는 최소 비용

[Question]
이제 기저 조건(base case)을 생각해보세요: 모든 도시를 방문한 경우는 어떻게 처리해야 할까요?
```
```

## ROADMAP인 경우:
- **[Roadmap]** 형식 필수
- 문제 해결 단계별 접근법
- 구체적 로직은 제외

예시:
```
[Roadmap]
문제 해결 단계별 접근법 (구체적 로직 제외):

1. 문제 이해: 입력/출력 형식 파악
2. 접근 방법 선택: 어떤 알고리즘 패러다임을 사용할지
3. 상태 정의: 동적 계획법이라면 어떤 상태를 저장할지
4. 점화식 설계: 상태 간의 관계 정의
5. 구현 및 테스트

[Question]
스스로 생각해보세요: "각 단계에서 어떤 정보가 필요할까요?"
```
```

## GENERATION인 경우 (코드 생성 요청):
- **[Code]** 형식 필수
- 이전 대화 맥락을 바탕으로 코드 생성
- 이전 턴에서 논의된 힌트, 점화식, 접근 방식을 반영
- 사용자가 요청한 제약 조건을 반드시 준수
- 코드에 주석을 추가하여 이해를 돕기

예시:
```
[Code]
이전에 논의한 점화식을 바탕으로 코드를 작성했습니다:

```python
# 이전 턴에서 논의한 점화식 구조를 반영
# dp[current][visited] = min(cost(current, next) + dp[next][visited | (1<<next)])
# ... (코드 내용)
```

[Note]
- 이전 대화에서 논의한 점화식 구조를 반영했습니다.
- 요청하신 제약 조건(시간 복잡도 O(N^2 * 2^N), sys.stdin.readline 사용 등)을 준수했습니다.
```
```

# 🚫 절대 금지
- 문제의 완전한 정답 코드 제공 (처음부터 끝까지 완성된 코드, 맥락 없이 요청된 경우)
- 문제 특정 핵심 로직의 완전한 구현 제공 (맥락 없이 요청된 경우)

# ✅ 허용 (맥락 기반)
- **힌트 요청 시**: 구체적이고 실용적인 힌트 제공 (회피적이지 않게)
  - 예: "점화식 수립을 위한 힌트" → 점화식의 구조, 접근 방식, 예시를 구체적으로 안내
  - 예: "비트마스킹 사용법" → 구체적인 사용 예시와 패턴 제공
- **코드 생성 요청 시**: 이전 대화 맥락을 바탕으로 적절한 코드 생성
  - 이전 턴에서 힌트, 점화식, 접근 방식이 논의된 경우 → 그를 바탕으로 코드 생성 허용
  - 예: "제안해주신 점화식을 바탕으로 코드를 작성해주세요" → 코드 생성 허용
  - 예: "이전에 말한 방법으로 코드를 작성해주세요" → 코드 생성 허용
  - 단, 처음부터 완전한 정답 코드를 요청하는 경우는 제외

# 📝 코드 생성 시 주의사항
- 이전 대화 맥락을 명확히 참조하여 일관성 있는 코드 생성
- 사용자가 요청한 제약 조건(시간 복잡도, 입력 형식 등)을 반드시 준수
- 코드에 주석을 추가하여 이해를 돕기

# Output Formats (Strictly Adhere)
답변은 반드시 다음 형식 중 하나 이상을 사용:
- **[Syntax Example]**: 문법 예시 (문제와 무관)
- **[Concept]**: 개념 설명 또는 구체적 힌트
- **[Roadmap]**: 단계별 접근법
- **[Question]**: 반문으로 유도
- **[Code]**: 코드 생성 요청 시 코드 제공 (맥락 기반)

# 톤
친절하고 격려하되, 적절한 수준의 도움을 제공
- 힌트 요청 시: 회피적이지 않고 구체적으로 안내
- 코드 생성 요청 시: 맥락을 고려하여 적절한 코드 제공

{memory_summary}
"""


def prepare_writer_input(state: MainGraphState) -> Dict[str, Any]:
    """Writer Chain 입력 준비 (Guide Strategy 기반)"""
    human_message = state.get("human_message", "")
    messages = state.get("messages", [])
    memory_summary = state.get("memory_summary", "")
    is_guardrail_failed = state.get("is_guardrail_failed", False)
    guardrail_message = state.get("guardrail_message", "")
    
    # Guide Strategy 정보 가져오기
    guide_strategy = state.get("guide_strategy", "LOGIC_HINT")  # 기본값
    keywords = state.get("keywords", [])
    problem_context = state.get("problem_context")
    
    # 코드 생성 요청 감지 (맥락 기반)
    is_code_generation_request = False
    if not is_guardrail_failed:
        message_lower = human_message.lower()
        code_generation_keywords = ["코드 작성", "코드 생성", "코드를 작성", "코드를 생성", "코드 작성해", "코드 생성해"]
        
        # 코드 생성 요청 키워드 확인
        if any(kw in message_lower for kw in code_generation_keywords):
            # 이전 대화에서 힌트나 점화식이 논의되었는지 확인
            has_previous_context = False
            if messages:
                # 최근 3턴 확인
                recent_messages = messages[-6:] if len(messages) > 6 else messages
                for msg in recent_messages:
                    if hasattr(msg, 'content'):
                        content = str(msg.content).lower()
                        # 힌트, 점화식, 접근 방식 등이 논의되었는지 확인
                        context_keywords = ["힌트", "점화식", "접근", "방법", "hint", "recurrence", "approach"]
                        if any(ck in content for ck in context_keywords):
                            has_previous_context = True
                            break
            
            # 이전 맥락이 있거나, 명시적으로 이전 대화를 참조하는 경우
            if has_previous_context or any(ref in message_lower for ref in ["제안해주신", "이전", "앞서", "말한", "바탕으로"]):
                is_code_generation_request = True
    
    # 시스템 프롬프트 선택
    if is_guardrail_failed:
        system_prompt = GUARDRAIL_SYSTEM_PROMPT_TEMPLATE.format(
            guardrail_message=guardrail_message or "부적절한 요청"
        )
    else:
        memory_text = f"\n\n이전 대화 요약:\n{memory_summary}" if memory_summary else ""
        keywords_text = ", ".join(keywords) if keywords else "없음"
        
        # 코드 생성 요청인 경우 Guide Strategy를 GENERATION으로 변경
        if is_code_generation_request:
            guide_strategy = "GENERATION"
        
        system_prompt = create_normal_system_prompt(
            status="SAFE",
            guide_strategy=guide_strategy or "LOGIC_HINT",
            keywords=keywords_text,
            memory_summary=memory_text,
            problem_context=problem_context,
            is_code_generation_request=is_code_generation_request
        )
    
    # 최근 메시지 변환 (최대 10개)
    recent_messages = messages[-10:] if len(messages) > 10 else messages
    formatted_messages = []
    for msg in recent_messages:
        if hasattr(msg, 'content'):
            role = getattr(msg, 'type', 'user')
            if role == 'human':
                role = 'user'
            elif role == 'ai':
                role = 'assistant'
            formatted_messages.append({"role": role, "content": msg.content})
    
    return {
        "system_prompt": system_prompt,
        "messages": formatted_messages,
        "human_message": human_message,
        "state": state,  # 후처리를 위해 state 전달
    }


def format_writer_messages(inputs: Dict[str, Any]) -> list:
    """메시지 리스트를 LangChain BaseMessage 객체로 변환"""
    chat_messages = []
    
    # 시스템 메시지 추가
    if inputs.get("system_prompt"):
        chat_messages.append(SystemMessage(content=inputs["system_prompt"]))
    
    # 이전 대화 메시지 변환
    for msg in inputs.get("messages", []):
        if isinstance(msg, dict):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                chat_messages.append(SystemMessage(content=content))
            elif role == "assistant" or role == "ai":
                chat_messages.append(AIMessage(content=content))
            else:
                chat_messages.append(HumanMessage(content=content))
        elif hasattr(msg, 'content'):
            # 이미 BaseMessage 객체인 경우
            chat_messages.append(msg)
    
    # 현재 사용자 메시지 추가
    if inputs.get("human_message"):
        chat_messages.append(HumanMessage(content=inputs["human_message"]))
    
    return chat_messages


def extract_content(response: Any) -> Dict[str, Any]:
    """LLM 응답에서 내용 추출"""
    ai_content = response.content if hasattr(response, 'content') else str(response)
    return {
        "ai_content": ai_content,
        "state": response.state if hasattr(response, 'state') else None,
    }


# Writer Chain 구성 (모듈 레벨에서 캐싱)
_writer_chain = None
_writer_llm = None

def get_writer_chain():
    """Writer Chain 생성 (싱글톤 패턴) - Middleware 적용"""
    global _writer_chain, _writer_llm
    
    if _writer_chain is None:
        _writer_llm = get_llm()
        
        # 기본 Chain: 입력 준비 -> 메시지 포맷 -> LLM 호출 -> 내용 추출 (토큰 추출을 위해 LLM 응답 객체도 전달)
        def extract_content_with_response(response: Any) -> Dict[str, Any]:
            """LLM 응답에서 내용과 응답 객체를 함께 반환"""
            ai_content = response.content if hasattr(response, 'content') else str(response)
            return {
                "ai_content": ai_content,
                "_llm_response": response  # 토큰 추출용 - LLM 응답 객체 그대로 전달
            }
        
        _base_writer_chain = (
            RunnableLambda(prepare_writer_input)
            | RunnableLambda(format_writer_messages)
            | _writer_llm  # LLM 호출 - AIMessage 객체 반환
            | RunnableLambda(extract_content_with_response)  # 내용 추출 및 응답 객체 보존
        )
        
        # Middleware 적용 (Factory 함수 사용)
        _writer_chain = wrap_chain_with_middleware(
            _base_writer_chain,
            name="Writer LLM"
        )
    
    return _writer_chain


async def writer_llm(state: MainGraphState) -> Dict[str, Any]:
    """
    AI 답변 생성 (Runnable & Chain 구조)
    
    역할:
    - 사용자 요청에 대한 코드 작성
    - 힌트 제공
    - 디버깅 도움
    - 설명 제공
    """
    import logging
    logger = logging.getLogger(__name__)
    
    human_message = state.get("human_message", "")
    is_guardrail_failed = state.get("is_guardrail_failed", False)
    
    logger.info(f"[Writer LLM] 답변 생성 시작 - message: {human_message[:100]}..., guardrail_failed: {is_guardrail_failed}")
    
    try:
        # Writer Chain 실행 (캐싱된 Chain 사용)
        chain = get_writer_chain()
        chain_result = await chain.ainvoke(state)
        
        # Chain 결과에서 내용과 LLM 응답 객체 분리
        ai_content = chain_result.get("ai_content", "") if isinstance(chain_result, dict) else str(chain_result)
        llm_response = chain_result.get("_llm_response") if isinstance(chain_result, dict) else None
        
        # 토큰 사용량 추출 및 State에 누적
        if llm_response:
            tokens = extract_token_usage(llm_response)
            if tokens:
                accumulate_tokens(state, tokens, token_type="chat")
                logger.debug(f"[Writer LLM] 토큰 사용량 - prompt: {tokens.get('prompt_tokens')}, completion: {tokens.get('completion_tokens')}, total: {tokens.get('total_tokens')}")
        
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
            from app.infrastructure.cache.redis_client import redis_client
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
        
        # messages 배열에 turn 정보 포함 (4번 노드 평가를 위해)
        # LangChain BaseMessage 객체를 직접 생성하여 turn 속성 보존
        from langchain_core.messages import HumanMessage, AIMessage
        
        human_msg = HumanMessage(content=human_message)
        human_msg.turn = current_turn  # turn 속성 추가
        human_msg.role = "user"  # role 속성 추가
        human_msg.timestamp = datetime.utcnow().isoformat()
        
        ai_msg = AIMessage(content=ai_content)
        ai_msg.turn = current_turn  # turn 속성 추가
        ai_msg.role = "assistant"  # role 속성 추가
        ai_msg.timestamp = datetime.utcnow().isoformat()
        
        new_messages = [human_msg, ai_msg]
        
        # State에 누적된 토큰 정보를 result에 포함 (LangGraph 병합을 위해)
        result = {
            "ai_message": ai_content,
            "messages": new_messages,
            "writer_status": WriterResponseStatus.SUCCESS.value,
            "writer_error": None,
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        # State에 누적된 토큰 정보 포함
        if "chat_tokens" in state:
            result["chat_tokens"] = state["chat_tokens"]
        
        return result
        
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


