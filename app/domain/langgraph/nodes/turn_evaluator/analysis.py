import logging
import re
from typing import Dict, Any

from app.domain.langgraph.states import EvalTurnState, IntentClassification
from app.infrastructure.persistence.models.enums import CodeIntentType
from app.domain.langgraph.nodes.turn_evaluator.utils import get_llm
from app.domain.langgraph.utils.token_tracking import extract_token_usage, accumulate_tokens
from app.domain.langgraph.utils.structured_output_parser import parse_structured_output_async
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)


def has_xml_tags(text: str) -> bool:
    """XML 태그 사용 여부 확인"""
    xml_pattern = r'<[^>]+>'
    return bool(re.search(xml_pattern, text))


def has_role_content_tags(text: str) -> bool:
    """<Role> 또는 <Content> 태그가 있는지 확인"""
    return bool(re.search(r'<Role>|<Content>', text, re.IGNORECASE))

async def intent_analysis(state: EvalTurnState) -> Dict[str, Any]:
    """
    4.0: Intent Analysis
    8가지 코드 패턴 분류
    
    [토큰 추적 개선]
    - with_structured_output은 원본 응답 메타데이터를 보존하지 않음
    - 원본 LLM을 먼저 호출하여 메타데이터 추출 후, 수동으로 파싱
    """
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.0 Intent Analysis] 진입 - session_id: {session_id}, turn: {turn}")
    
    human_message = state.get("human_message", "")
    ai_message = state.get("ai_message", "")
    
    llm = get_llm()
    structured_llm = llm.with_structured_output(IntentClassification)
    
    # 턴 번호와 XML 태그 정보 추출
    is_first_turn = (turn == 1)
    has_xml = has_xml_tags(human_message)
    has_role_content = has_role_content_tags(human_message)
    
    # 첫 턴 및 XML 태그 기반 우선순위 조정
    if is_first_turn:
        priority_note = """
**⚠️ 첫 턴 특별 규칙**:
- 첫 턴(turn=1)에서는 FOLLOW_UP을 선택할 수 없습니다. (이전 대화가 없으므로 후속 질문 불가능)
- <Role> 또는 <Content> 태그가 있으면 SYSTEM_PROMPT 또는 RULE_SETTING을 우선 고려하세요.
- 규칙 설정 중에 코드 예시를 요청하는 것은 RULE_SETTING입니다. (즉시 실행 가능한 코드 생성이 아닌 경우)
"""
    else:
        priority_note = ""
    
    if has_role_content:
        xml_hint = """
**XML 태그 힌트**: <Role> 또는 <Content> 태그가 감지되었습니다.
이는 SYSTEM_PROMPT 또는 RULE_SETTING 의도를 강하게 시사합니다.
"""
    else:
        xml_hint = ""
    
    system_prompt = f"""당신은 코딩 대화의 의도를 분류하는 전문가입니다.
사용자와 AI의 대화를 분석하여 다음 8가지 중 가장 적절한 의도를 **단일 선택**하세요.

{priority_note}{xml_hint}
**의도 우선순위 규칙** (우선순위가 높은 것을 선택):
1. GENERATION (최우선): 즉시 실행 가능한 코드 생성이 목적이면 최우선
2. OPTIMIZATION: 기존 코드 개선
3. DEBUGGING: 버그 수정
4. TEST_CASE: 테스트 작성
5. RULE_SETTING: 제약조건 명시, 향후 코드 생성에 대한 규칙 설정
6. SYSTEM_PROMPT: 역할 정의
7. HINT_OR_QUERY: 질문/힌트
8. FOLLOW_UP: 후속 질문 (⚠️ 첫 턴에서는 선택 불가)

**의도 정의 및 구분 기준**:
1. SYSTEM_PROMPT: 시스템 프롬프트 설정, AI 역할/페르소나 정의, 답변 스타일 지정
   - 예: "<Role>너는 문제 분해 전문가다</Role>"
   - <Role> 태그가 있으면 SYSTEM_PROMPT를 우선 고려

2. RULE_SETTING: 규칙 설정, 요구사항 정의, 제약조건 설명
   - **핵심**: 현재 코드를 생성하는 것이 아니라, 향후 코드 생성에 대한 규칙/제약조건을 설정하는 것
   - **중요 구분**: "설명해줘", "알려줘", "진행해봐" 같은 동작 요청은 RULE_SETTING이 아님
   - 예: "Interface 구조나 pesudo code로 제시해줘야한다" → RULE_SETTING (향후 코드 생성 규칙)
   - 예: "한 번에 하나씩 수행해야 한다" → RULE_SETTING (작업 순서 규칙)
   - 예: "각 전략에서 구조는 Interface구조나 pesudo code로 제시해줘야한다" → RULE_SETTING (출력 형식 규칙)
   - ❌ "다음 내용 진행해보면서 설명해" → RULE_SETTING 아님 (HINT_OR_QUERY 또는 FOLLOW_UP)
   - ❌ "진행해봐" → RULE_SETTING 아님 (FOLLOW_UP 또는 GENERATION)
   - <Content> 태그가 있으면 RULE_SETTING을 우선 고려
   - ⚠️ "코드로 제시"라는 표현이 있어도, 즉시 실행 가능한 코드 생성이 아니라 규칙 설정이면 RULE_SETTING

3. GENERATION: 새로운 코드 생성 요청
   - **핵심**: 즉시 실행 가능한 코드를 생성하라는 명시적 요청
   - 예: "이 함수를 구현해줘", "코드를 작성해줘", "진행해봐" (이전 맥락에서 코드 생성 의미)
   - ⚠️ 규칙 설정 중에 코드 예시를 요청하는 것은 GENERATION이 아닌 RULE_SETTING

4. OPTIMIZATION: 기존 코드 최적화, 성능 개선
5. DEBUGGING: 버그 수정, 오류 해결
6. TEST_CASE: 테스트 케이스 작성, 테스트 관련
7. HINT_OR_QUERY: 힌트 요청, 질문, 설명 요청
   - **핵심**: 개념 설명, 방법론 질문, 정보 요청
   - 예: "비트마스킹에 대한 개념 간단히 설명해" → HINT_OR_QUERY
   - 예: "다음 내용 진행해보면서 비트마스킹에 대한 개념 간단히 설명해" → HINT_OR_QUERY (설명 요청이 주 목적)
   - ❌ "진행해봐"만 있으면 HINT_OR_QUERY 아님 (FOLLOW_UP 또는 GENERATION)
8. FOLLOW_UP: 후속 질문, 추가 요청, 확인
   - **핵심**: 이전 대화를 참조하여 다음 단계를 진행하거나 확인하는 것
   - 예: "진행해봐" (이전 대화 맥락에서 다음 단계 진행) → FOLLOW_UP
   - 예: "그럼 다음은?" → FOLLOW_UP
   - ⚠️ 첫 턴(turn=1)에서는 선택 불가 (이전 대화가 없으므로)

**구분 예시**:
- "Interface 구조나 pesudo code로 제시해줘야한다" → RULE_SETTING (향후 코드 생성 규칙)
- "이 함수를 구현해줘" → GENERATION (즉시 코드 생성)
- "코드를 작성하고 최적화해주세요" → GENERATION (코드 생성이 최우선 목적)
- "비트마스킹에 대한 개념 간단히 설명해" → HINT_OR_QUERY (설명 요청)
- "다음 내용 진행해보면서 비트마스킹에 대한 개념 간단히 설명해" → HINT_OR_QUERY (설명 요청이 주 목적)
- "진행해봐" (이전 대화 맥락 있음) → FOLLOW_UP (후속 진행 요청)
- "어, 진행해봐" → FOLLOW_UP (이전 대화 맥락에서 다음 단계 진행)
- "<Role>너는 전문가다</Role><Content>규칙을 설정한다</Content>" → SYSTEM_PROMPT 또는 RULE_SETTING

**중요**: 여러 의도가 관련되어 있어도, 우선순위가 가장 높은 **단일 의도만** 선택하세요."""

    prompt = f"사용자: {human_message}\n\nAI 응답: {ai_message}"
    
    try:
        # 원본 LLM 호출 (메타데이터 보존을 위해)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        
        # 원본 LLM 호출 (1회만 - 토큰 추출 + JSON 파싱)
        raw_response = await llm.ainvoke(messages)
        
        # 토큰 사용량 추출 및 State에 누적
        tokens = extract_token_usage(raw_response)
        if tokens:
            accumulate_tokens(state, tokens, token_type="eval")
            logger.debug(f"[4.0 Intent Analysis] 토큰 사용량 - prompt: {tokens.get('prompt_tokens')}, completion: {tokens.get('completion_tokens')}, total: {tokens.get('total_tokens')}")
        else:
            logger.warning(f"[4.0 Intent Analysis] 토큰 사용량 추출 실패 - raw_response 타입: {type(raw_response)}")
        
        # 원본 응답을 구조화된 출력으로 파싱
        try:
            parsed_response = await parse_structured_output_async(
                raw_response=raw_response,
                model_class=IntentClassification,
                fallback_llm=structured_llm,
                formatted_messages=messages
            )
        except Exception as parse_error:
            logger.error(f"[4.0 Intent Analysis] 구조화된 출력 파싱 실패: {str(parse_error)}", exc_info=True)
            # 파싱 실패 시 fallback으로 구조화된 출력 Chain 사용
            logger.info("[4.0 Intent Analysis] Fallback: 구조화된 출력 Chain 사용")
            parsed_response = await structured_llm.ainvoke(messages)
        
        # 리스트 형태의 값 추출
        intent_values = [intent.value for intent in parsed_response.intent_types]
        
        # 첫 턴 검증: 첫 턴이 FOLLOW_UP이면 재분류
        if is_first_turn and CodeIntentType.FOLLOW_UP.value in intent_values:
            logger.warning(f"[4.0 Intent Analysis] 첫 턴에서 FOLLOW_UP 감지 - 재분류 필요. 원본 의도: {intent_values}")
            # FOLLOW_UP 제거하고 다른 의도 선택
            intent_values = [intent for intent in intent_values if intent != CodeIntentType.FOLLOW_UP.value]
            if not intent_values:
                # 대체 의도 선택 (XML 태그 기반)
                if has_role_content:
                    intent_values = [CodeIntentType.SYSTEM_PROMPT.value]
                    logger.info(f"[4.0 Intent Analysis] 첫 턴 FOLLOW_UP → XML 태그 기반으로 SYSTEM_PROMPT로 재분류")
                else:
                    intent_values = [CodeIntentType.RULE_SETTING.value]
                    logger.info(f"[4.0 Intent Analysis] 첫 턴 FOLLOW_UP → RULE_SETTING으로 재분류")
        
        # 우선순위 기반 단일 선택 (복수 선택 시)
        if len(intent_values) > 1:
            # 의도 우선순위 정의 (첫 턴에서는 RULE_SETTING/SYSTEM_PROMPT 우선순위 상향)
            if is_first_turn:
                # 첫 턴 우선순위: RULE_SETTING/SYSTEM_PROMPT 우선
                intent_priority = {
                    CodeIntentType.SYSTEM_PROMPT.value: 1,  # 첫 턴 최우선
                    CodeIntentType.RULE_SETTING.value: 2,    # 첫 턴 최우선
                    CodeIntentType.GENERATION.value: 3,
                    CodeIntentType.OPTIMIZATION.value: 4,
                    CodeIntentType.DEBUGGING.value: 5,
                    CodeIntentType.TEST_CASE.value: 6,
                    CodeIntentType.HINT_OR_QUERY.value: 7,
                    CodeIntentType.FOLLOW_UP.value: 999,  # 첫 턴에서는 선택 불가
                }
            else:
                # 일반 우선순위
                intent_priority = {
                    CodeIntentType.GENERATION.value: 1,  # 최우선
                    CodeIntentType.OPTIMIZATION.value: 2,
                    CodeIntentType.DEBUGGING.value: 3,
                    CodeIntentType.TEST_CASE.value: 4,
                    CodeIntentType.RULE_SETTING.value: 5,
                    CodeIntentType.SYSTEM_PROMPT.value: 6,
                    CodeIntentType.HINT_OR_QUERY.value: 7,
                    CodeIntentType.FOLLOW_UP.value: 8,  # 최하위
                }
            
            # XML 태그가 있으면 SYSTEM_PROMPT/RULE_SETTING 우선순위 추가 상향
            if has_role_content:
                if CodeIntentType.SYSTEM_PROMPT.value in intent_values:
                    intent_priority[CodeIntentType.SYSTEM_PROMPT.value] = 0  # 최최우선
                if CodeIntentType.RULE_SETTING.value in intent_values:
                    intent_priority[CodeIntentType.RULE_SETTING.value] = 0  # 최최우선
            
            # 우선순위가 가장 높은 의도 선택
            selected_intent = min(intent_values, key=lambda x: intent_priority.get(x, 999))
            intent_values = [selected_intent]
            
            logger.info(f"[4.0 Intent Analysis] 복수 의도 감지 - 원본: {parsed_response.intent_types}, 우선순위 기반 단일 선택: {selected_intent}")
        
        # 단일 의도 선택 후 추가 검증
        if len(intent_values) == 1:
            selected_intent = intent_values[0]
            
            # 첫 턴 + FOLLOW_UP 최종 검증
            if is_first_turn and selected_intent == CodeIntentType.FOLLOW_UP.value:
                logger.warning(f"[4.0 Intent Analysis] 첫 턴에서 FOLLOW_UP 최종 검증 실패 - RULE_SETTING으로 강제 변경")
                intent_values = [CodeIntentType.RULE_SETTING.value]
            
            # XML 태그 기반 힌트 적용
            if has_role_content and selected_intent not in [CodeIntentType.SYSTEM_PROMPT.value, CodeIntentType.RULE_SETTING.value]:
                logger.info(f"[4.0 Intent Analysis] XML 태그 감지되었으나 {selected_intent} 선택됨 - 유지 (LLM 판단 존중)")
        
        logger.info(f"[4.0 Intent Analysis] 완료 - session_id: {session_id}, turn: {turn}, 의도: {intent_values}, 신뢰도: {parsed_response.confidence:.2f}")
        
        result = {
            "intent_types": intent_values,
            "intent_confidence": parsed_response.confidence,
        }
        
        # State에 누적된 토큰 정보를 result에 포함 (LangGraph 병합을 위해)
        if "eval_tokens" in state:
            result["eval_tokens"] = state["eval_tokens"]
        
        return result
        
    except Exception as e:
        logger.error(f"[4.0 Intent Analysis] 오류 - session_id: {session_id}, turn: {turn}, error: {str(e)}", exc_info=True)
        return {
            "intent_types": [CodeIntentType.HINT_OR_QUERY.value],
            "intent_confidence": 0.0,
        }

