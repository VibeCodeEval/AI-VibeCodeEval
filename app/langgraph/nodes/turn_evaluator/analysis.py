import logging
from typing import Dict, Any

from app.langgraph.states import EvalTurnState, IntentClassification
from app.db.models.enums import CodeIntentType
from app.langgraph.nodes.turn_evaluator.utils import get_llm

logger = logging.getLogger(__name__)

async def intent_analysis(state: EvalTurnState) -> Dict[str, Any]:
    """
    4.0: Intent Analysis
    7가지 코드 패턴 분류
    """
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.0 Intent Analysis] 진입 - session_id: {session_id}, turn: {turn}")
    
    human_message = state.get("human_message", "")
    ai_message = state.get("ai_message", "")
    
    llm = get_llm()
    classifier = llm.with_structured_output(IntentClassification)
    
    system_prompt = """당신은 코딩 대화의 의도를 분류하는 전문가입니다.
사용자와 AI의 대화를 분석하여 다음 8가지 중 적절한 의도를 모두 선택하세요 (복수 선택 가능):

1. SYSTEM_PROMPT: 시스템 프롬프트 설정, AI 역할/페르소나 정의, 답변 스타일 지정
2. RULE_SETTING: 규칙 설정, 요구사항 정의, 제약조건 설명
3. GENERATION: 새로운 코드 생성 요청
4. OPTIMIZATION: 기존 코드 최적화, 성능 개선
5. DEBUGGING: 버그 수정, 오류 해결
6. TEST_CASE: 테스트 케이스 작성, 테스트 관련
7. HINT_OR_QUERY: 힌트 요청, 질문, 설명 요청
8. FOLLOW_UP: 후속 질문, 추가 요청, 확인

대화 맥락을 고려하여 관련된 모든 의도를 선택하세요."""

    prompt = f"사용자: {human_message}\n\nAI 응답: {ai_message}"
    
    try:
        result = await classifier.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])
        
        # 리스트 형태의 값 추출
        intent_values = [intent.value for intent in result.intent_types]
        
        logger.info(f"[4.0 Intent Analysis] 완료 - session_id: {session_id}, turn: {turn}, 의도: {intent_values}, 신뢰도: {result.confidence:.2f}")
        
        return {
            "intent_types": intent_values,
            "intent_confidence": result.confidence,
        }
        
    except Exception as e:
        logger.error(f"[4.0 Intent Analysis] 오류 - session_id: {session_id}, turn: {turn}, error: {str(e)}", exc_info=True)
        return {
            "intent_types": [CodeIntentType.HINT_OR_QUERY.value],
            "intent_confidence": 0.0,
        }

