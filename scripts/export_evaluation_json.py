#!/usr/bin/env python
"""
DB에서 참가자·문제(또는 spec) 조합으로 평가를 JSON으로 내보냅니다.

저장 기본값: data/{exam_id}_{participant_id}_평가.json
구조 순서: 단일 턴 평가 → 전체(홀리스틱) 턴 평가 → 코드 점수

사용 예:
  uv run python scripts/export_evaluation_json.py --participant-id 1 --problem-id 5
  uv run python scripts/export_evaluation_json.py --session-id 42
  uv run python scripts/export_evaluation_json.py --participant-id 1 --spec-id 20 -o custom/path.json
  uv run python scripts/export_evaluation_json.py --participant-id 1 --problem-id 5 --stdout

환경 변수: POSTGRES_URL (앱과 동일)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

# 프로젝트 루트
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

logger = logging.getLogger(__name__)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _extract_rubrics_from_details(details: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """prompt_evaluations.details에서 루브릭 배열 후보를 모읍니다."""
    if not details or not isinstance(details, dict):
        return []
    out: List[Dict[str, Any]] = []
    for key in ("rubrics", "detailed_rubrics"):
        r = details.get(key)
        if isinstance(r, list):
            out.extend([x for x in r if isinstance(x, dict)])
    ped = details.get("prompt_evaluation_details")
    if isinstance(ped, dict):
        r2 = ped.get("rubrics")
        if isinstance(r2, list):
            out.extend([x for x in r2 if isinstance(x, dict)])
    df = details.get("detailed_feedback")
    if isinstance(df, list):
        for item in df:
            if isinstance(item, dict):
                rub = item.get("rubrics")
                if isinstance(rub, list):
                    out.extend([x for x in rub if isinstance(x, dict)])
    return out


def _orm_prompt_message(m: Any) -> Dict[str, Any]:
    role = m.role
    role_s = role.value if hasattr(role, "value") else str(role)
    return {
        "id": m.id,
        "session_id": m.session_id,
        "turn": m.turn,
        "role": role_s,
        "content": m.content,
        "token_count": m.token_count,
        "meta": m.meta,
        "created_at": m.created_at,
    }


def _message_row_to_dict(row: Any) -> Dict[str, Any]:
    """raw SQL 행 → 메시지 dict (DB enum과 앱 Enum 불일치 시 사용)."""
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "turn": row["turn"],
        "role": row["role"],
        "content": row["content"],
        "token_count": row["token_count"],
        "meta": row["meta"],
        "created_at": row["created_at"],
    }


def _orm_prompt_evaluation(e: Any) -> Dict[str, Any]:
    et = e.evaluation_type
    et_s = et.value if hasattr(et, "value") else str(et)
    details = e.details if isinstance(e.details, dict) else {}
    return {
        "id": e.id,
        "session_id": e.session_id,
        "turn": e.turn,
        "evaluation_type": et_s,
        "details": details,
        "rubrics_extracted": _extract_rubrics_from_details(details),
        "created_at": e.created_at,
    }


def _orm_score(s: Any) -> Dict[str, Any]:
    return {
        "submission_id": s.submission_id,
        "prompt_score": s.prompt_score,
        "perf_score": s.perf_score,
        "correctness_score": s.correctness_score,
        "total_score": s.total_score,
        "rubric_json": s.rubric_json,
        "created_at": s.created_at,
    }


def _build_ordered_export(
    ps: Any,
    problem_id: Optional[int],
    messages: List[Any],
    evaluations: List[Any],
    sub: Any,
    score_row: Any,
) -> Dict[str, Any]:
    """
    JSON 키 순서: 단일 턴 평가 → 전체 세션(홀리스틱) 평가 → 코드 점수.
    """
    from app.infrastructure.persistence.models.enums import EvaluationTypeEnum

    msg_dicts = [
        m if isinstance(m, dict) else _orm_prompt_message(m) for m in messages
    ]
    eval_dicts = [_orm_prompt_evaluation(e) for e in evaluations]

    turn_evals = [
        e
        for e in eval_dicts
        if e.get("evaluation_type") == EvaluationTypeEnum.TURN_EVAL.value
    ]
    turn_evals.sort(key=lambda x: (x.get("turn") or 0, x.get("id") or 0))

    holistic_evals = [
        e
        for e in eval_dicts
        if e.get("evaluation_type") == EvaluationTypeEnum.HOLISTIC_FLOW.value
    ]

    return {
        "meta": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "session_id": ps.id,
            "exam_id": ps.exam_id,
            "participant_id": ps.participant_id,
            "spec_id": ps.spec_id,
            "problem_id": problem_id,
            "started_at": ps.started_at,
            "ended_at": ps.ended_at,
            "total_tokens": ps.total_tokens,
        },
        "single_turn_evaluation": {
            "description": "턴별(TURN_EVAL) 프롬프트 평가 — 노드 4 턴 서브그래프 결과",
            "prompt_messages": msg_dicts,
            "evaluations": turn_evals,
        },
        "whole_session_evaluation": {
            "description": "세션 전체(HOLISTIC_FLOW) Chaining·전략 평가 — 노드 6a",
            "evaluations": holistic_evals,
        },
        "code_scores": {
            "description": "제출·Judge0 연동 최종 점수 — scores / submission",
            "submission": (
                {
                    "id": sub.id,
                    "exam_id": sub.exam_id,
                    "participant_id": sub.participant_id,
                    "spec_id": sub.spec_id,
                    "status": sub.status.value
                    if hasattr(sub.status, "value")
                    else str(sub.status),
                    "created_at": sub.created_at,
                }
                if sub
                else None
            ),
            "score": _orm_score(score_row) if score_row else None,
        },
    }


async def _lookup_problem_id_for_spec(spec_id: int) -> Optional[int]:
    """별도 트랜잭션으로 problem_id만 조회 (스키마 불일치 시에도 본 쿼리를 오염시키지 않음)."""
    from sqlalchemy import text

    from app.infrastructure.persistence.session import get_db_context

    async with get_db_context() as db:
        for q in (
            "SELECT problem_id FROM problem_specs WHERE id = :sid LIMIT 1",
            "SELECT problem_id FROM problem_specs WHERE problem_spec_id = :sid LIMIT 1",
        ):
            try:
                r = await db.execute(text(q), {"sid": spec_id})
                row = r.mappings().first()
                if row and row.get("problem_id") is not None:
                    return int(row["problem_id"])
            except Exception:
                continue
    return None


async def _export_session_bundle(session_id: int) -> Dict[str, Any]:
    from sqlalchemy import select, text
    from sqlalchemy.orm import selectinload

    from app.infrastructure.persistence.models.sessions import PromptSession
    from app.infrastructure.persistence.models.submissions import (
        Score,
        Submission,
    )
    from app.infrastructure.persistence.session import get_db_context

    async with get_db_context() as db:
        ps = await db.scalar(
            select(PromptSession)
            .options(selectinload(PromptSession.evaluations))
            .where(PromptSession.id == session_id)
        )
        if not ps:
            raise ValueError(f"prompt_sessions.id={session_id} 없음")

        problem_id: Optional[int] = None
        if ps.spec_id:
            problem_id = await _lookup_problem_id_for_spec(ps.spec_id)
            if problem_id is None:
                logger.debug(
                    "problem_id 조회 실패 (spec_id=%s) — meta에는 spec_id만 유지",
                    ps.spec_id,
                )

        # ORM 로드 시 role enum이 DB 값(소문자)과 맞지 않을 수 있어 raw 조회
        msg_result = await db.execute(
            text(
                """
                SELECT id, session_id, turn, role::text AS role, content,
                       token_count, meta, created_at
                FROM prompt_messages
                WHERE session_id = :sid
                ORDER BY turn, id
                """
            ),
            {"sid": session_id},
        )
        messages = [_message_row_to_dict(r) for r in msg_result.mappings().all()]

        evaluations = sorted(
            ps.evaluations or [],
            key=lambda e: (e.turn is None, e.turn or 0, e.id),
        )

        sub = None
        if ps.spec_id is not None:
            sub = await db.scalar(
                select(Submission)
                .where(
                    Submission.participant_id == ps.participant_id,
                    Submission.spec_id == ps.spec_id,
                    Submission.exam_id == ps.exam_id,
                )
                .order_by(Submission.created_at.desc())
                .limit(1)
            )
        score_row = None
        if sub:
            score_row = await db.scalar(
                select(Score).where(Score.submission_id == sub.id)
            )

        return _build_ordered_export(ps, problem_id, messages, evaluations, sub, score_row)


def _default_output_path(exam_id: int, participant_id: int, session_id: int) -> str:
    """data/{exam_id}_{participant_id}_평가.json (단일 세션 기본)"""
    data_dir = os.path.join(project_root, "data")
    filename = f"{exam_id}_{participant_id}_평가.json"
    return os.path.join(data_dir, filename)


def _default_output_path_multi(
    exam_id: int, participant_id: int, session_id: int
) -> str:
    """여러 세션 시 파일명 충돌 방지"""
    data_dir = os.path.join(project_root, "data")
    filename = f"{exam_id}_{participant_id}_평가_session_{session_id}.json"
    return os.path.join(data_dir, filename)


async def _find_session_ids(
    participant_id: int,
    exam_id: Optional[int],
    spec_id: Optional[int],
    problem_id: Optional[int],
) -> List[int]:
    from sqlalchemy import select, text

    from app.infrastructure.persistence.models.sessions import PromptSession
    from app.infrastructure.persistence.session import get_db_context

    async with get_db_context() as db:
        if problem_id is not None:
            for join_on in (
                "ps.spec_id = pspec.id",
                "ps.spec_id = pspec.problem_spec_id",
            ):
                try:
                    q = f"""
                        SELECT ps.id FROM prompt_sessions ps
                        INNER JOIN problem_specs pspec ON {join_on}
                        WHERE ps.participant_id = :pid AND pspec.problem_id = :problem_id
                    """
                    params: Dict[str, Any] = {
                        "pid": participant_id,
                        "problem_id": problem_id,
                    }
                    if exam_id is not None:
                        q += " AND ps.exam_id = :eid"
                        params["eid"] = exam_id
                    if spec_id is not None:
                        q += " AND ps.spec_id = :sid"
                        params["sid"] = spec_id
                    r = await db.execute(text(q), params)
                    return list(r.scalars().all())
                except Exception:
                    continue
            return []

        stmt = select(PromptSession.id).where(
            PromptSession.participant_id == participant_id
        )
        if exam_id is not None:
            stmt = stmt.where(PromptSession.exam_id == exam_id)
        if spec_id is not None:
            stmt = stmt.where(PromptSession.spec_id == spec_id)

        rows = (await db.execute(stmt)).scalars().all()
        return list(rows)


async def _async_main() -> int:
    parser = argparse.ArgumentParser(
        description="평가 JSON을 data/에 저장 (단일 턴 → 홀리스틱 → 코드 점수 순)."
    )
    parser.add_argument("--participant-id", type=int, help="participants.id")
    parser.add_argument("--exam-id", type=int, help="exams.id (시험 번호)")
    parser.add_argument("--problem-id", type=int, help="problems.id")
    parser.add_argument("--spec-id", type=int, help="problem_specs.id")
    parser.add_argument("--session-id", type=int, help="prompt_sessions.id")
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="",
        help="저장 경로 (없으면 data/{exam}_{participant}_평가.json)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="파일 대신 stdout에 JSON 출력",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        default=True,
        help="들여쓰기 (기본 True)",
    )
    parser.add_argument(
        "--no-pretty",
        action="store_true",
        help="한 줄 JSON",
    )
    args = parser.parse_args()

    session_ids: List[int] = []
    if args.session_id is not None:
        session_ids = [args.session_id]
    else:
        if args.participant_id is None:
            print("--participant-id 또는 --session-id 가 필요합니다.", file=sys.stderr)
            return 2
        need_filter = (
            args.exam_id is not None
            or args.spec_id is not None
            or args.problem_id is not None
        )
        if not need_filter:
            print(
                "--exam-id, --spec-id, --problem-id 중 하나 이상이 필요합니다.",
                file=sys.stderr,
            )
            return 2
        session_ids = await _find_session_ids(
            args.participant_id,
            args.exam_id,
            args.spec_id,
            args.problem_id,
        )
        if not session_ids:
            print("조건에 맞는 prompt_sessions 가 없습니다.", file=sys.stderr)
            return 1

    bundles: List[Dict[str, Any]] = []
    for sid in session_ids:
        bundles.append(await _export_session_bundle(sid))

    indent = None if args.no_pretty else (2 if args.pretty else None)

    if args.stdout:
        if len(bundles) > 1:
            payload = {"count": len(bundles), "sessions": bundles}
        else:
            payload = bundles[0]
        print(
            json.dumps(payload, ensure_ascii=False, indent=indent, default=_json_default)
        )
        return 0

    os.makedirs(os.path.join(project_root, "data"), exist_ok=True)

    written: List[str] = []
    for i, bundle in enumerate(bundles):
        meta = bundle["meta"]
        exam_id = meta["exam_id"]
        participant_id = meta["participant_id"]
        session_id = meta["session_id"]

        if args.output:
            out_path = args.output
            if len(bundles) > 1 and not args.output.endswith(os.sep):
                base, ext = os.path.splitext(args.output)
                out_path = f"{base}_session_{session_id}{ext or '.json'}"
        elif len(bundles) == 1:
            out_path = _default_output_path(exam_id, participant_id, session_id)
        else:
            out_path = _default_output_path_multi(exam_id, participant_id, session_id)

        text = json.dumps(
            bundle, ensure_ascii=False, indent=indent, default=_json_default
        )
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        written.append(out_path)
        print(f"저장 완료: {out_path}", file=sys.stderr)

    return 0


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(asyncio.run(_async_main()))


if __name__ == "__main__":
    main()
