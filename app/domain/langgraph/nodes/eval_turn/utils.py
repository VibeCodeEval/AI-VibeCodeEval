import logging
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai import ChatVertexAI

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_llm_for_model(model: str, temperature: float = 0.1):
    """
    N4 턴 평가 등과 동일한 인증 경로.
    - AI Studio: GEMINI_API_KEY (google_api_key 명시 — ADC 미사용)
    - Vertex: 프로젝트/서비스 계정
    """
    if settings.USE_VERTEX_AI:
        import json

        from google.oauth2 import service_account

        credentials = None
        if settings.GOOGLE_SERVICE_ACCOUNT_JSON:
            service_account_info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info
            )

        return ChatVertexAI(
            model=model,
            project=settings.GOOGLE_PROJECT_ID,
            location=settings.GOOGLE_LOCATION,
            credentials=credentials,
            temperature=temperature,
        )
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=temperature,
    )


def get_llm(model: Optional[str] = None, temperature: Optional[float] = None):
    """기본 모델·온도로 LLM 생성 (N4 eval_turn 등)."""
    return get_llm_for_model(
        model or settings.DEFAULT_LLM_MODEL,
        0.1 if temperature is None else temperature,
    )
