"""
N6: 정적 코드 분석 노드 (Radon CC & AST Pattern 검사)

[역할]
- Radon 순환 복잡도(Cyclomatic Complexity) 분석
- v1/v2 코드 간 CC Delta 계산
- AST 패턴 검사 (spec_id 기반 적용 여부 결정)
- junior_grade 플래그 산출

[주의]
이 파일은 구 holistic_flow LLM 평가 노드를 대체한 정적 분석 전용 노드입니다.
이전에 존재하던 eval_holistic_flow, create_holistic_system_prompt 함수는 제거됐습니다.
LLM 기반 holistic 평가는 N8 다중 에이전트 토론 (subgraph_debate.py)에서 수행합니다.
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
    problem_context = state.get("problem_context") or {}
    # checker_json.reference_code → get_problem_info에서 solution_code로 병합됨
    reference_code = (
        (problem_context.get("solution_code") or problem_context.get("reference_code") or "")
        .strip()
    )

    logger.info(f"[N6. Eval Static Analysis] 진입 - session_id: {session_id}")

    code_quality_metrics = {}
    # N5 -> N6 -> N7 전달 보장을 위해 N5 산출값을 명시적으로 패스스루한다.
    n5_passthrough = {
        "code_correctness_score": state.get("code_correctness_score"),
        "code_performance_score": state.get("code_performance_score"),
        "test_cases_passed": state.get("test_cases_passed"),
        "test_cases_total": state.get("test_cases_total"),
        "execution_time": state.get("execution_time"),
        "memory_used_mb": state.get("memory_used_mb"),
        "time_limit_sec": state.get("time_limit_sec"),
        "memory_limit_mb": state.get("memory_limit_mb"),
        "skip_performance": state.get("skip_performance"),
        "skip_reason": state.get("skip_reason"),
        "correctness_reasoning": state.get("correctness_reasoning"),
    }

    if not code_content:
        logger.warning(f"[N6] 코드 없음. 분석 스킵.")
        return {"code_quality_metrics": code_quality_metrics, **n5_passthrough}

    try:
        from app.domain.langgraph.utils.code_quality import (
            check_ast_patterns, compute_delta_cc, compute_radon_cc)
            
        v2_radon = compute_radon_cc(code_content)
        v1_radon = compute_radon_cc(v1_code) if v1_code and v1_code.strip() else {}

        has_v1 = bool(v1_code and v1_code.strip())

        delta_cc = compute_delta_cc(v1_radon, v2_radon) if has_v1 else {}

        has_reference_code = bool(reference_code)
        reference_radon: Dict[str, Any] = {}
        delta_cc_vs_reference: Dict[str, Any] = {}
        if has_reference_code:
            reference_radon = compute_radon_cc(reference_code)
            delta_cc_vs_reference = compute_delta_cc(reference_radon, v2_radon)
            logger.info(
                "[N6] reference_code Radon CC 측정 완료 — avg_cc=%s, 제출 대비 ΔCC%%=%s",
                reference_radon.get("avg_cc"),
                delta_cc_vs_reference.get("delta_cc_pct"),
            )
        else:
            logger.info(
                "[N6] reference_code가 없어 참조 Radon CC 및 제출 대비 비교를 건너뜁니다. "
                "(checker_json.reference_code / problem_context.solution_code 비어 있음)"
            )

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
            "reference_radon_cc": reference_radon,
            "delta_cc_vs_reference": delta_cc_vs_reference,
            "has_reference_code": has_reference_code,
            "ast_pattern_matched": ast_result.get("ast_pattern_matched", False),
            "ast_applicable": ast_result.get("applicable", False),
            "junior_grade": junior_grade,
        }
        
        logger.info(f"[N6. Eval Static Analysis] 완료 - avg_cc: {avg_cc}, max_cc: {max_cc}, junior: {junior_grade}")

    except Exception as e:
        logger.error(f"[N6. Eval Static Analysis] 에러 발생: {e}", exc_info=True)

    return {"code_quality_metrics": code_quality_metrics, **n5_passthrough}
