"""N9 performance_score 보정이 total_score 계산보다 먼저 적용되는지."""

import inspect

from app.domain.langgraph.nodes.eval import n9_final_scores


def test_submission_avg_cc_prefers_radon_cc():
    from app.domain.langgraph.nodes.eval.n9_final_scores import _submission_avg_cc

    assert _submission_avg_cc({"radon_cc": {"avg_cc": 7.5}}) == 7.5
    assert _submission_avg_cc(
        {"v2_metrics": {"radon_cc": {"avg_cc": 9.0}}}
    ) == 9.0


def test_n9_total_score_computed_after_perf_cc_adjustment():
    src = inspect.getsource(n9_final_scores.aggregate_final_scores)
    perf_adj = src.index("perf_score = round(perf_score * (0.8 + 0.2 * cc_bonus)")
    total_calc = src.index("total_score = (")
    assert perf_adj < total_calc


def test_grade_from_total_score_matches_p4_case():
    from app.domain.langgraph.nodes.eval.n9_final_scores import (
        _grade_from_total_score,
    )

    assert _grade_from_total_score(82.38) == "B"
    assert _grade_from_total_score(90.0) == "A"
    assert _grade_from_total_score(79.9) == "C"
    assert _grade_from_total_score(59.0) == "F"
