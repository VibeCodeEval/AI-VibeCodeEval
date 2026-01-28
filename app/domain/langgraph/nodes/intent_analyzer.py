"""
노드 2: Intent Analyzer LLM
의도 분석 및 가드레일 검사 (2-Layer Guardrails)
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai import ChatVertexAI
from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import settings
from app.domain.langgraph.middleware import wrap_chain_with_middleware
from app.domain.langgraph.states import GuardrailCheck, MainGraphState
from app.domain.langgraph.utils.structured_output_parser import \
    parse_structured_output_async
from app.domain.langgraph.utils.token_tracking import (accumulate_tokens,
                                                       extract_token_usage)
from app.infrastructure.persistence.models.enums import IntentAnalyzerStatus


class IntentAnalysisResult(BaseModel):
    """Intent 분석 결과 (2-Layer Guardrails)"""

    # 새로운 필드 (Guide Strategy 기반)
    status: Literal["SAFE", "BLOCKED"] = Field(..., description="전체 안전 상태")
    block_reason: Literal["DIRECT_ANSWER", "JAILBREAK", "OFF_TOPIC"] | None = Field(
        None, description="차단 이유 (BLOCKED인 경우)"
    )
    request_type: Literal["CHAT", "SUBMISSION"] = Field(..., description="요청 유형")
    guide_strategy: (
        Literal[
            "SYNTAX_GUIDE", "LOGIC_HINT", "ROADMAP", "GENERATION", "FULL_CODE_ALLOWED"
        ]
        | None
    ) = Field(
        None,
        description="가이드 전략 (SAFE인 경우). GENERATION=인터페이스만, FULL_CODE_ALLOWED=맥락 기반 풀 코드 생성",
    )
    keywords: List[str] = Field(default_factory=list, description="핵심 키워드")

    # 기존 필드 (하위 호환성)
    is_submission_request: bool = Field(..., description="제출 요청인지 여부")
    guardrail_passed: bool = Field(..., description="가드레일 통과 여부")
    violation_message: str | None = Field(None, description="위반 시 메시지")
    reasoning: str = Field(..., description="분석 이유")

    @model_validator(mode="after")
    def validate_status_and_block_reason(self):
        """논리적 일관성 검증 및 기본값 설정"""
        # BLOCKED 상태인데 block_reason이 없는 경우 기본값 설정 (안전장치)
        if self.status == "BLOCKED" and not self.block_reason:
            # LLM이 block_reason을 제공하지 않은 경우 기본값 설정
            self.block_reason = "OFF_TOPIC"  # 가장 안전한 기본값

        # SAFE 상태인데 block_reason이 있는 경우 제거
        if self.status == "SAFE" and self.block_reason:
            self.block_reason = None

        return self


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
            temperature=0.3,
        )
    else:
        # AI Studio 사용 (API Key 방식, Free Tier)
        return ChatGoogleGenerativeAI(
            model=settings.DEFAULT_LLM_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.3,
        )


# Layer 1: 키워드 기반 빠른 검증 (정답 관련)
def quick_answer_detection(
    message: str,
    problem_context: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[str]] = None,
    turn_number: Optional[int] = None,
) -> Dict[str, Any] | None:
    """
    정답 관련 키워드 기반 빠른 검증 (LLM 호출 없음)
    맥락을 고려한 가드레일 검사

    Args:
        message: 사용자 메시지
        problem_context: 문제 정보 (문제별 키워드 동적 추가용)
        conversation_history: 이전 대화 히스토리 (최근 턴의 메시지 리스트)
        turn_number: 현재 턴 번호

    Returns:
        차단 결과 또는 None (통과)
    """
    message_lower = message.lower()

    # [수정] 구조/인터페이스/의사코드 관련 키워드는 Layer 2 분석으로 넘김 (차단하지 않음)
    safe_structural_keywords = [
        "인터페이스",
        "함수 정의",
        "함수 선언",
        "구조",
        "틀",
        "껍데기",
        "의사코드",
        "수도코드",
        "pseudo",
        "interface",
        "structure",
        "skeleton",
    ]

    # 구조적 요청 키워드가 있고, 직접적인 정답 요청("정답", "풀이")이 없으면 허용
    if any(safe_kw in message_lower for safe_kw in safe_structural_keywords):
        if not any(
            block_kw in message_lower
            for block_kw in ["정답", "풀이", "answer", "solution"]
        ):
            return None

    # 직접 답변 요청 패턴 (항상 차단)
    direct_answer_patterns = [
        # 한국어
        "정답 코드",
        "정답 알려줘",
        "답 코드",
        "완성된 코드",
        "핵심 코드",
        "로직 전체",
        "점화식 알려줘",
        "재귀 구조",
        "핵심 로직",
        "dp[x][vis]",
        "점화식은",
        "재귀는",
        "알고리즘 전체",
        # 영어
        "complete solution",
        "answer code",
        "entire code",
        "whole solution",
        "complete algorithm",
        "recurrence relation",
        "dp formula",
    ]

    # 맥락 기반 판단이 필요한 패턴
    context_sensitive_patterns = {
        "전체 코드": [
            "코드 작성",
            "코드 생성",
            "코드를 작성",
            "코드를 생성",
            "작성해주신 코드",
        ],
        "full code": [
            "코드 작성",
            "코드 생성",
            "코드를 작성",
            "코드를 생성",
            "작성해주신 코드",
        ],
        "whole code": [
            "코드 작성",
            "코드 생성",
            "코드를 작성",
            "코드를 생성",
            "작성해주신 코드",
        ],
    }

    # 힌트 요청 키워드 (학습 가이드 요청)
    hint_keywords = [
        "힌트",
        "가이드",
        "방향",
        "수립",
        "어떻게",
        "학습",
        "hint",
        "guide",
        "direction",
    ]

    # 직접 답변 요청 키워드
    direct_answer_keywords = [
        "알려줘",
        "알려",
        "뭐야",
        "뭐",
        "정답",
        "tell me",
        "what is",
        "show me",
    ]

    # 1. 직접 답변 요청 패턴 확인 (항상 차단)
    if any(pattern in message_lower for pattern in direct_answer_patterns):
        # 단, "힌트" 키워드가 함께 있으면 학습 가이드 요청으로 판단
        if not any(hint_kw in message_lower for hint_kw in hint_keywords):
            return {
                "status": "BLOCKED",
                "block_reason": "DIRECT_ANSWER",
                "request_type": "CHAT",
                "guide_strategy": None,
                "keywords": [],
                "is_submission_request": False,
                "guardrail_passed": False,
                "violation_message": "정답 코드 요청 패턴 감지",
                "reasoning": "정답 코드 요청 패턴 감지",
            }

    # 2. "점화식" 키워드 맥락 기반 판단
    if "점화식" in message_lower or "recurrence" in message_lower:
        # 직접 답변 요청 키워드 확인
        has_direct_answer_keyword = any(
            kw in message_lower for kw in direct_answer_keywords
        )
        # 힌트 요청 키워드 확인
        has_hint_keyword = any(kw in message_lower for kw in hint_keywords)

        # 직접 답변 요청이고 힌트 요청이 아닌 경우 차단
        if has_direct_answer_keyword and not has_hint_keyword:
            return {
                "status": "BLOCKED",
                "block_reason": "DIRECT_ANSWER",
                "request_type": "CHAT",
                "guide_strategy": None,
                "keywords": [],
                "is_submission_request": False,
                "guardrail_passed": False,
                "violation_message": "점화식 직접 요청 패턴 감지",
                "reasoning": "점화식 직접 요청 패턴 감지 (힌트 요청이 아님)",
            }
        # 힌트 요청인 경우 허용
        # (has_hint_keyword가 True이거나, "수립" 같은 학습 목적 키워드가 있는 경우)

    # 3. "전체 코드" 요청 맥락 기반 판단
    for pattern, code_generation_keywords in context_sensitive_patterns.items():
        if pattern in message_lower:
            # 이전 대화에서 코드 생성 요청이 있었는지 확인
            has_code_generation = False
            if conversation_history:
                # 최근 3턴 확인
                recent_history = (
                    conversation_history[-3:]
                    if len(conversation_history) > 3
                    else conversation_history
                )
                for turn in recent_history:
                    turn_lower = turn.lower()
                    if any(kw in turn_lower for kw in code_generation_keywords):
                        has_code_generation = True
                        break

            # 코드 생성 요청이 없었으면 차단
            if not has_code_generation:
                return {
                    "status": "BLOCKED",
                    "block_reason": "DIRECT_ANSWER",
                    "request_type": "CHAT",
                    "guide_strategy": None,
                    "keywords": [],
                    "is_submission_request": False,
                    "guardrail_passed": False,
                    "violation_message": "전체 코드 요청 패턴 감지 (이전 대화에 코드 생성 요청 없음)",
                    "reasoning": "전체 코드 요청 패턴 감지 (이전 대화에 코드 생성 요청 없음)",
                }
            # 코드 생성 요청이 있었으면 허용 (수정 후 확인 요청으로 판단)

    # 4. 문제별 정답 키워드 확인 (동적)
    problem_keywords = []
    if problem_context:
        # State에서 직접 키워드 가져오기 (하드코딩 또는 DB에서)
        keywords_from_context = problem_context.get("keywords", [])
        if keywords_from_context:
            problem_keywords.extend(keywords_from_context)
        else:
            # Fallback: 문제 ID/이름 기반 키워드 추론 (하위 호환성)
            problem_id = str(problem_context.get("problem_id", "")).lower()
            problem_name = str(problem_context.get("problem_name", "")).lower()

            # 백준 2098 (TSP)
            if (
                "2098" in problem_id
                or "tsp" in problem_name
                or "외판원" in problem_name
            ):
                problem_keywords.extend(
                    [
                        "외판원",
                        "tsp",
                        "traveling salesman",
                        "dp[현재도시][방문도시]",
                        "방문 상태",
                    ]
                )

    # 문제별 키워드가 정답 관련 키워드와 함께 사용된 경우 차단
    if problem_keywords:
        for keyword in problem_keywords:
            if keyword.lower() in message_lower:
                # 정답 관련 키워드 확인 (점화식, 재귀, 로직 등)
                answer_related_keywords = [
                    "점화식",
                    "recurrence",
                    "재귀",
                    "로직",
                    "알고리즘",
                    "solution",
                    "code",
                ]
                has_answer_related_keyword = any(
                    kw in message_lower for kw in answer_related_keywords
                )

                # 직접 답변 요청 키워드 확인
                has_direct_answer_keyword = any(
                    kw in message_lower for kw in direct_answer_keywords
                )

                # 힌트 요청 키워드 확인
                has_hint_keyword = any(kw in message_lower for kw in hint_keywords)

                # 문제 특정 키워드 + 정답 관련 키워드 조합 차단
                if has_answer_related_keyword:
                    # 힌트 요청 키워드가 있으면 허용
                    if not has_hint_keyword:
                        return {
                            "status": "BLOCKED",
                            "block_reason": "DIRECT_ANSWER",
                            "request_type": "CHAT",
                            "guide_strategy": None,
                            "keywords": [],
                            "is_submission_request": False,
                            "guardrail_passed": False,
                            "violation_message": "문제 특정 정답 요청 패턴 감지",
                            "reasoning": f"문제 특정 정답 요청 패턴 감지 ({keyword} + 정답 관련 키워드)",
                        }
                # 직접 답변 요청 키워드와 함께 사용된 경우도 차단
                elif has_direct_answer_keyword:
                    # 단, 힌트 요청 키워드가 함께 있으면 허용
                    if not has_hint_keyword:
                        return {
                            "status": "BLOCKED",
                            "block_reason": "DIRECT_ANSWER",
                            "request_type": "CHAT",
                            "guide_strategy": None,
                            "keywords": [],
                            "is_submission_request": False,
                            "guardrail_passed": False,
                            "violation_message": "문제 특정 정답 요청 패턴 감지",
                            "reasoning": f"문제 특정 정답 요청 패턴 감지 ({keyword})",
                        }

    return None  # 통과


# 시스템 프롬프트 템플릿 (문제 정보 포함)
def create_intent_analysis_system_prompt(
    problem_context: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Intent Analyzer 시스템 프롬프트 생성 (문제 정보 포함)

    YAML 파일에서 프롬프트 템플릿을 로드하고 변수를 치환합니다.

    Args:
        problem_context: 문제 정보 딕셔너리 (basic_info, constraints, ai_guide 포함)

    Returns:
        str: 시스템 프롬프트
    """
    from app.domain.langgraph.prompts import render_prompt

    # 문제 정보 추출
    basic_info = problem_context.get("basic_info", {}) if problem_context else {}
    constraints = problem_context.get("constraints", {}) if problem_context else {}
    ai_guide = problem_context.get("ai_guide", {}) if problem_context else {}

    problem_title = basic_info.get("title", "알 수 없음")
    problem_id = basic_info.get("problem_id", "")
    description_summary = basic_info.get("description_summary", "")
    input_format = basic_info.get("input_format", "")
    output_format = basic_info.get("output_format", "")
    logic_reasoning = constraints.get("logic_reasoning", "")
    key_algorithms = ai_guide.get("key_algorithms", [])
    algorithms_text = ", ".join(key_algorithms) if key_algorithms else "없음"
    solution_architecture = ai_guide.get("solution_architecture", "")

    # 문제 정보 섹션 (문제 정보가 있는 경우에만 추가)
    problem_info_section = ""
    if problem_context:
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

        if logic_reasoning:
            problem_info_parts.append(f"- 제약 조건 분석: {logic_reasoning}")

        if solution_architecture:
            problem_info_parts.append(f"- 솔루션 아키텍처: {solution_architecture}")

        problem_info_section = f"""
[문제 정보]
{chr(10).join(problem_info_parts)}

"""

    # 차단 기준 추가 항목 미리 계산 (에러 체크 및 디버깅 용이)
    additional_block_criteria = (
        f"- 문제 특성({algorithms_text})에 맞지 않는 알고리즘 요청 (예: 그리디 알고리즘으로 풀어줘)"
        if algorithms_text != "없음"
        else ""
    )

    # YAML 템플릿에서 프롬프트 렌더링
    return render_prompt(
        "intent_analyzer",
        problem_info_section=problem_info_section,
        problem_title=problem_title,
        algorithms_text=algorithms_text,
        additional_block_criteria=additional_block_criteria,
    )


# 프롬프트 템플릿 생성 함수 (동적 시스템 프롬프트 사용)
def create_intent_analysis_prompt(system_prompt: str) -> ChatPromptTemplate:
    """동적 시스템 프롬프트로 프롬프트 템플릿 생성"""
    return ChatPromptTemplate.from_messages(
        [("system", system_prompt), ("user", "{human_message}")]
    )


# 입력 전처리 함수
def prepare_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """입력을 Chain에 맞게 준비 (문제 정보 포함)"""
    import logging

    logger = logging.getLogger(__name__)

    try:
        state = inputs.get("state", {})
        problem_context = state.get("problem_context")

        # 문제 정보를 포함한 시스템 프롬프트 생성
        system_prompt = create_intent_analysis_system_prompt(problem_context)

        result = {
            "system_prompt": system_prompt,
            "human_message": inputs.get("human_message", ""),
        }
        logger.debug(
            f"[Chain] prepare_input 완료 - message 길이: {len(result['human_message'])}, problem_context 존재: {problem_context is not None}"
        )
        return result
    except Exception as e:
        logger.error(f"[Chain] prepare_input 에러: {str(e)}", exc_info=True)
        raise


# 출력 후처리 함수
def process_output(result: IntentAnalysisResult) -> Dict[str, Any]:
    """Chain 결과를 State 형식으로 변환"""
    import logging

    logger = logging.getLogger(__name__)

    try:
        # 새로운 status (SAFE/BLOCKED)를 기존 Enum 값으로 변환 (하위 호환성)
        # (model_validator에서 이미 block_reason 검증 및 기본값 설정 완료)
        if result.status == "BLOCKED":
            if result.block_reason == "OFF_TOPIC":
                intent_status = IntentAnalyzerStatus.FAILED_GUARDRAIL.value
            else:
                intent_status = IntentAnalyzerStatus.FAILED_GUARDRAIL.value
        elif result.request_type == "SUBMISSION":
            intent_status = IntentAnalyzerStatus.PASSED_SUBMIT.value
        else:
            intent_status = IntentAnalyzerStatus.PASSED_HINT.value

        output = {
            "intent_status": intent_status,
            "is_guardrail_failed": not result.guardrail_passed,
            "guardrail_message": result.violation_message,
            "is_submitted": result.is_submission_request,
            "guide_strategy": result.guide_strategy,
            "keywords": result.keywords,
            "updated_at": datetime.utcnow().isoformat(),
        }
        logger.debug(
            f"[Chain] process_output 완료 - status: {output['intent_status']}, guide_strategy: {output.get('guide_strategy')}"
        )
        return output
    except Exception as e:
        logger.error(f"[Chain] process_output 에러: {str(e)}", exc_info=True)
        raise


# Intent Analysis Chain 구성
# Chain: 입력 준비 -> 동적 프롬프트 생성 -> LLM (구조화된 출력) -> 출력 처리
# 주의: with_structured_output은 원본 응답 메타데이터를 보존하지 않으므로
# Chain 외부에서 원본 LLM을 먼저 호출하여 메타데이터 추출
llm = get_llm()
structured_llm = llm.with_structured_output(IntentAnalysisResult)


def format_messages(inputs: Dict[str, Any]) -> list:
    """
    동적 프롬프트로 메시지 포맷팅 (BaseMessage 리스트 반환)

    시스템 프롬프트는 이미 포맷팅된 문자열이므로, ChatPromptTemplate을 사용하면
    JSON 예시의 중괄호가 포맷 키로 인식되어 KeyError가 발생할 수 있습니다.
    따라서 SystemMessage와 HumanMessage를 직접 생성하여 템플릿 포맷팅을 우회합니다.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    system_prompt = inputs.get("system_prompt", "")
    human_message = inputs.get("human_message", "")

    # 시스템 프롬프트는 이미 포맷팅된 문자열이므로 직접 SystemMessage로 생성
    # HumanMessage도 직접 생성하여 템플릿 포맷팅 우회
    return [SystemMessage(content=system_prompt), HumanMessage(content=human_message)]


# 기본 Chain 구성 (구조화된 출력만 처리, 원본 응답은 Chain 외부에서 추출)
def extract_llm_response_and_process(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """LLM 응답 객체와 처리된 결과를 함께 반환"""
    llm_response = inputs.get("llm_response")
    processed = process_output(llm_response)
    # LLM 응답 객체를 processed에 포함 (토큰 추출용)
    # 주의: with_structured_output의 결과는 Pydantic 모델이므로
    # 원본 응답 메타데이터가 없음 - Chain 외부에서 원본 LLM 호출 필요
    processed["_llm_response"] = llm_response
    return processed


_base_intent_analysis_chain = (
    RunnableLambda(prepare_input)
    | RunnableLambda(format_messages)
    | structured_llm
    | RunnableLambda(lambda x: {"llm_response": x})
    | RunnableLambda(extract_llm_response_and_process)
)

# Middleware 적용 (Factory 함수 사용)
intent_analysis_chain = wrap_chain_with_middleware(
    _base_intent_analysis_chain, name="Intent Analyzer"
)


async def intent_analyzer(state: MainGraphState) -> Dict[str, Any]:
    """
    의도 분석 및 가드레일 검사 (2-Layer Guardrails)

    Layer 1: 키워드 기반 빠른 검증 (정답 관련)
    Layer 2: LLM 기반 상세 분석
    """
    import logging

    logger = logging.getLogger(__name__)

    human_message = state.get("human_message", "")

    logger.info(f"[Intent Analyzer] 메시지 분석 시작: {human_message[:100]}...")

    if not human_message:
        logger.warning("[Intent Analyzer] 빈 메시지 - PASSED_HINT로 처리")
        return {
            "intent_status": IntentAnalyzerStatus.PASSED_HINT.value,
            "is_guardrail_failed": False,
            "guide_strategy": None,
            "keywords": [],
        }

    try:
        # Layer 1: 키워드 기반 빠른 검증 (정답 관련)
        # State에서 문제 정보 가져오기
        problem_context = {
            "problem_id": state.get("problem_id", str(state.get("spec_id"))),
            "problem_name": state.get("problem_name", ""),
            "keywords": state.get(
                "problem_keywords", []
            ),  # 문제별 키워드 (하드코딩 또는 DB에서)
        }

        # 대화 히스토리 추출 (맥락 기반 가드레일용)
        conversation_history = []
        messages = state.get("messages", [])
        if messages:
            # LangGraph messages는 BaseMessage 객체 리스트
            # content 속성을 사용하여 텍스트 추출
            for msg in messages:
                if hasattr(msg, "content"):
                    content = msg.content
                    if isinstance(content, str):
                        conversation_history.append(content)
                    elif isinstance(content, list):
                        # 멀티모달 메시지의 경우 텍스트 부분만 추출
                        text_parts = [
                            item.get("text", "")
                            for item in content
                            if isinstance(item, dict) and "text" in item
                        ]
                        if text_parts:
                            conversation_history.append(" ".join(text_parts))

        # 현재 턴 번호
        turn_number = state.get("current_turn", 0)

        quick_result = quick_answer_detection(
            human_message,
            problem_context,
            conversation_history=conversation_history if conversation_history else None,
            turn_number=turn_number,
        )

        if quick_result:
            logger.info(
                f"[Intent Analyzer] Layer 1 차단 - reason: {quick_result['block_reason']}"
            )
            # quick_result를 State 형식으로 변환
            return {
                "intent_status": IntentAnalyzerStatus.FAILED_GUARDRAIL.value,
                "is_guardrail_failed": True,
                "guardrail_message": quick_result["violation_message"],
                "is_submitted": quick_result["is_submission_request"],
                "guide_strategy": quick_result.get("guide_strategy"),
                "keywords": quick_result.get("keywords", []),
                "updated_at": datetime.utcnow().isoformat(),
            }

        # Layer 2: LLM 기반 상세 분석
        logger.debug("[Intent Analyzer] Layer 1 통과 - Layer 2 LLM 분석 진행")

        # 입력 준비
        chain_input = {"state": state, "human_message": human_message}
        prepared_input = prepare_input(chain_input)

        # 메시지 포맷팅
        formatted_messages = format_messages(prepared_input)

        # 원본 LLM 호출 (1회만 - 토큰 추출 + JSON 파싱)
        raw_response = await llm.ainvoke(formatted_messages)

        # 토큰 사용량 추출 및 State에 누적
        tokens = extract_token_usage(raw_response)
        if tokens:
            accumulate_tokens(state, tokens, token_type="chat")
            logger.debug(
                f"[Intent Analyzer] 토큰 사용량 추출 성공 - prompt: {tokens.get('prompt_tokens')}, completion: {tokens.get('completion_tokens')}, total: {tokens.get('total_tokens')}"
            )
        else:
            logger.warning(
                f"[Intent Analyzer] 토큰 사용량 추출 실패 - raw_response 타입: {type(raw_response)}"
            )

        # 원본 응답을 구조화된 출력으로 파싱
        try:
            structured_llm = llm.with_structured_output(IntentAnalysisResult)
            structured_result = await parse_structured_output_async(
                raw_response=raw_response,
                model_class=IntentAnalysisResult,
                fallback_llm=structured_llm,
                formatted_messages=formatted_messages,
            )
        except Exception as parse_error:
            logger.error(
                f"[Intent Analyzer] 구조화된 출력 파싱 실패: {str(parse_error)}",
                exc_info=True,
            )
            # 파싱 실패 시 fallback으로 구조화된 출력 Chain 사용
            logger.info("[Intent Analyzer] Fallback: 구조화된 출력 Chain 사용")
            structured_llm = llm.with_structured_output(IntentAnalysisResult)
            structured_result = await structured_llm.ainvoke(formatted_messages)

        # 출력 처리 (State 형식으로 변환)
        result = process_output(structured_result)

        # State에 누적된 토큰 정보를 result에 포함 (LangGraph 병합을 위해)
        if "chat_tokens" in state:
            result["chat_tokens"] = state["chat_tokens"]

        logger.info(
            f"[Intent Analyzer] 분석 결과 - status: {result['intent_status']}, guardrail_passed: {not result['is_guardrail_failed']}, is_submission: {result['is_submitted']}, guide_strategy: {result.get('guide_strategy')}"
        )

        return result

    except Exception as e:
        logger.error(f"[Intent Analyzer] 에러 발생: {str(e)}", exc_info=True)
        # Rate limit 등의 에러 처리
        error_msg = str(e).lower()
        if "rate" in error_msg or "quota" in error_msg:
            logger.warning(
                f"[Intent Analyzer] Rate limit 초과 - FAILED_RATE_LIMIT로 처리"
            )
            return {
                "intent_status": IntentAnalyzerStatus.FAILED_RATE_LIMIT.value,
                "is_guardrail_failed": False,
                "error_message": str(e),
                "guide_strategy": None,
                "keywords": [],
            }

        # 다른 에러는 재발생
        logger.error(f"[Intent Analyzer] 예상치 못한 에러 - 재발생: {str(e)}")
        raise
