import logging
from typing import Dict, Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from app.domain.langgraph.states import EvalTurnState
from app.domain.langgraph.nodes.turn_evaluator.utils import get_llm
from app.domain.langgraph.utils.token_tracking import extract_token_usage, accumulate_tokens

logger = logging.getLogger(__name__)


# 시스템 프롬프트 정의
SUMMARY_SYSTEM_PROMPT = """AI 응답을 3줄 이내로 핵심만 요약하세요.
- 제공된 코드의 핵심 기능
- 주요 알고리즘/접근 방식
- 핵심 설명 포인트"""


# 프롬프트 템플릿 생성
summary_prompt = ChatPromptTemplate.from_messages([
    ("system", SUMMARY_SYSTEM_PROMPT),
    ("user", "{ai_message}")
])


def prepare_summary_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """요약 입력 준비"""
    state = inputs.get("state")
    ai_message = state.get("ai_message", "")
    return {"ai_message": ai_message}


def extract_summary_with_response(response: Any) -> Dict[str, Any]:
    """요약 내용과 LLM 응답 객체 추출"""
    ai_content = response.content if hasattr(response, 'content') else str(response)
    return {
        "ai_content": ai_content,
        "_llm_response": response  # 토큰 추출용
    }


# Summary Chain 구성 (토큰 추출을 위해 LLM 응답 객체도 전달)
summary_chain = (
    RunnableLambda(prepare_summary_input)
    | summary_prompt
    | get_llm()
    | RunnableLambda(extract_summary_with_response)
)


async def summarize_answer(state: EvalTurnState) -> Dict[str, Any]:
    """
    4.X: Summarize Answer (Runnable & Chain 구조)
    LLM 답변 요약/추론
    """
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.X 답변 요약] 진입 - session_id: {session_id}, turn: {turn}")
    
    ai_message = state.get("ai_message", "")
    
    if not ai_message:
        logger.warning(f"[4.X 답변 요약] AI 메시지 없음 - session_id: {session_id}, turn: {turn}")
        return {"answer_summary": None}

    try:
        # Summary Chain 실행
        chain_result = await summary_chain.ainvoke({"state": state})
        
        # Chain 결과에서 내용과 LLM 응답 객체 분리
        summary = chain_result.get("ai_content", "") if isinstance(chain_result, dict) else str(chain_result)
        llm_response = chain_result.get("_llm_response") if isinstance(chain_result, dict) else None
        
        # 토큰 사용량 추출 및 State에 누적
        if llm_response:
            tokens = extract_token_usage(llm_response)
            if tokens:
                accumulate_tokens(state, tokens, token_type="eval")
                logger.debug(f"[4.X 답변 요약] 토큰 사용량 - prompt: {tokens.get('prompt_tokens')}, completion: {tokens.get('completion_tokens')}, total: {tokens.get('total_tokens')}")
        
        logger.info(f"[4.X 답변 요약] 완료 - session_id: {session_id}, turn: {turn}, 요약 길이: {len(summary)}")
        
        result = {"answer_summary": summary}
        
        # State에 누적된 토큰 정보를 result에 포함 (LangGraph 병합을 위해)
        if "eval_tokens" in state:
            result["eval_tokens"] = state["eval_tokens"]
        
        return result
        
    except Exception as e:
        logger.error(f"[4.X 답변 요약] 오류 - session_id: {session_id}, turn: {turn}, error: {str(e)}", exc_info=True)
        return {"answer_summary": None}

