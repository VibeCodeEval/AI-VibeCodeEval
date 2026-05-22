from typing import Optional

from app.core.config import settings


def get_llm_for_model(model: str, temperature: float):
    """
    N4 턴 평가·N8 토론 등과 동일한 인증 경로.
    - USE_VERTEX_AI=true: Vertex (프로젝트 + 선택적 SA JSON/경로 또는 ADC)
    - false: AI Studio (GEMINI_API_KEY)
    """
    from app.domain.langgraph.utils.llm_factory import create_gemini_llm

    return create_gemini_llm(model=model, temperature=temperature)


def get_llm(model: Optional[str] = None, temperature: Optional[float] = None):
    """N4 루브릭 평가, N7 등 (LLM_TEMPERATURE_EVAL)."""
    resolved = (
        settings.LLM_TEMPERATURE_EVAL if temperature is None else temperature
    )
    return get_llm_for_model(model or settings.DEFAULT_LLM_MODEL, resolved)


def get_llm_intent(model: Optional[str] = None, temperature: Optional[float] = None):
    """N4 intent_analysis — 6대 통합 의도 분류 (LLM_TEMPERATURE_EVAL_INTENT)."""
    resolved = (
        settings.LLM_TEMPERATURE_EVAL_INTENT
        if temperature is None
        else temperature
    )
    return get_llm_for_model(model or settings.DEFAULT_LLM_MODEL, resolved)


def get_llm_summary(
    model: Optional[str] = None, temperature: Optional[float] = None
):
    """N4 summarize_answer — 턴 대화 요약 (LLM_TEMPERATURE_EVAL_SUMMARY)."""
    resolved = (
        settings.LLM_TEMPERATURE_EVAL_SUMMARY
        if temperature is None
        else temperature
    )
    return get_llm_for_model(model or settings.DEFAULT_LLM_MODEL, resolved)
