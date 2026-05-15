from typing import Optional

from app.core.config import settings


def get_llm_for_model(model: str, temperature: float = 0.1):
    """
    N4 턴 평가·N8 토론 등과 동일한 인증 경로.
    - USE_VERTEX_AI=true: Vertex (프로젝트 + 선택적 SA JSON/경로 또는 ADC)
    - false: AI Studio (GEMINI_API_KEY)
    """
    from app.domain.langgraph.utils.llm_factory import create_gemini_llm

    return create_gemini_llm(model=model, temperature=temperature)


def get_llm(model: Optional[str] = None, temperature: Optional[float] = None):
    """기본 모델·온도로 LLM 생성 (N4 eval_turn 등)."""
    return get_llm_for_model(
        model or settings.DEFAULT_LLM_MODEL,
        0.1 if temperature is None else temperature,
    )
