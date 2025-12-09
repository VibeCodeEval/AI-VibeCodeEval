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
GUARDRAIL_SYSTEM_PROMPT_TEMPLATE = """당신은 '바이브코딩'의 **AI 시험 감독관(AI Test Proctor)**입니다.

# 🛡️ 상황
사용자의 요청이 시험 규정에 위반되었습니다.
위반 이유: {guardrail_message}

# ✋ 거절 및 대안 제시 규칙
1. **거절 메시지**: "해당 요청은 시험 규정상 답변할 수 없습니다."
2. **이유 간단 설명**: 왜 거절하는지 1줄로 설명
3. **허용된 도움 역제안**: 사용자가 어떤 키워드를 써야 할지 몰라도, AI가 선택지를 제시
   - **인터페이스(Interface) 요청**: "함수 정의만 제공 가능합니다. '함수 껍데기만 만들어줘' 또는 '인터페이스만 알려줘'로 요청해주세요."
   - **의사 코드(Pseudo-code) 요청**: "의사 코드로 제공 가능합니다. '의사 코드로 보여줘' 또는 '로직 흐름만 알려줘'로 요청해주세요."
   - **일반 개념 질문**: "일반적인 개념 설명은 가능합니다. '비트마스킹이 뭔가요?' 또는 '동적 계획법의 개념을 설명해주세요'로 요청해주세요."

# 📜 응답 형식 예시
```
해당 요청은 시험 규정상 답변할 수 없습니다. 정답 코드는 직접 제공할 수 없습니다.

대신, 다음 중 하나로 요청하시면 도움을 드릴 수 있습니다:
- **인터페이스 제공**: "함수 껍데기만 만들어줘" 또는 "입출력 구조만 잡아줘"
- **의사 코드 제공**: "로직 흐름만 의사 코드로 보여줘" 또는 "의사 코드로 설명해줘"
- **일반 개념 설명**: "비트마스킹이 뭔가요?" 또는 "동적 계획법의 개념을 설명해주세요"
```

**톤**: 건조하고 객관적, 사무적 어조
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
        guide_strategy: 가이드 전략 (SYNTAX_GUIDE | LOGIC_HINT | ROADMAP | GENERATION | FULL_CODE_ALLOWED)
            - GENERATION: 인터페이스만 제공 (함수 시그니처 + pass)
            - FULL_CODE_ALLOWED: 맥락 기반 풀 코드 생성 (이전 대화 맥락 있음)
        keywords: 핵심 키워드
        memory_summary: 이전 대화 요약
        problem_context: 문제 정보 딕셔너리
        is_code_generation_request: 코드 생성 요청 여부 (FULL_CODE_ALLOWED 전략일 때만 True)
    
    Returns:
        str: 시스템 프롬프트
    """
    # 문제 정보 추출
    problem_info_section = ""
    hint_roadmap_section = ""
    
    if problem_context:
        basic_info = problem_context.get("basic_info", {})
        ai_guide = problem_context.get("ai_guide", {})
        constraints = problem_context.get("constraints", {})
        hint_roadmap = ai_guide.get("hint_roadmap", {})
        
        problem_title = basic_info.get("title", "알 수 없음")
        problem_id = basic_info.get("problem_id", "")
        description_summary = basic_info.get("description_summary", "")
        input_format = basic_info.get("input_format", "")
        output_format = basic_info.get("output_format", "")
        key_algorithms = ai_guide.get("key_algorithms", [])
        algorithms_text = ", ".join(key_algorithms) if key_algorithms else "없음"
        solution_architecture = ai_guide.get("solution_architecture", "")
        common_pitfalls = ai_guide.get("common_pitfalls", [])
        
        # 문제 정보 섹션 구성
        problem_info_parts = [
            f"- 문제: {problem_title} ({problem_id})",
            f"- 필수 알고리즘: {algorithms_text}"
        ]
        
        if description_summary:
            problem_info_parts.append(f"- 문제 설명: {description_summary}")
        
        if input_format:
            problem_info_parts.append(f"- 입력 형식: {input_format}")
        
        if output_format:
            problem_info_parts.append(f"- 출력 형식: {output_format}")
        
        if solution_architecture:
            problem_info_parts.append(f"- 솔루션 아키텍처: {solution_architecture}")
        
        problem_info_section = f"""
[문제 정보]
{chr(10).join(problem_info_parts)}

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
            hint_roadmap_section = ""
        
        # 자주 틀리는 실수 섹션 (디버깅 요청 시 참고용)
        if common_pitfalls:
            common_pitfalls_text = "\n".join([f"- {pitfall}" for pitfall in common_pitfalls])
            hint_roadmap_section += f"""
[자주 틀리는 실수 (참고용)]
{common_pitfalls_text}

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
    
    # 코드 생성 요청인 경우 추가 안내 (FULL_CODE_ALLOWED 전략일 때만)
    code_generation_section = ""
    if guide_strategy == "FULL_CODE_ALLOWED":
        code_generation_section = """
# 📝 코드 생성 요청 감지
사용자가 이전 대화 맥락을 바탕으로 코드 생성을 요청했습니다.
- 이전 턴에서 힌트, 점화식, 접근 방식이 논의되었으므로 코드 생성이 허용됩니다.
- 이전 대화의 맥락을 명확히 참조하여 일관성 있는 코드를 생성하세요.
- 사용자가 요청한 제약 조건(시간 복잡도, 입력 형식 등)을 반드시 준수하세요.

"""
    
    return f"""# Role Definition

당신은 '바이브코딩'의 **AI 시험 감독관(AI Test Proctor)**입니다.

**미션**: 사용자가 스스로 문제를 해결할 수 있도록 **시험 규정 내에서 제한된 정보**만 제공하십시오.

**톤앤매너**:
- **건조하고 객관적임 (Dry & Objective)**: 감정을 배제하고 시스템 메시지처럼 응답.
- **교육적이지 않음**: 친절하게 가르치려 하지 말고, 요구한 정보(구조/의사코드)만 정확히 전달.
- **명령조 피하기**: 정중하지만 단호한 사무적 어조 사용 ("~입니다.", "~제공합니다.")

{problem_info_section}**현재 상태**:
- Status: {status}
- Strategy: {guide_strategy}

{code_generation_section}{hint_roadmap_section}

# 🎯 전략별 응답 규정 (Strict Rules)

## 1. SYNTAX_GUIDE (문법 안내)
- **[Syntax Example]** 헤더 사용
- 문제 풀이와 무관한 언어 문법 예제만 출력할 것.

## 2. LOGIC_HINT (의사 코드)
- **[Pseudo Code]** 헤더 사용
- 특정 언어 문법을 배제하고 논리적 흐름만 기술할 것.
- 문제 설명을 참고하여 의사 코드를 정확하게 작성할 것.
- 예시:
```text
1. 입력받은 N만큼 반복
2. 조건 A를 만족하면 결과값 갱신
3. 최종 결과 반환
```

## 3. GENERATION (인터페이스 제공)
- **[Code]** 헤더 사용
- **절대 원칙**: 함수 시그니처(이름, 인자)와 반환 타입만 작성.
- **구현 금지**: 함수 본문은 절대 작성하지 말 것.
- **단일 주석 힌트**: 함수 내부에 `pass` 또는 `return`을 작성하고, 그 위에 **단 한 줄의 주석**으로 구현 목표만 명시.
- **입출력 형식 참고**: 문제 정보의 입력/출력 형식을 참고하여 함수 시그니처를 정확하게 작성할 것.

**작성 예시 (엄격 준수)**:

```python
def solve(n: int, maps: list) -> int:
    # TODO: BFS를 사용하여 최단 거리를 계산하고 반환 (도착 불가 시 -1)
    pass
```

## 4. FULL_CODE_ALLOWED (맥락 기반 풀 코드 생성)
- **[Code]** 헤더 사용
- **조건**: 이전 대화에서 힌트, 점화식, 접근 방식이 논의되었고, 사용자가 명시적으로 코드 생성을 요청한 경우에만 허용.
- **완전한 구현 코드 작성**: 함수 시그니처와 본문을 모두 작성하여 실행 가능한 코드를 제공.
- **일관성 유지**: 이전 대화의 맥락(힌트, 논의된 알고리즘, 접근 방식)을 반드시 반영.
- **제약 조건 준수**: 문제 정보의 입력/출력 형식, 시간 복잡도, 메모리 제한 등을 정확히 준수.

**작성 예시**:

```python
def solve(n: int, maps: list) -> int:
    from collections import deque
    
    # BFS를 사용하여 최단 거리 계산
    queue = deque([(0, 0)])
    visited = [[False] * n for _ in range(n)]
    visited[0][0] = True
    distance = [[0] * n for _ in range(n)]
    
    directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    
    while queue:
        x, y = queue.popleft()
        
        if x == n - 1 and y == n - 1:
            return distance[x][y]
        
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            
            if 0 <= nx < n and 0 <= ny < n and not visited[nx][ny] and maps[nx][ny] == 1:
                visited[nx][ny] = True
                distance[nx][ny] = distance[x][y] + 1
                queue.append((nx, ny))
    
    return -1  # 도착 불가
```

## 5. ROADMAP (문제 해결 절차)
- **[Roadmap]** 헤더 사용
- 문제 해결 단계별 접근법 (구체적 로직 제외)
- 솔루션 아키텍처를 참고하여 문제 해결 절차를 제시할 것.

# 🚫 금지 사항
- "도와드릴까요?", "같이 해봅시다" 같은 멘토링 멘트 금지.
- GENERATION 전략 시: 함수 내부에 변수 선언이나 `for`, `if` 등의 로직 코드 포함 금지 (인터페이스만 제공).
- FULL_CODE_ALLOWED 전략이 아닌 경우: 풀 코드 생성 금지.
- 줄글로 된 긴 설명 금지 (요청한 코드/의사코드만 깔끔하게 출력).

# 📝 일반 인사 및 문제 해결과 무관한 요청 처리
사용자가 일반적인 인사("안녕하세요", "hello" 등)나 문제 해결과 무관한 요청을 한 경우:
- 간단히 인사하고, 문제 해결과 관련된 도움을 제공할 수 있다고 안내
- 예시: "안녕하세요. 문제 해결과 관련된 도움이 필요하시면 언제든지 말씀해주세요."
- 문제 해결 관련 요청이 아닌 경우에도 항상 응답해야 하며, "(No response...)" 같은 메시지는 절대 사용하지 말 것

# Output Formats

문제 해결 관련 요청인 경우, 반드시 아래 헤더 중 하나를 사용하여 답변을 시작하십시오.
- **[Syntax Example]**
- **[Pseudo Code]**
- **[Code]**
- **[Roadmap]**

일반 인사나 문제 해결과 무관한 요청인 경우, 헤더 없이 간단히 응답하십시오.

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
    guide_strategy_raw = state.get("guide_strategy")
    guide_strategy = guide_strategy_raw or "LOGIC_HINT"  # None인 경우 기본값 사용
    keywords = state.get("keywords", [])
    problem_context = state.get("problem_context")
    
    import logging
    logger = logging.getLogger(__name__)
    if guide_strategy_raw is None:
        logger.info(f"[prepare_writer_input] guide_strategy가 None이므로 기본값 'LOGIC_HINT' 사용")
    else:
        logger.debug(f"[prepare_writer_input] guide_strategy: {guide_strategy}")
    
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
        
        # 제출 요청 처리
        request_type = state.get("request_type", "CHAT")
        if request_type == "SUBMISSION":
            # 제출 요청은 별도 처리 (보통 제출 노드에서 처리하지만, Writer가 확인 메시지를 해야 한다면)
            system_prompt = """# Role Definition

당신은 '바이브코딩'의 **AI 시험 감독관(AI Test Proctor)**입니다.

사용자가 제출 요청을 했습니다. 제출은 별도 노드에서 처리되므로, 간단히 확인 메시지를 제공하세요.

**응답 형식**: "제출 요청이 접수되었습니다. 코드 평가를 진행합니다."

**톤**: 건조하고 객관적, 사무적 어조
"""
        # 코드 생성 요청인 경우 Guide Strategy를 FULL_CODE_ALLOWED로 변경
        elif is_code_generation_request:
            guide_strategy = "FULL_CODE_ALLOWED"
            system_prompt = create_normal_system_prompt(
                status="SAFE",
                guide_strategy=guide_strategy,
                keywords=keywords_text,
                memory_summary=memory_text,
                problem_context=problem_context,
                is_code_generation_request=True
            )
        else:
            system_prompt = create_normal_system_prompt(
                status="SAFE",
                guide_strategy=guide_strategy or "LOGIC_HINT",
                keywords=keywords_text,
                memory_summary=memory_text,
                problem_context=problem_context,
                is_code_generation_request=False
            )
            logger.info(f"[prepare_writer_input] 시스템 프롬프트 생성 완료 - guide_strategy: {guide_strategy or 'LOGIC_HINT'}, 프롬프트 길이: {len(system_prompt)}")
            logger.debug(f"[prepare_writer_input] 시스템 프롬프트 (처음 500자): {system_prompt[:500]}...")
    
    # 최근 메시지 변환 (최대 10개)
    recent_messages = messages[-10:] if len(messages) > 10 else messages
    formatted_messages = []
    for msg in recent_messages:
        if hasattr(msg, 'content'):
            content = msg.content
            # 빈 content 필터링
            if content and str(content).strip():
                role = getattr(msg, 'type', 'user')
                if role == 'human':
                    role = 'user'
                elif role == 'ai':
                    role = 'assistant'
                formatted_messages.append({"role": role, "content": content})
    
    return {
        "system_prompt": system_prompt,
        "messages": formatted_messages,
        "human_message": human_message,
        "state": state,  # 후처리를 위해 state 전달
    }


def format_writer_messages(inputs: Dict[str, Any]) -> list:
    """메시지 리스트를 LangChain BaseMessage 객체로 변환"""
    import logging
    logger = logging.getLogger(__name__)
    
    chat_messages = []
    
    # 시스템 메시지 추가 (content가 비어있지 않은 경우에만)
    system_prompt = inputs.get("system_prompt")
    if system_prompt and str(system_prompt).strip():
        chat_messages.append(SystemMessage(content=system_prompt))
        logger.info(f"[format_writer_messages] 시스템 메시지 추가 - 길이: {len(str(system_prompt))}자")
        logger.debug(f"[format_writer_messages] 시스템 프롬프트 (처음 300자): {str(system_prompt)[:300]}...")
    else:
        logger.error(f"[format_writer_messages] ⚠️ 시스템 메시지가 비어있음 - system_prompt: {system_prompt}")
    
    # 이전 대화 메시지 변환 (content가 비어있지 않은 경우에만)
    messages_count = 0
    filtered_count = 0
    for msg in inputs.get("messages", []):
        messages_count += 1
        if isinstance(msg, dict):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # 빈 content 필터링
            if content and str(content).strip():
                if role == "system":
                    chat_messages.append(SystemMessage(content=content))
                elif role == "assistant" or role == "ai":
                    chat_messages.append(AIMessage(content=content))
                else:
                    chat_messages.append(HumanMessage(content=content))
            else:
                filtered_count += 1
                logger.debug(f"[format_writer_messages] 빈 메시지 필터링됨 - role: {role}, content: {content}")
        elif hasattr(msg, 'content'):
            # 이미 BaseMessage 객체인 경우 - 빈 content 필터링
            content = msg.content
            if content and str(content).strip():
                chat_messages.append(msg)
            else:
                filtered_count += 1
                logger.debug(f"[format_writer_messages] 빈 BaseMessage 필터링됨 - type: {type(msg)}, content: {content}")
    
    if filtered_count > 0:
        logger.info(f"[format_writer_messages] 총 {messages_count}개 메시지 중 {filtered_count}개 빈 메시지 필터링됨")
    
    # 현재 사용자 메시지 추가 (content가 비어있지 않은 경우에만)
    human_message = inputs.get("human_message")
    if human_message and str(human_message).strip():
        chat_messages.append(HumanMessage(content=human_message))
        logger.debug(f"[format_writer_messages] 사용자 메시지 추가 - 길이: {len(str(human_message))}")
    else:
        logger.warning(f"[format_writer_messages] 사용자 메시지가 비어있음 - human_message: {human_message}")
    
    # 모든 메시지가 비어있을 경우, Vertex AI의 "at least one parts field" 오류 방지를 위해 기본 메시지 추가
    if not chat_messages:
        logger.error(f"[format_writer_messages] 모든 메시지가 비어있음! 기본 메시지 추가")
        chat_messages.append(SystemMessage(content="안녕하세요. 무엇을 도와드릴까요?"))
    
    logger.info(f"[format_writer_messages] 최종 메시지 개수: {len(chat_messages)}개")
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
        
        # LLM 응답 상세 로깅 (디버깅용)
        if llm_response:
            logger.debug(f"[Writer LLM] LLM 응답 상세 - type: {type(llm_response)}, has_content: {hasattr(llm_response, 'content')}, content_type: {type(getattr(llm_response, 'content', None))}")
            if hasattr(llm_response, 'response_metadata'):
                logger.debug(f"[Writer LLM] response_metadata: {llm_response.response_metadata}")
        
        # 빈 응답 체크 및 처리
        if not ai_content or (isinstance(ai_content, str) and not ai_content.strip()):
            logger.warning(f"[Writer LLM] 빈 응답 감지 - LLM이 빈 응답을 반환했습니다. chain_result: {chain_result}, llm_response type: {type(llm_response)}")
            # 빈 응답인 경우 기본 메시지 제공
            ai_content = "죄송합니다. 응답을 생성할 수 없습니다. 다시 시도해주세요."
        
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


