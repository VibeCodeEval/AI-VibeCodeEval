"""
노드 3: Writer LLM
AI 답변 생성 (Runnable & Chain 구조)
"""

from datetime import datetime
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai import ChatVertexAI

from app.core.config import settings
from app.domain.langgraph.middleware import wrap_chain_with_middleware
from app.domain.langgraph.states import MainGraphState
from app.domain.langgraph.utils.token_tracking import (accumulate_tokens,
                                                       extract_token_usage)
from app.infrastructure.persistence.models.enums import WriterResponseStatus


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


# 시스템 프롬프트 템플릿 - YAML에서 로드
def get_guardrail_system_prompt(guardrail_message: str) -> str:
    """가드레일 위반 시 거절 응답 프롬프트를 YAML에서 로드하여 반환"""
    from app.domain.langgraph.prompts import render_prompt

    return render_prompt("writer_guardrail", guardrail_message=guardrail_message)


def create_spec_based_system_prompt(
    problem_context: Dict[str, Any],
    spec_result: Dict[str, Any],
    modified_code: Optional[str],
    memory_summary: str,
) -> str:
    """
    Spec 기반 코드 생성용 시스템 프롬프트 생성 (Phase 6)
    
    사용자 프롬프트의 Spec 충족도에 따라 코드 품질을 조절합니다.
    
    Args:
        problem_context: 문제 정보
        spec_result: Spec Extractor 결과
        modified_code: Error Injector가 생성한 변형 코드
        memory_summary: 이전 대화 요약
        
    Returns:
        str: 시스템 프롬프트
    """
    from app.domain.langgraph.prompts import load_prompt, render_prompt
    
    # Spec 분석 결과 추출
    specified_requirements = spec_result.get("specified_requirements", [])
    missing_requirements = spec_result.get("missing_requirements", [])
    prompt_quality_score = spec_result.get("prompt_quality_score", 50.0)
    
    # 문제 정보 추출
    basic_info = problem_context.get("basic_info", {})
    problem_title = basic_info.get("title", "알 수 없음")
    
    # 코드 결정: 품질 점수에 따라 다른 코드 제공
    if modified_code and prompt_quality_score < 80:
        code_to_provide = modified_code
    else:
        # 높은 품질이면 정답 코드 제공
        code_to_provide = problem_context.get("solution_code", "# 정답 코드 없음")
    
    # 명시된 요구사항 텍스트
    specified_text = ", ".join(specified_requirements) if specified_requirements else "없음"
    
    # 누락된 요구사항 텍스트
    if missing_requirements:
        missing_text = ", ".join([
            f"{mr.get('category', '알 수 없음')} ({mr.get('importance', 'MEDIUM')})"
            for mr in missing_requirements
        ])
    else:
        missing_text = "없음 (모든 요구사항 충족)"
    
    # 기본 프롬프트 섹션
    base_prompt = f"""# Role Definition

당신은 '바이브코딩'의 **AI 시험 감독관(AI Test Proctor)**입니다.

**미션**: 사용자의 프롬프트 품질(Spec 충족도)에 따라 적절한 수준의 코드를 제공합니다.

**톤앤매너**:
- **건조하고 객관적임 (Dry & Objective)**: 감정을 배제하고 시스템 메시지처럼 응답.
- **코드 중심**: 요청에 따라 코드를 제공하되, 품질은 Spec 충족도에 비례.

[문제 정보]
- 문제: {problem_title}

**현재 상태**:
- Status: SAFE
- Strategy: SPEC_BASED_CODE

# 📝 Spec 기반 코드 생성 모드

## Spec 분석 결과
- 명시된 요구사항: {specified_text}
- 누락된 요구사항: {missing_text}
- 프롬프트 품질 점수: {prompt_quality_score:.1f}/100

## 코드 생성 지침

"""

    # 품질 점수에 따른 지침 추가
    if prompt_quality_score >= 80:
        base_prompt += """### 품질 점수 80-100 (우수한 프롬프트)
- 완전한 정답 코드를 제공합니다.
- 모든 요구사항이 충족되었습니다.
- 주석을 포함한 깔끔한 코드를 제공합니다.

"""
    elif prompt_quality_score >= 50:
        base_prompt += """### 품질 점수 50-79 (보통 프롬프트)
- 핵심 로직은 제공하되, 누락된 Spec 부분은 TODO 주석으로 표시합니다.
- 일부 최적화가 빠진 코드를 제공합니다.
- 개선 방향 힌트를 함께 제공합니다.

**개선 제안**: 다음 요구사항을 명시하면 더 완전한 코드를 받을 수 있습니다:
""" + missing_text + "\n\n"
    else:
        base_prompt += """### 품질 점수 0-49 (미흡한 프롬프트)
- 함수 시그니처와 기본 구조만 제공합니다.
- 핵심 로직은 TODO로 표시합니다.
- Spec을 더 명확히 해달라는 안내를 제공합니다.

**안내**: 더 구체적인 요구사항을 명시해주세요. 예를 들어:
- 사용할 알고리즘 (예: DP, 비트마스킹)
- 시간복잡도 요구사항
- 상태 정의 방식
- 점화식 힌트

"""

    # 코드 섹션 추가
    base_prompt += f"""## 제공 코드

```python
{code_to_provide}
```

# Output Format

**[Code]** 헤더를 사용하여 위 코드를 제공하세요.
품질 점수가 낮은 경우, 코드 아래에 개선 방향을 간단히 안내하세요.

"""

    # 메모리 요약 추가
    if memory_summary:
        base_prompt += f"\n이전 대화 요약:\n{memory_summary}"
    
    return base_prompt


def create_normal_system_prompt(
    status: str,
    guide_strategy: str,
    keywords: str,
    memory_summary: str,
    problem_context: Optional[Dict[str, Any]] = None,
    is_code_generation_request: bool = False,
) -> str:
    """
    Writer LLM 시스템 프롬프트 생성 (문제 정보 포함)

    YAML 파일에서 프롬프트 템플릿을 로드하고 변수를 치환합니다.

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
    from app.domain.langgraph.prompts import load_prompt, render_prompt

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
            f"- 필수 알고리즘: {algorithms_text}",
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
            common_pitfalls_text = "\n".join(
                [f"- {pitfall}" for pitfall in common_pitfalls]
            )
            hint_roadmap_section += f"""
[자주 틀리는 실수 (참고용)]
{common_pitfalls_text}

"""
    else:
        problem_info_section = ""
        hint_roadmap_section = ""

    # 코드 생성 요청인 경우 추가 안내 (FULL_CODE_ALLOWED 전략일 때만)
    code_generation_section = ""
    if guide_strategy == "FULL_CODE_ALLOWED":
        # YAML에서 코드 생성 섹션 템플릿 로드
        yaml_data = load_prompt("writer_normal")
        code_generation_section = yaml_data.get("code_generation_section_template", "")

    # YAML 템플릿에서 프롬프트 렌더링
    return render_prompt(
        "writer_normal",
        problem_info_section=problem_info_section,
        status=status,
        guide_strategy=guide_strategy,
        code_generation_section=code_generation_section,
        hint_roadmap_section=hint_roadmap_section,
        memory_summary=memory_summary,
    )


def prepare_writer_input(state: MainGraphState) -> Dict[str, Any]:
    """Writer Chain 입력 준비 (Guide Strategy 기반 + Spec 기반 코드 생성)"""
    human_message = state.get("human_message", "")
    messages = state.get("messages", [])
    memory_summary = state.get("memory_summary", "")
    is_guardrail_failed = state.get("is_guardrail_failed", False)
    guardrail_message = state.get("guardrail_message", "")
    
    # Phase 6: Spec 기반 코드 생성 관련 상태
    spec_result = state.get("spec_result")
    modified_code = state.get("modified_code")

    # Guide Strategy 정보 가져오기
    guide_strategy_raw = state.get("guide_strategy")
    guide_strategy = guide_strategy_raw or "LOGIC_HINT"  # None인 경우 기본값 사용
    keywords = state.get("keywords", [])
    problem_context = state.get("problem_context")

    import logging

    logger = logging.getLogger(__name__)
    if guide_strategy_raw is None:
        logger.info(
            f"[prepare_writer_input] guide_strategy가 None이므로 기본값 'LOGIC_HINT' 사용"
        )
    else:
        logger.debug(f"[prepare_writer_input] guide_strategy: {guide_strategy}")

    # 코드 생성 요청 감지 (맥락 기반)
    is_code_generation_request = False
    if not is_guardrail_failed:
        message_lower = human_message.lower()
        code_generation_keywords = [
            "코드 작성",
            "코드 생성",
            "코드를 작성",
            "코드를 생성",
            "코드 작성해",
            "코드 생성해",
        ]

        # 코드 생성 요청 키워드 확인
        if any(kw in message_lower for kw in code_generation_keywords):
            # 이전 대화에서 힌트나 점화식이 논의되었는지 확인
            has_previous_context = False
            if messages:
                # 최근 3턴 확인
                recent_messages = messages[-6:] if len(messages) > 6 else messages
                for msg in recent_messages:
                    if hasattr(msg, "content"):
                        content = str(msg.content).lower()
                        # 힌트, 점화식, 접근 방식 등이 논의되었는지 확인
                        context_keywords = [
                            "힌트",
                            "점화식",
                            "접근",
                            "방법",
                            "hint",
                            "recurrence",
                            "approach",
                        ]
                        if any(ck in content for ck in context_keywords):
                            has_previous_context = True
                            break

            # 이전 맥락이 있거나, 명시적으로 이전 대화를 참조하는 경우
            if has_previous_context or any(
                ref in message_lower
                for ref in ["제안해주신", "이전", "앞서", "말한", "바탕으로"]
            ):
                is_code_generation_request = True

    # 시스템 프롬프트 선택
    if is_guardrail_failed:
        system_prompt = get_guardrail_system_prompt(
            guardrail_message=guardrail_message or "부적절한 요청"
        )
    else:
        memory_text = f"\n\n이전 대화 요약:\n{memory_summary}" if memory_summary else ""
        keywords_text = ", ".join(keywords) if keywords else "없음"

        # 제출 요청 처리
        request_type = state.get("request_type", "CHAT")
        if request_type == "SUBMISSION":
            # 제출 요청은 별도 처리 (보통 제출 노드에서 처리하지만, Writer가 확인 메시지를 해야 한다면)
            # YAML에서 제출 템플릿 로드
            from app.domain.langgraph.prompts import load_prompt

            yaml_data = load_prompt("writer_normal")
            system_prompt = yaml_data.get("submission_template", "")
        # Phase 6: Spec 기반 코드 생성 모드
        elif spec_result and modified_code:
            # Spec Extractor + Error Injector 결과가 있으면 Spec 기반 코드 생성
            logger.info(
                f"[prepare_writer_input] Spec 기반 코드 생성 모드 - "
                f"품질점수: {spec_result.get('prompt_quality_score', 0)}"
            )
            system_prompt = create_spec_based_system_prompt(
                problem_context=problem_context or {},
                spec_result=spec_result,
                modified_code=modified_code,
                memory_summary=memory_text,
            )
            guide_strategy = "SPEC_BASED_CODE"
        # 코드 생성 요청인 경우 Guide Strategy를 FULL_CODE_ALLOWED로 변경
        elif is_code_generation_request:
            guide_strategy = "FULL_CODE_ALLOWED"
            system_prompt = create_normal_system_prompt(
                status="SAFE",
                guide_strategy=guide_strategy,
                keywords=keywords_text,
                memory_summary=memory_text,
                problem_context=problem_context,
                is_code_generation_request=True,
            )
        else:
            system_prompt = create_normal_system_prompt(
                status="SAFE",
                guide_strategy=guide_strategy or "LOGIC_HINT",
                keywords=keywords_text,
                memory_summary=memory_text,
                problem_context=problem_context,
                is_code_generation_request=False,
            )
            logger.info(
                f"[prepare_writer_input] 시스템 프롬프트 생성 완료 - guide_strategy: {guide_strategy or 'LOGIC_HINT'}, 프롬프트 길이: {len(system_prompt)}"
            )
            logger.debug(
                f"[prepare_writer_input] 시스템 프롬프트 (처음 500자): {system_prompt[:500]}..."
            )

    # 최근 메시지 변환 (최대 10개)
    recent_messages = messages[-10:] if len(messages) > 10 else messages
    formatted_messages = []
    for msg in recent_messages:
        if hasattr(msg, "content"):
            content = msg.content
            # 빈 content 필터링
            if content and str(content).strip():
                role = getattr(msg, "type", "user")
                if role == "human":
                    role = "user"
                elif role == "ai":
                    role = "assistant"
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
        logger.info(
            f"[format_writer_messages] 시스템 메시지 추가 - 길이: {len(str(system_prompt))}자"
        )
        logger.debug(
            f"[format_writer_messages] 시스템 프롬프트 (처음 300자): {str(system_prompt)[:300]}..."
        )
    else:
        logger.error(
            f"[format_writer_messages] ⚠️ 시스템 메시지가 비어있음 - system_prompt: {system_prompt}"
        )

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
                logger.debug(
                    f"[format_writer_messages] 빈 메시지 필터링됨 - role: {role}, content: {content}"
                )
        elif hasattr(msg, "content"):
            # 이미 BaseMessage 객체인 경우 - 빈 content 필터링
            content = msg.content
            if content and str(content).strip():
                chat_messages.append(msg)
            else:
                filtered_count += 1
                logger.debug(
                    f"[format_writer_messages] 빈 BaseMessage 필터링됨 - type: {type(msg)}, content: {content}"
                )

    if filtered_count > 0:
        logger.info(
            f"[format_writer_messages] 총 {messages_count}개 메시지 중 {filtered_count}개 빈 메시지 필터링됨"
        )

    # 현재 사용자 메시지 추가 (content가 비어있지 않은 경우에만)
    human_message = inputs.get("human_message")
    if human_message and str(human_message).strip():
        chat_messages.append(HumanMessage(content=human_message))
        logger.debug(
            f"[format_writer_messages] 사용자 메시지 추가 - 길이: {len(str(human_message))}"
        )
    else:
        logger.warning(
            f"[format_writer_messages] 사용자 메시지가 비어있음 - human_message: {human_message}"
        )

    # 모든 메시지가 비어있을 경우, Vertex AI의 "at least one parts field" 오류 방지를 위해 기본 메시지 추가
    if not chat_messages:
        logger.error(
            f"[format_writer_messages] 모든 메시지가 비어있음! 기본 메시지 추가"
        )
        chat_messages.append(SystemMessage(content="안녕하세요. 무엇을 도와드릴까요?"))

    logger.info(f"[format_writer_messages] 최종 메시지 개수: {len(chat_messages)}개")
    return chat_messages


def extract_content(response: Any) -> Dict[str, Any]:
    """LLM 응답에서 내용 추출"""
    ai_content = response.content if hasattr(response, "content") else str(response)
    return {
        "ai_content": ai_content,
        "state": response.state if hasattr(response, "state") else None,
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
            ai_content = (
                response.content if hasattr(response, "content") else str(response)
            )
            return {
                "ai_content": ai_content,
                "_llm_response": response,  # 토큰 추출용 - LLM 응답 객체 그대로 전달
            }

        _base_writer_chain = (
            RunnableLambda(prepare_writer_input)
            | RunnableLambda(format_writer_messages)
            | _writer_llm  # LLM 호출 - AIMessage 객체 반환
            | RunnableLambda(
                extract_content_with_response
            )  # 내용 추출 및 응답 객체 보존
        )

        # Middleware 적용 (Factory 함수 사용)
        _writer_chain = wrap_chain_with_middleware(
            _base_writer_chain, name="Writer LLM"
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

    logger.info(
        f"[Writer LLM] 답변 생성 시작 - message: {human_message[:100]}..., guardrail_failed: {is_guardrail_failed}"
    )

    try:
        # Writer Chain 실행 (캐싱된 Chain 사용)
        chain = get_writer_chain()
        chain_result = await chain.ainvoke(state)

        # Chain 결과에서 내용과 LLM 응답 객체 분리
        ai_content = (
            chain_result.get("ai_content", "")
            if isinstance(chain_result, dict)
            else str(chain_result)
        )
        llm_response = (
            chain_result.get("_llm_response")
            if isinstance(chain_result, dict)
            else None
        )

        # LLM 응답 상세 로깅 (디버깅용)
        if llm_response:
            logger.debug(
                f"[Writer LLM] LLM 응답 상세 - type: {type(llm_response)}, has_content: {hasattr(llm_response, 'content')}, content_type: {type(getattr(llm_response, 'content', None))}"
            )
            if hasattr(llm_response, "response_metadata"):
                logger.debug(
                    f"[Writer LLM] response_metadata: {llm_response.response_metadata}"
                )

        # 빈 응답 체크 및 처리
        if not ai_content or (isinstance(ai_content, str) and not ai_content.strip()):
            logger.warning(
                f"[Writer LLM] 빈 응답 감지 - LLM이 빈 응답을 반환했습니다. chain_result: {chain_result}, llm_response type: {type(llm_response)}"
            )
            # 빈 응답인 경우 기본 메시지 제공
            ai_content = "죄송합니다. 응답을 생성할 수 없습니다. 다시 시도해주세요."

        # 토큰 사용량 추출 및 State에 누적
        if llm_response:
            tokens = extract_token_usage(llm_response)
            if tokens:
                accumulate_tokens(state, tokens, token_type="chat")
                logger.debug(
                    f"[Writer LLM] 토큰 사용량 - prompt: {tokens.get('prompt_tokens')}, completion: {tokens.get('completion_tokens')}, total: {tokens.get('total_tokens')}"
                )

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
            import asyncio

            from app.infrastructure.cache.redis_client import redis_client

            # 비동기로 턴 매핑 저장 (실패해도 메인 플로우 중단 안 함)
            asyncio.create_task(
                redis_client.save_turn_mapping(
                    session_id=session_id,
                    turn=current_turn,
                    start_msg_idx=start_msg_idx,
                    end_msg_idx=end_msg_idx,
                )
            )
            logger.info(
                f"[Writer LLM] 턴 매핑 저장 시작 - turn: {current_turn}, indices: [{start_msg_idx}, {end_msg_idx}]"
            )
        except Exception as e:
            logger.warning(f"[Writer LLM] 턴 매핑 저장 실패 (무시): {str(e)}")

        # messages 배열에 turn 정보 포함 (4번 노드 평가를 위해)
        # LangChain BaseMessage 객체를 직접 생성하여 turn 속성 보존
        from langchain_core.messages import AIMessage, HumanMessage

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
