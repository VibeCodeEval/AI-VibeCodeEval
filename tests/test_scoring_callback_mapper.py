"""BE ScoringResultRequest 매핑 단위 테스트."""

from app.application.services.scoring_callback_mapper import (
    build_be_scoring_result_body,
    judge_status_to_verdict,
    map_test_case_to_be_dto,
)


def test_judge_status_accepted_passed_ac():
    assert judge_status_to_verdict({"status_id": 3, "passed": True}) == "AC"


def test_judge_status_accepted_failed_stdout_wa():
    assert judge_status_to_verdict({"status_id": 3, "passed": False}) == "WA"


def test_judge_status_tle():
    assert judge_status_to_verdict({"status_id": 5, "passed": False}) == "TLE"


def test_map_test_case_time_ms_and_bytes():
    dto = map_test_case_to_be_dto(
        {
            "test_case_index": 1,
            "time": "0.15",
            "memory": "1024",
            "actual": "hello",
            "stderr": "err",
            "status_id": 3,
            "passed": True,
        }
    )
    assert dto["caseIndex"] == 1
    assert dto["group"] == "SAMPLE"
    assert dto["verdict"] == "AC"
    assert dto["timeMs"] == 150
    assert dto["memKb"] == 1024
    assert dto["stdoutBytes"] == 5
    assert dto["stderrBytes"] == 3


def test_build_be_scoring_result_failed_empty():
    body = build_be_scoring_result_body(status="FAILED")
    assert body["status"] == "FAILED"
    assert body["testCases"] == []
    assert body["score"] is None


def test_build_be_scoring_result_done_rubric_json_string():
    body = build_be_scoring_result_body(
        status="DONE",
        test_case_results=[
            {
                "test_case_index": 0,
                "time": "0.01",
                "memory": "512",
                "actual": "35",
                "status_id": 3,
                "passed": True,
            }
        ],
        prompt_score=30,
        perf_score=20,
        correctness_score=40,
        rubric_dict={"grade": "A"},
    )
    assert body["status"] == "DONE"
    assert len(body["testCases"]) == 1
    assert isinstance(body["score"]["rubricJson"], str)
    assert '"grade"' in body["score"]["rubricJson"]
