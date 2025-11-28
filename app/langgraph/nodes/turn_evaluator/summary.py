import logging
from typing import Dict, Any

from app.langgraph.states import EvalTurnState
from app.langgraph.nodes.turn_evaluator.utils import get_llm

logger = logging.getLogger(__name__)

async def summarize_answer(state: EvalTurnState) -> Dict[str, Any]:
    """
    4.X: Summarize Answer
    LLM 답변 요약/추론
    """
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.X 답변 요약] 진입 - session_id: {session_id}, turn: {turn}")
    
    ai_message = state.get("ai_message", "")
    
    if not ai_message:
        logger.warning(f"[4.X 답변 요약] AI 메시지 없음 - session_id: {session_id}, turn: {turn}")
        return {"answer_summary": None}
    
    llm = get_llm()
    
    system_prompt = """AI 응답을 3줄 이내로 핵심만 요약하세요.
- 제공된 코드의 핵심 기능
- 주요 알고리즘/접근 방식
- 핵심 설명 포인트"""

    try:
        result = await llm.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": ai_message}
        ])
        
        logger.info(f"[4.X 답변 요약] 완료 - session_id: {session_id}, turn: {turn}, 요약 길이: {len(result.content)}")
        return {"answer_summary": result.content}
        
    except Exception as e:
        logger.error(f"[4.X 답변 요약] 오류 - session_id: {session_id}, turn: {turn}, error: {str(e)}", exc_info=True)
        return {"answer_summary": None}

