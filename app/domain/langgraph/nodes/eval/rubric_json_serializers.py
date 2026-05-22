"""
N9 rubric_json용 correctness_details / performance_details 조립.

N5 test_case_results(Judge0 per-TC)를 DB 저장 스키마로 직렬화한다.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.domain.langgraph.nodes.eval.n5_integrated_evaluator import (
    _parse_judge_memory_mb,
    _parse_judge_time_seconds,
    _per_tc_raw_performance_score,
)


def _tc_index(tc: Dict[str, Any]) -> int:
    raw = tc.get("test_case_index", 0)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def serialize_test_case_for_correctness(tc: Dict[str, Any]) -> Dict[str, Any]:
    """Judge0 TC 결과 → rubric_json.correctness_details.test_cases[] 항목."""
    time_sec = _parse_judge_time_seconds(tc.get("time"))
    memory_mb = _parse_judge_memory_mb(tc.get("memory"))
    return {
        "index": _tc_index(tc),
        "input": tc.get("input", ""),
        "expected": tc.get("expected", ""),
        "actual": tc.get("actual", ""),
        "passed": bool(tc.get("passed")),
        "status_id": tc.get("status_id"),
        "status_description": tc.get("status_description"),
        "time_sec": time_sec,
        "memory_mb": memory_mb,
        "stderr": tc.get("stderr"),
        "compile_output": tc.get("compile_output"),
    }


def serialize_test_case_for_performance(
    tc: Dict[str, Any],
    *,
    time_limit_sec: float,
    memory_limit_mb: float,
) -> Dict[str, Any]:
    """passed TC의 성능 raw 점수 포함."""
    time_sec = _parse_judge_time_seconds(tc.get("time"))
    memory_mb = _parse_judge_memory_mb(tc.get("memory"))
    passed = bool(tc.get("passed"))
    raw_performance_score: Optional[float] = None
    if passed and time_sec is not None and memory_mb is not None:
        raw_performance_score = round(
            _per_tc_raw_performance_score(
                time_sec, memory_mb, time_limit_sec, memory_limit_mb
            ),
            2,
        )
    return {
        "index": _tc_index(tc),
        "passed": passed,
        "time_sec": time_sec,
        "memory_mb": memory_mb,
        "raw_performance_score": raw_performance_score,
    }


def build_correctness_details(
    *,
    test_cases_passed: Optional[int],
    test_cases_total: Optional[int],
    correctness_reasoning: Optional[str],
    test_case_results: Optional[List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    """
    N5 실패·타임아웃 시 test_cases=[] + reasoning 유지.
    평가 미실행(test_cases_total·results·reasoning 모두 없음)이면 None.
    """
    has_results = bool(test_case_results)
    if (
        test_cases_total is None
        and not has_results
        and not correctness_reasoning
    ):
        return None

    total = int(test_cases_total or 0)
    passed = int(test_cases_passed or 0)
    pass_rate = round((passed / total * 100) if total > 0 else 0.0, 1)

    details: Dict[str, Any] = {
        "test_cases_passed": passed,
        "test_cases_total": total,
        "pass_rate": pass_rate,
        "correctness_reasoning": correctness_reasoning,
        "test_cases": [
            serialize_test_case_for_correctness(tc)
            for tc in (test_case_results or [])
            if isinstance(tc, dict)
        ],
    }
    return details


def build_performance_details(
    *,
    execution_time: Optional[float],
    memory_used_mb: Optional[float],
    time_limit_sec: Optional[float],
    memory_limit_mb: Optional[float],
    skip_performance: bool,
    skip_reason: Optional[str],
    test_case_results: Optional[List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    """기존 대표 메트릭 + TC별 performance 스냅샷."""
    t_limit = float(time_limit_sec) if time_limit_sec else 2.0
    m_limit = float(memory_limit_mb) if memory_limit_mb else 128.0

    if skip_performance and execution_time is None and not test_case_results:
        return None

    details: Dict[str, Any] = {
        "execution_time": execution_time,
        "memory_used_mb": memory_used_mb,
        "time_limit_sec": time_limit_sec,
        "memory_limit_mb": memory_limit_mb,
        "skip_performance": skip_performance,
        "skip_reason": skip_reason,
        "test_cases": [
            serialize_test_case_for_performance(
                tc, time_limit_sec=t_limit, memory_limit_mb=m_limit
            )
            for tc in (test_case_results or [])
            if isinstance(tc, dict)
        ],
    }
    return details


def build_tc_summary(
    *,
    test_cases_passed: Optional[int],
    test_cases_total: Optional[int],
    test_case_results: Optional[List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    """
    N5 Judge0 TC 집계 — rubric_json.tc_summary.

    - average_pass_rate: 통과 TC / 전체 TC (%)
    - average_time_sec / average_memory_mb: **통과한 TC만** 평균 (없으면 null)
    """
    has_results = bool(test_case_results)
    if test_cases_total is None and not has_results:
        return None

    tcs = [tc for tc in (test_case_results or []) if isinstance(tc, dict)]
    passed_tcs = [tc for tc in tcs if tc.get("passed")]

    if test_cases_total is not None:
        total = int(test_cases_total)
        passed = int(test_cases_passed or 0)
    else:
        total = len(tcs)
        passed = len(passed_tcs)

    if total <= 0 and not has_results:
        return None

    pass_rate = round((passed / total * 100) if total > 0 else 0.0, 2)

    times: List[float] = []
    memories: List[float] = []
    for tc in passed_tcs:
        time_sec = _parse_judge_time_seconds(tc.get("time"))
        memory_mb = _parse_judge_memory_mb(tc.get("memory"))
        if time_sec is not None:
            times.append(time_sec)
        if memory_mb is not None:
            memories.append(memory_mb)

    return {
        "average_pass_rate": pass_rate,
        "average_time_sec": round(sum(times) / len(times), 4) if times else None,
        "average_memory_mb": round(sum(memories) / len(memories), 4)
        if memories
        else None,
        "test_cases_passed": passed,
        "test_cases_total": total,
    }


def build_reference_cc_summary(
    code_quality_metrics: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    N6 reference_code 대비 제출 코드 Radon CC 상승률 — rubric_json.reference_cc_summary.

    ΔCC(%) = (submission_avg_cc - reference_avg_cc) / max(reference_avg_cc, 0.01) × 100
    (compute_delta_cc / N6 delta_cc_vs_reference 와 동일)
    """
    if not code_quality_metrics or not isinstance(code_quality_metrics, dict):
        return None
    if not code_quality_metrics.get("has_reference_code"):
        return None

    ref_radon = code_quality_metrics.get("reference_radon_cc") or {}
    sub_radon = code_quality_metrics.get("radon_cc") or {}
    delta_ref = code_quality_metrics.get("delta_cc_vs_reference") or {}

    if not isinstance(ref_radon, dict):
        ref_radon = {}
    if not isinstance(sub_radon, dict):
        sub_radon = {}
    if not isinstance(delta_ref, dict):
        delta_ref = {}

    ref_avg = ref_radon.get("avg_cc")
    sub_avg = sub_radon.get("avg_cc")
    if ref_avg is None and sub_avg is None and not delta_ref:
        return None

    delta_pct = delta_ref.get("delta_cc_pct")
    if delta_pct is None and ref_avg is not None and sub_avg is not None:
        base = max(float(ref_avg), 0.01)
        delta_pct = round((float(sub_avg) - float(ref_avg)) / base * 100.0, 2)

    return {
        "has_reference_code": True,
        "reference_avg_cc": ref_radon.get("avg_cc"),
        "reference_max_cc": ref_radon.get("max_cc"),
        "submission_avg_cc": sub_radon.get("avg_cc"),
        "submission_max_cc": sub_radon.get("max_cc"),
        "delta_cc_pct": delta_pct,
        "delta_cc_vs_reference": delta_ref if delta_ref else None,
    }
