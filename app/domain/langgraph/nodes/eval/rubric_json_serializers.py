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
