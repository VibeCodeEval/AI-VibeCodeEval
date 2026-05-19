"""N5 Performance: TC별 passed일 때만 raw, (Σ raw / 전체 TC) × 만점."""

from app.core.config import settings
from app.domain.langgraph.nodes.eval.n5_integrated_evaluator import (
    _per_tc_raw_performance_score,
    _performance_score_from_test_cases,
)


def test_per_tc_raw_performance_fast_low_memory():
    raw = _per_tc_raw_performance_score(0.04, 8.0, time_limit_sec=2.0, memory_limit_mb=128.0)
    assert raw == 100.0


def test_performance_three_tc_two_passed():
    """2/3 passed, each fast → (100+100+0)/3 * scale."""
    tcs = [
        {"test_case_index": 0, "passed": True, "time": "0.01", "memory": "1024"},
        {"test_case_index": 1, "passed": True, "time": "0.02", "memory": "2048"},
        {"test_case_index": 2, "passed": False, "time": "0.01", "memory": "1024"},
    ]
    score, t, m, skip, reason = _performance_score_from_test_cases(
        test_case_results=tcs,
        time_limit_sec=2.0,
        memory_limit_mb=128.0,
        use_smart_gate_suite=False,
        passed_count=2,
        total_count=3,
        fallback_execution_time=None,
        fallback_memory_used_mb=None,
    )
    mx = float(settings.CODE_PERFORMANCE_MAX_POINTS)
    expected = round((100.0 + 100.0) / 3 * (mx / 100.0), 2)
    assert score == expected
    assert skip is False
    assert reason is not None and "부분" in reason
    assert t is not None and m is not None


def test_performance_failed_tc_contributes_zero():
    tcs = [
        {"test_case_index": 0, "passed": False, "time": "0.01", "memory": "1024"},
    ]
    score, _, _, skip, _ = _performance_score_from_test_cases(
        test_case_results=tcs,
        time_limit_sec=2.0,
        memory_limit_mb=128.0,
        use_smart_gate_suite=False,
        passed_count=0,
        total_count=1,
        fallback_execution_time=None,
        fallback_memory_used_mb=None,
    )
    assert score == 0.0
    assert skip is True


def test_performance_smart_gate_uses_fallback():
    score, t, m, skip, _ = _performance_score_from_test_cases(
        test_case_results=None,
        time_limit_sec=2.0,
        memory_limit_mb=128.0,
        use_smart_gate_suite=True,
        passed_count=1,
        total_count=1,
        fallback_execution_time=0.04,
        fallback_memory_used_mb=8.0,
    )
    assert score == float(settings.CODE_PERFORMANCE_MAX_POINTS)
    assert skip is False
    assert t == 0.04
