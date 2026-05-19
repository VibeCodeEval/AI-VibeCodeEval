import logging
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from app.domain.langgraph.nodes.eval_turn.utils import get_llm_summary
from app.domain.langgraph.states import EvalTurnState
from app.domain.langgraph.utils.token_tracking import (accumulate_tokens,
                                                       extract_token_usage)

logger = logging.getLogger(__name__)


def _build_latest_turn(human_message: str, ai_message: str) -> str:
    """최근 턴(human/ai)을 요약 프롬프트 입력 형태로 구성."""
    return (
        f"human: {human_message or '(없음)'}\n"
        f"ai: {ai_message or '(없음)'}"
    )


async def summarize_answer(state: EvalTurnState) -> Dict[str, Any]:
    """
    4.X: Summarize Answer (Runnable & Chain 구조)
    LLM 답변 요약/추론
    """
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.X 답변 요약] 진입 - session_id: {session_id}, turn: {turn}")

    from app.domain.langgraph.prompts import load_prompt, render_prompt

    human_message = state.get("human_message", "")
    ai_message = state.get("ai_message", "")

    if not ai_message:
        logger.warning(
            f"[4.X 답변 요약] AI 메시지 없음 - session_id: {session_id}, turn: {turn}"
        )
        return {"answer_summary": None}

    try:
        prev_summary = (state.get("previous_turns_summary") or "").strip()
        if not prev_summary:
            prev_summary = "(이전 대화 없음)"

        latest_turn = _build_latest_turn(human_message, ai_message)
        summary_yaml = load_prompt("summary")
        system_prompt = summary_yaml.get(
            "system",
            "당신은 대화 요약 전문가입니다. 핵심만 남긴 갱신 요약 1개를 만듭니다.",
        )
        user_prompt = render_prompt(
            "summary",
            prev_summary=prev_summary,
            latest_turn=latest_turn,
        )

        llm = get_llm_summary()
        llm_response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        summary = (
            llm_response.content
            if hasattr(llm_response, "content")
            else str(llm_response)
        )

        # 토큰 사용량 추출 및 State에 누적
        if llm_response:
            tokens = extract_token_usage(llm_response)
            if tokens:
                accumulate_tokens(state, tokens, token_type="eval")
                logger.debug(
                    f"[4.X 답변 요약] 토큰 사용량 - prompt: {tokens.get('prompt_tokens')}, completion: {tokens.get('completion_tokens')}, total: {tokens.get('total_tokens')}"
                )

        logger.info(
            f"[4.X 답변 요약] 완료 - session_id: {session_id}, turn: {turn}, 요약 길이: {len(summary)}"
        )

        result = {"answer_summary": summary}

        # State에 누적된 토큰 정보를 result에 포함 (LangGraph 병합을 위해)
        if "eval_tokens" in state:
            result["eval_tokens"] = state["eval_tokens"]

        return result

    except Exception as e:
        logger.error(
            f"[4.X 답변 요약] 오류 - session_id: {session_id}, turn: {turn}, error: {str(e)}",
            exc_info=True,
        )
        return {"answer_summary": None}
