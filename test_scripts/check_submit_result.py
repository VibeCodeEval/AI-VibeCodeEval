"""
Submit 테스트 결과 확인
test_ids.json에서 자동으로 생성된 ID 사용

기본: scripts/export_evaluation_json.py와 동일 구조의 전체 번들 JSON을 stdout에 출력
  (meta → single_turn_evaluation → whole_session_evaluation → code_scores)

옵션:
  --summary   이전처럼 짧은 텍스트 요약만
  -o PATH     JSON을 파일로도 저장
  --session-id N   test_ids 대신 세션 ID 지정
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Optional

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text, select
from app.infrastructure.persistence.session import get_db_context, init_db


def _load_export_evaluation_module() -> Any:
    path = project_root / "scripts" / "export_evaluation_json.py"
    spec = importlib.util.spec_from_file_location("export_evaluation_json", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"모듈 로드 실패: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_test_ids() -> tuple[int, int]:
    test_ids_file = project_root / "test_ids.json"
    if test_ids_file.exists():
        with open(test_ids_file, "r", encoding="utf-8") as f:
            test_ids = json.load(f)
        return (
            int(test_ids.get("session_id", 1000)),
            int(test_ids.get("submission_id", 1000)),
        )
    print("⚠️  test_ids.json 파일을 찾을 수 없습니다.", file=sys.stderr)
    print("   기본값 사용: SessionId=1000, SubmissionId=1000", file=sys.stderr)
    return 1000, 1000


async def _print_summary(session_id: int, submission_id: int) -> None:
    """이전 방식: DB 직접 조회 요약."""
    print("=" * 80)
    print("Submit 테스트 결과 확인 (요약)")
    print(f"SessionId: {session_id}, SubmissionId: {submission_id}")
    print("=" * 80)

    async with get_db_context() as db:
        try:
            print("\n[1] Submission 상태 확인")
            submission_result = await db.execute(
                text("""
                SELECT id, exam_id, participant_id, spec_id, lang, status, code_inline, created_at
                FROM ai_vibe_coding_test.submissions
                WHERE id = :submission_id
            """),
                {"submission_id": submission_id},
            )
            submission = submission_result.fetchone()

            if submission:
                print("✅ Submission 발견:")
                print(f"   ID: {submission[0]}")
                print(f"   Status: {submission[5]}")
                print(f"   Language: {submission[4]}")
                print(f"   Code 길이: {len(submission[6]) if submission[6] else 0} 문자")
                print(f"   Created: {submission[7]}")
            else:
                print("❌ Submission을 찾을 수 없습니다.")

            print("\n[2] Scores 확인")
            scores_result = await db.execute(
                text("""
                SELECT submission_id, prompt_score, perf_score, correctness_score,
                       total_score, rubric_json, created_at
                FROM ai_vibe_coding_test.scores
                WHERE submission_id = :submission_id
            """),
                {"submission_id": submission_id},
            )
            score = scores_result.fetchone()

            if score:
                print("✅ Score 발견:")
                print(f"   Submission ID: {score[0]}")
                print(f"   Prompt Score: {score[1]}")
                print(f"   Performance Score: {score[2]}")
                print(f"   Correctness Score: {score[3]}")
                print(f"   Total Score: {score[4]}")
                if score[5]:
                    rubric = score[5]
                    if isinstance(rubric, dict):
                        print(f"   Grade: {rubric.get('grade', 'N/A')}")
                        snippet = json.dumps(rubric, indent=2, ensure_ascii=False)
                        if len(snippet) > 400:
                            snippet = snippet[:400] + "..."
                        print(f"   Rubric JSON: {snippet}")
                print(f"   Created: {score[6]}")
            else:
                print("⏳ Score가 아직 생성되지 않았습니다. (평가 진행 중일 수 있음)")

            print("\n[3] Turn Evaluations 확인")
            turn_eval_result = await db.execute(
                text("""
                SELECT id, session_id, turn, evaluation_type, details, created_at
                FROM ai_vibe_coding_test.prompt_evaluations
                WHERE session_id = :session_id AND evaluation_type = 'TURN_EVAL'
                ORDER BY turn
            """),
                {"session_id": session_id},
            )
            turn_evals = turn_eval_result.fetchall()

            if turn_evals:
                print(f"✅ Turn Evaluations 발견: {len(turn_evals)}개")
                for eval_row in turn_evals:
                    d = eval_row[4]
                    sc = (
                        d.get("score", "N/A")
                        if isinstance(d, dict)
                        else "N/A"
                    )
                    print(f"   Turn {eval_row[2]}: Score={sc}")
            else:
                print("⏳ Turn Evaluations가 아직 생성되지 않았습니다.")

            print("\n[4] Holistic Flow Evaluation 확인")
            holistic_result = await db.execute(
                text("""
                SELECT id, session_id, turn, evaluation_type, details, created_at
                FROM ai_vibe_coding_test.prompt_evaluations
                WHERE session_id = :session_id AND evaluation_type = 'HOLISTIC_FLOW'
            """),
                {"session_id": session_id},
            )
            holistic = holistic_result.fetchone()

            if holistic:
                print("✅ Holistic Flow Evaluation 발견:")
                h = holistic[4]
                sc = h.get("score", "N/A") if isinstance(h, dict) else "N/A"
                print(f"   Score: {sc}")
                print(f"   Created: {holistic[5]}")
            else:
                print("⏳ Holistic Flow Evaluation이 아직 생성되지 않았습니다.")

            print("\n[5] Session 상태 확인")
            session_result = await db.execute(
                text("""
                SELECT id, exam_id, participant_id, spec_id, started_at, ended_at
                FROM ai_vibe_coding_test.prompt_sessions
                WHERE id = :session_id
            """),
                {"session_id": session_id},
            )
            session = session_result.fetchone()

            if session:
                print("✅ Session 발견:")
                print(f"   ID: {session[0]}")
                print(f"   Started: {session[4]}")
                print(f"   Ended: {session[5] if session[5] else '진행 중'}")
            else:
                print("❌ Session을 찾을 수 없습니다.")

            print("\n" + "=" * 80)
            print("결과 확인 완료")
            print("=" * 80)

        except Exception as e:
            print(f"\n❌ 오류 발생: {str(e)}", file=sys.stderr)
            import traceback

            traceback.print_exc()
            raise


async def check_submit_result(
    summary_only: bool = False,
    output_path: Optional[Path] = None,
    session_id_override: Optional[int] = None,
) -> None:
    session_id, submission_id = _read_test_ids()
    if session_id_override is not None:
        session_id = session_id_override

    await init_db()

    if summary_only:
        await _print_summary(session_id, submission_id)
        return

    mod = _load_export_evaluation_module()
    bundle = await mod._export_session_bundle(session_id)

    sub = (bundle.get("code_scores") or {}).get("submission") or {}
    bundle_sub_id = sub.get("id")
    if submission_id and bundle_sub_id is not None and bundle_sub_id != submission_id:
        print(
            f"⚠️  test_ids.json submission_id={submission_id} 와 "
            f"번들의 최신 제출 id={bundle_sub_id} 가 다릅니다. "
            f"code_scores 는 세션 기준 최신 제출입니다.",
            file=sys.stderr,
        )

    indent = 2
    payload = json.dumps(
        bundle, ensure_ascii=False, indent=indent, default=mod._json_default
    )
    print(payload)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
        print(f"저장: {output_path}", file=sys.stderr)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Submit 테스트 결과 — 기본은 export_evaluation_json 과 동일 구조의 JSON"
    )
    p.add_argument(
        "--summary",
        action="store_true",
        help="짧은 텍스트 요약만 (이전 동작)",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="JSON을 이 경로에도 저장",
    )
    p.add_argument(
        "--session-id",
        type=int,
        default=None,
        help="test_ids.json 대신 사용할 prompt_sessions.id",
    )
    return p.parse_args()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    args = _parse_args()
    asyncio.run(
        check_submit_result(
            summary_only=args.summary,
            output_path=args.output,
            session_id_override=args.session_id,
        )
    )
