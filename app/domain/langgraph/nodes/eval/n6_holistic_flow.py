"""
N6: 정적 분석 에이전트 (Radon CC & AST Pattern 검사)
"""

import logging
from typing import Any, Dict

from app.domain.langgraph.states import MainGraphState

logger = logging.getLogger(__name__)


async def eval_static_analysis(state: MainGraphState) -> Dict[str, Any]:
    """
    N6: 정적 코드 분석
    Radon 순환 복잡도(CC), AST 패턴 등을 분석합니다.
    """
    session_id = state.get("session_id", "unknown")
    code_content = state.get("code_content", "")
    v1_code = state.get("v1_code", "")
    spec_id = state.get("spec_id")

    logger.info(f"[N6. Eval Static Analysis] 진입 - session_id: {session_id}")

    code_quality_metrics = {}

    if not code_content:
        logger.warning(f"[N6] 코드 없음. 분석 스킵.")
        return {"code_quality_metrics": code_quality_metrics}

    try:
        from app.domain.langgraph.utils.code_quality import (
            check_ast_patterns, compute_delta_cc, compute_radon_cc)
            
        v2_radon = compute_radon_cc(code_content)
        v1_radon = compute_radon_cc(v1_code) if v1_code and v1_code.strip() else {}
        
        has_v1 = bool(v1_code and v1_code.strip())
        
        delta_cc = compute_delta_cc(v1_radon, v2_radon) if has_v1 else {}
        
        ast_result = check_ast_patterns(code_content, spec_id=spec_id)
        
        avg_cc = v2_radon.get("avg_cc", 0.0)
        max_cc = v2_radon.get("max_cc", 0)
        junior_grade = v2_radon.get("junior_grade", False)
        
        if delta_cc and delta_cc.get("delta_cc_pct", 0) > 30 and avg_cc > 8:
            junior_grade = True
            
        code_quality_metrics = {
            "radon_cc": v2_radon,
            "v1_metrics": {"radon_cc": v1_radon} if has_v1 else {},
            "delta_cc": delta_cc,
            "has_v1": has_v1,
            "ast_pattern_matched": ast_result.get("ast_pattern_matched", False),
            "ast_applicable": ast_result.get("applicable", False),
            "junior_grade": junior_grade,
        }
        
        logger.info(f"[N6. Eval Static Analysis] 완료 - avg_cc: {avg_cc}, max_cc: {max_cc}, junior: {junior_grade}")

    except Exception as e:
        logger.error(f"[N6. Eval Static Analysis] 에러 발생: {e}", exc_info=True)

    return {"code_quality_metrics": code_quality_metrics}
