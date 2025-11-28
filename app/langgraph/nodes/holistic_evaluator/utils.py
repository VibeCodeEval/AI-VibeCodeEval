import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings

logger = logging.getLogger(__name__)

def get_llm():
    """LLM 인스턴스 생성"""
    return ChatGoogleGenerativeAI(
        model=settings.DEFAULT_LLM_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.1,
    )

