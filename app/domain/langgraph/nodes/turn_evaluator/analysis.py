import logging
from typing import Dict, Any

from app.domain.langgraph.states import EvalTurnState, IntentClassification
from app.infrastructure.persistence.models.enums import CodeIntentType
from app.domain.langgraph.nodes.turn_evaluator.utils import get_llm
from app.domain.langgraph.utils.token_tracking import extract_token_usage, accumulate_tokens
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

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
    
    system_prompt = """당신은 코딩 대화의 의도를 분류하는 전문가입니다.
사용자와 AI의 대화를 분석하여 다음 8가지 중 가장 적절한 의도를 **단일 선택**하세요.

**의도 우선순위 규칙** (우선순위가 높은 것을 선택):
1. GENERATION (최우선): 코드 생성이 목적이면 최우선
2. OPTIMIZATION: 기존 코드 개선
3. DEBUGGING: 버그 수정
4. TEST_CASE: 테스트 작성
5. RULE_SETTING: 제약조건 명시
6. SYSTEM_PROMPT: 역할 정의
7. HINT_OR_QUERY: 질문/힌트
8. FOLLOW_UP: 후속 질문

**의도 정의**:
1. SYSTEM_PROMPT: 시스템 프롬프트 설정, AI 역할/페르소나 정의, 답변 스타일 지정
2. RULE_SETTING: 규칙 설정, 요구사항 정의, 제약조건 설명
3. GENERATION: 새로운 코드 생성 요청
4. OPTIMIZATION: 기존 코드 최적화, 성능 개선
5. DEBUGGING: 버그 수정, 오류 해결
6. TEST_CASE: 테스트 케이스 작성, 테스트 관련
7. HINT_OR_QUERY: 힌트 요청, 질문, 설명 요청
8. FOLLOW_UP: 후속 질문, 추가 요청, 확인

**중요**: 여러 의도가 관련되어 있어도, 우선순위가 가장 높은 **단일 의도만** 선택하세요.
예: "코드를 작성하고 최적화해주세요" → GENERATION 선택 (코드 생성이 최우선 목적)"""

    prompt = f"사용자: {human_message}\n\nAI 응답: {ai_message}"
    
    try:
        # 원본 LLM 호출 (메타데이터 보존을 위해)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        
        # 원본 LLM 응답 받기 (토큰 사용량 추출용)
        raw_response = await llm.ainvoke(messages)
        
        # 토큰 사용량 추출 및 State에 누적 (원본 응답에서)
        tokens = extract_token_usage(raw_response)
        if tokens:
            accumulate_tokens(state, tokens, token_type="eval")
            logger.debug(f"[4.0 Intent Analysis] 토큰 사용량 - prompt: {tokens.get('prompt_tokens')}, completion: {tokens.get('completion_tokens')}, total: {tokens.get('total_tokens')}")
        else:
            logger.warning(f"[4.0 Intent Analysis] 토큰 사용량 추출 실패 - raw_response 타입: {type(raw_response)}")
        
        # 구조화된 출력으로 파싱 (원본 응답 내용 사용)
        parsed_response = await structured_llm.ainvoke(messages)
        
        # 리스트 형태의 값 추출
        intent_values = [intent.value for intent in parsed_response.intent_types]
        
        # 우선순위 기반 단일 선택 (복수 선택 시)
        if len(intent_values) > 1:
            # 의도 우선순위 정의
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
            
            # 우선순위가 가장 높은 의도 선택
            selected_intent = min(intent_values, key=lambda x: intent_priority.get(x, 999))
            intent_values = [selected_intent]
            
            logger.info(f"[4.0 Intent Analysis] 복수 의도 감지 - 원본: {parsed_response.intent_types}, 우선순위 기반 단일 선택: {selected_intent}")
        
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

