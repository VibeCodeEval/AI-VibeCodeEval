"""
LangGraph 유틸리티 모듈
"""

from app.domain.langgraph.utils.problem_info import (HARDCODED_PROBLEM_SPEC,
                                                     get_problem_info,
                                                     get_problem_info_sync)

# 하위 호환성을 위한 별칭
PROBLEM_INFO_MAP = HARDCODED_PROBLEM_SPEC

__all__ = [
    "get_problem_info",
    "get_problem_info_sync",
    "HARDCODED_PROBLEM_SPEC",
    "PROBLEM_INFO_MAP",  # 하위 호환성
]
