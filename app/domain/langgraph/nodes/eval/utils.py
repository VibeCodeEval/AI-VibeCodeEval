def get_llm():
    """LLM 인스턴스 생성 (Vertex AI 또는 AI Studio — llm_factory 단일 경로)"""
    from app.core.config import settings
    from app.domain.langgraph.utils.llm_factory import create_gemini_llm

    return create_gemini_llm(temperature=settings.LLM_TEMPERATURE_EVAL)
