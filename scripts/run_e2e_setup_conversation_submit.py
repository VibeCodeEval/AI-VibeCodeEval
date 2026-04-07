#!/usr/bin/env python3
"""
로컬 E2E: DB 시드 → 대화 JSON save-message → 제출(submit)까지 한 번에 실행합니다.

1) test_scripts/setup_submit_test_data.py
   - exams / participants / exam_participants / prompt_sessions / submissions 등 생성
   - 매 실행마다 MAX(id)+1 로 새 exam_id, participant_id, session_id, submission_id
2) scripts/load_conversation_json.py
   - data/평가용_대화_3turns.json 적재 + 기본 TSP 코드로 submit
   - spec_id 는 test_ids.json 의 spec_id 를 우선 사용 (없으면 10)

사전 조건: PostgreSQL, Redis, Worker 가 .env 기준으로 동작 중일 것.
Worker 는 별도 터미널에서 띄운 뒤 이 스크립트를 실행하는 것을 권장합니다.

예:
  cd C:\\P-project\\AI-VibeCodeEval
  uv run python scripts/run_e2e_setup_conversation_submit.py

옵션:
  --skip-setup       이미 test_ids.json 이 있을 때 시드 생략
  --conversation-json PATH
  --code-file PATH   제출 코드 (기본: scripts/fixtures/tsp_submit_solution.py)
  --worker-url URL
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_step(argv: list[str], *, cwd: Path) -> None:
    print("\n>>", " ".join(argv), flush=True)
    r = subprocess.run(argv, cwd=cwd)
    if r.returncode != 0:
        raise SystemExit(r.returncode)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--skip-setup", action="store_true")
    p.add_argument(
        "--conversation-json",
        type=Path,
        default=ROOT / "data" / "평가용_대화_3turns.json",
    )
    p.add_argument(
        "--code-file",
        type=Path,
        default=ROOT / "scripts" / "fixtures" / "tsp_submit_solution.py",
    )
    p.add_argument("--worker-url", default="http://127.0.0.1:8000")
    args = p.parse_args()

    uv = "uv"
    if sys.platform == "win32":
        # uv 가 PATH 에 있으면 그대로 사용
        pass

    if not args.skip_setup:
        run_step(
            [uv, "run", "python", "test_scripts/setup_submit_test_data.py"],
            cwd=ROOT,
        )
    else:
        tid = ROOT / "test_ids.json"
        if not tid.is_file():
            print("--skip-setup 인데 test_ids.json 이 없습니다.", file=sys.stderr)
            return 2

    if not args.conversation_json.is_file():
        print(f"대화 JSON 없음: {args.conversation_json}", file=sys.stderr)
        return 2
    if not args.code_file.is_file():
        print(f"코드 파일 없음: {args.code_file}", file=sys.stderr)
        return 2

    tid_path = ROOT / "test_ids.json"
    spec_id = 10
    if tid_path.is_file():
        try:
            with tid_path.open(encoding="utf-8") as f:
                tid = json.load(f)
            if tid.get("spec_id") is not None:
                spec_id = int(tid["spec_id"])
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    run_step(
        [
            uv,
            "run",
            "python",
            "scripts/load_conversation_json.py",
            str(args.conversation_json),
            "--test-ids",
            str(tid_path),
            "--worker-url",
            args.worker_url,
            "--submit",
            "--code-file",
            str(args.code_file),
            "--problem-id",
            "1",
            "--spec-id",
            str(spec_id),
        ],
        cwd=ROOT,
    )

    print("\n✅ E2E 완료 (시드 → 대화 적재 → 제출 요청). Worker 로그·DB에서 평가 결과를 확인하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
