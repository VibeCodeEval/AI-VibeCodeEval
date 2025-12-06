import logging
from app.domain.langgraph.utils.llm_factory import get_llm as get_llm_from_factory

logger = logging.getLogger(__name__)

def get_llm():
    """LLM 인스턴스 생성 (Factory 사용)"""
    return get_llm_from_factory("turn_evaluator")

