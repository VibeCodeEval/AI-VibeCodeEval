"""rubric_json correctness/performance details 직렬화."""

from app.domain.langgraph.nodes.eval.rubric_json_serializers import (
    build_correctness_details,
    build_performance_details,
    build_reference_cc_summary,
    build_tc_summary,
    serialize_test_case_for_correctness,
)
from app.domain.langgraph.nodes.eval.turn_evaluation_details import (
    build_turn_evaluation_details,
)


def test_serialize_test_case_for_correctness_maps_judge0_fields():
    tc = {
        "test_case_index": 2,
        "input": "1\n2",
        "expected": "3",
        "actual": "3",
        "passed": True,
        "status_id": 3,
        "status_description": "Accepted",
        "time": "0.05",
        "memory": "2048",
        "stderr": None,
        "compile_output": None,
    }
    out = serialize_test_case_for_correctness(tc)
    assert out["index"] == 2
    assert out["passed"] is True
    assert out["time_sec"] == 0.05
    assert abs(out["memory_mb"] - 2.0) < 1e-6


def test_build_correctness_details_failure_empty_test_cases():
    details = build_correctness_details(
        test_cases_passed=0,
        test_cases_total=10,
        correctness_reasoning="타임아웃",
        test_case_results=[],
    )
    assert details is not None
    assert details["test_cases"] == []
    assert details["test_cases_total"] == 10
    assert details["correctness_reasoning"] == "타임아웃"


def test_build_correctness_details_none_when_no_eval():
    assert (
        build_correctness_details(
            test_cases_passed=None,
            test_cases_total=None,
            correctness_reasoning=None,
            test_case_results=None,
        )
        is None
    )


def test_build_performance_details_includes_per_tc():
    details = build_performance_details(
        execution_time=0.1,
        memory_used_mb=4.0,
        time_limit_sec=2.0,
        memory_limit_mb=128.0,
        skip_performance=False,
        skip_reason=None,
        test_case_results=[
            {
                "test_case_index": 0,
                "passed": True,
                "time": "0.05",
                "memory": "1024",
            },
            {
                "test_case_index": 1,
                "passed": False,
                "time": "0",
                "memory": "0",
            },
        ],
    )
    assert details is not None
    assert len(details["test_cases"]) == 2
    assert details["test_cases"][0]["raw_performance_score"] is not None
    assert details["test_cases"][1]["raw_performance_score"] is None


def test_build_tc_summary_passed_only_averages():
    summary = build_tc_summary(
        test_cases_passed=1,
        test_cases_total=2,
        test_case_results=[
            {
                "passed": True,
                "time": "0.10",
                "memory": "2048",
            },
            {
                "passed": False,
                "time": "9.99",
                "memory": "999999",
            },
        ],
    )
    assert summary is not None
    assert summary["average_pass_rate"] == 50.0
    assert summary["average_time_sec"] == 0.1
    assert abs(summary["average_memory_mb"] - 2.0) < 1e-6


def test_build_tc_summary_none_when_no_eval():
    assert (
        build_tc_summary(
            test_cases_passed=None,
            test_cases_total=None,
            test_case_results=None,
        )
        is None
    )


def test_build_reference_cc_summary_from_n6_metrics():
    summary = build_reference_cc_summary(
        {
            "has_reference_code": True,
            "reference_radon_cc": {"avg_cc": 5.0, "max_cc": 6},
            "radon_cc": {"avg_cc": 7.0, "max_cc": 8},
            "delta_cc_vs_reference": {
                "delta_cc_pct": 40.0,
                "v1_avg_cc": 5.0,
                "v2_avg_cc": 7.0,
                "v1_max_cc": 6,
                "v2_max_cc": 8,
            },
        }
    )
    assert summary is not None
    assert summary["delta_cc_pct"] == 40.0
    assert summary["reference_avg_cc"] == 5.0
    assert summary["submission_avg_cc"] == 7.0


def test_build_reference_cc_summary_none_without_reference():
    assert build_reference_cc_summary({"has_reference_code": False}) is None
    assert build_reference_cc_summary(None) is None


def test_build_turn_evaluation_details_matches_storage_shape():
    turn_log = {
        "prompt_evaluation_details": {
            "score": 88.0,
            "intent": "EXPLORATION",
            "unified_intent": "EXPLORATION",
            "rubric_breakdown": {"R1": 90},
            "scoring_cot": {"R1": "ok"},
        },
        "turn_score": 88.0,
        "user_prompt_summary": "hello",
        "llm_answer_summary": "world",
    }
    details = build_turn_evaluation_details(turn_log)
    assert details["score"] == 88.0
    assert details["turn_score"] == 88.0
    assert details["user_prompt_summary"] == "hello"
    assert details["rubric_breakdown"] == {"R1": 90}
