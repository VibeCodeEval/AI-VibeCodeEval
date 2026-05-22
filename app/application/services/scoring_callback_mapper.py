"""
Judge0 / N9 State → BE ScoringResultRequest DTO 매핑.

docs/ai-callback-scoring.md §3.4 — rubric 직렬화(rubric_json_serializers)와 분리.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set

from app.infrastructure.judge0.utils import (
    parse_judge_memory_kb,
    parse_judge_time_seconds,
)

_JUDGE_STATUS_ACCEPTED = 3
_JUDGE_STATUS_WRONG_ANSWER = 4
_JUDGE_STATUS_TLE = 5
_JUDGE_STATUS_COMPILATION_ERROR = 6
# Judge0 CE: 7 Runtime Error (NS) — BE MLE과 구분
_JUDGE_STATUS_RUNTIME_ERROR_NS = 7

_DEFAULT_RUN_GROUP = "SAMPLE"
_VALID_RUN_GROUPS: Set[str] = {"SAMPLE", "PUBLIC", "PRIVATE"}
_VALID_VERDICTS: Set[str] = {"AC", "WA", "TLE", "MLE", "RE"}


def _utf8_byte_len(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bytes):
        return len(value)
    return len(str(value).encode("utf-8"))


def judge_status_to_verdict(tc: Dict[str, Any]) -> str:
    """Judge0 per-TC dict → BE Verdict enum string."""
    status_id = tc.get("status_id")
    try:
        sid = int(status_id) if status_id is not None else None
    except (TypeError, ValueError):
        sid = None

    passed = bool(tc.get("passed"))

    if sid == _JUDGE_STATUS_ACCEPTED:
        return "AC" if passed else "WA"
    if sid == _JUDGE_STATUS_WRONG_ANSWER:
        return "WA"
    if sid == _JUDGE_STATUS_TLE:
        return "TLE"
    if sid == _JUDGE_STATUS_COMPILATION_ERROR:
        return "RE"
    if sid == _JUDGE_STATUS_RUNTIME_ERROR_NS:
        return "MLE"
    if not passed:
        return "WA"
    return "RE"


def map_test_case_to_be_dto(
    tc: Dict[str, Any],
    *,
    default_group: str = _DEFAULT_RUN_GROUP,
) -> Dict[str, Any]:
    """단일 Judge0 TC 결과 → BE testCases[] 항목."""
    idx = tc.get("test_case_index", 0)
    try:
        case_index = int(idx)
    except (TypeError, ValueError):
        case_index = 0

    time_sec = parse_judge_time_seconds(tc.get("time"))
    time_ms = int(round(time_sec * 1000)) if time_sec is not None else None

    mem_kb = parse_judge_memory_kb(tc.get("memory"))

    return {
        "caseIndex": case_index,
        "group": default_group,
        "verdict": judge_status_to_verdict(tc),
        "timeMs": time_ms,
        "memKb": mem_kb,
        "stdoutBytes": _utf8_byte_len(tc.get("actual")),
        "stderrBytes": _utf8_byte_len(tc.get("stderr")),
    }


def map_test_cases_to_be_dto(
    test_case_results: Optional[List[Dict[str, Any]]],
    *,
    default_group: str = _DEFAULT_RUN_GROUP,
) -> List[Dict[str, Any]]:
    if not test_case_results:
        return []
    out: List[Dict[str, Any]] = []
    for tc in test_case_results:
        if isinstance(tc, dict):
            out.append(map_test_case_to_be_dto(tc, default_group=default_group))
    return out


def build_be_score_payload(
    *,
    prompt_score: float,
    perf_score: float,
    correctness_score: float,
    rubric_dict: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "promptScore": round(float(prompt_score), 2),
        "perfScore": round(float(perf_score), 2),
        "correctnessScore": round(float(correctness_score), 2),
        "rubricJson": json.dumps(rubric_dict, ensure_ascii=False),
    }


def validate_be_scoring_body(body: Dict[str, Any]) -> Optional[str]:
    """
    BE ScoringResultRequest 사전 검증.

    Returns:
        None if valid, else human-readable error (BE 400과 동일 계약).
    """
    if not body or not isinstance(body, dict):
        return "body가 비어 있습니다."

    status = (body.get("status") or "").upper()
    if status not in ("DONE", "FAILED", "QUEUED", "RUNNING"):
        return f"잘못된 status: {body.get('status')}"

    test_cases = body.get("testCases")
    if test_cases is None:
        test_cases = []
    if not isinstance(test_cases, list):
        return "testCases는 배열이어야 합니다."

    if status == "DONE" and len(test_cases) < 1:
        return "status=DONE일 때 testCases는 1건 이상 필요합니다 (BE 400)."

    for idx, tc in enumerate(test_cases):
        if not isinstance(tc, dict):
            return f"testCases[{idx}]는 객체여야 합니다."
        group = tc.get("group")
        if group is not None and str(group) not in _VALID_RUN_GROUPS:
            return f"testCases[{idx}].group={group!r} — SAMPLE|PUBLIC|PRIVATE만 허용"
        verdict = tc.get("verdict")
        if verdict is not None and str(verdict) not in _VALID_VERDICTS:
            return f"testCases[{idx}].verdict={verdict!r} — AC|WA|TLE|MLE|RE만 허용"

    return None


def build_be_scoring_from_eval_result(
    eval_result: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    LangGraph / EvalService 응답 dict에서 BE result body 재구성 (fallback).

    `be_scoring_callback`가 state에서 누락된 경우 session 백그라운드에서 사용.
    """
    submission_id = eval_result.get("submission_id")
    final_scores = eval_result.get("final_scores")
    if not submission_id or not final_scores or not isinstance(final_scores, dict):
        return None

    rubric_dict = dict(final_scores)
    rubric_dict.setdefault(
        "correctness_details", final_scores.get("correctness_details")
    )
    rubric_dict.setdefault(
        "performance_details", final_scores.get("performance_details")
    )

    return build_be_scoring_result_body(
        status="DONE",
        test_case_results=eval_result.get("test_case_results"),
        prompt_score=final_scores.get("prompt_score"),
        perf_score=final_scores.get("performance_score"),
        correctness_score=final_scores.get("correctness_score"),
        rubric_dict=rubric_dict,
    )


def build_be_scoring_result_body(
    *,
    status: str,
    test_case_results: Optional[List[Dict[str, Any]]] = None,
    prompt_score: Optional[float] = None,
    perf_score: Optional[float] = None,
    correctness_score: Optional[float] = None,
    rubric_dict: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    POST .../submissions/{submissionId}/result body (ScoringResultRequest).

    FAILED 시 testCases=[], score=null.
    """
    status_upper = (status or "").upper()
    test_cases = map_test_cases_to_be_dto(test_case_results)

    if status_upper == "FAILED":
        body = {
            "status": "FAILED",
            "testCases": [],
            "score": None,
        }
        err = validate_be_scoring_body(body)
        if err:
            raise ValueError(err)
        return body

    if rubric_dict is None:
        rubric_dict = {}

    body = {
        "status": status_upper,
        "testCases": test_cases,
        "score": build_be_score_payload(
            prompt_score=float(prompt_score or 0),
            perf_score=float(perf_score or 0),
            correctness_score=float(correctness_score or 0),
            rubric_dict=rubric_dict,
        ),
    }
    err = validate_be_scoring_body(body)
    if err:
        raise ValueError(err)
    return body
