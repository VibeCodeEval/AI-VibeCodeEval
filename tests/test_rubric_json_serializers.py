"""rubric_json correctness/performance details 직렬화."""

from app.domain.langgraph.nodes.eval.rubric_json_serializers import (
    build_correctness_details,
    build_performance_details,
    serialize_test_case_for_correctness,
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
