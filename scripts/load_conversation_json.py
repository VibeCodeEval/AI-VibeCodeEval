#!/usr/bin/env python3
"""
평가용_대화_3turns.json 같은 배열을 순서대로 POST /api/chat/save-message 에 넣고,
선택적으로 POST /api/session/submit 으로 제출까지 수행합니다.

사전 준비 (로컬 기준)
--------------------
1) PostgreSQL + Redis + Worker(uvicorn) 기동, .env 에 DB/Redis URL 설정
2) exam / participant / exam_participants(spec_id 필수) 행 존재
   - 빠르게: `uv run python test_scripts/setup_submit_test_data.py`
     → test_ids.json 에 exam_id, participant_id, submission_id 가 생김
3) 대화 JSON 의 examId·participantId 를 2)와 맞추거나, 본 스크립트에
   --test-ids test_ids.json 을 주어 자동 치환
4) 제출까지 할 때: submissions 행이 있어야 하면 setup 스크립트처럼 미리 넣어두거나,
   Core 에서 만든 submissionId 를 --submission-id 로 전달

예시
----
  uv run python scripts/load_conversation_json.py data/평가용_대화_3turns.json \\
    --test-ids test_ids.json \\
    --submit --code-file path/to/solution.py

  # 대화만 적재 (제출 없음)
  uv run python scripts/load_conversation_json.py data/평가용_대화_3turns.json \\
    --worker-url http://127.0.0.1:8000 --test-ids test_ids.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx


def _load_test_ids(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    p = argparse.ArgumentParser(description="대화 JSON → save-message (+ 선택 submit)")
    p.add_argument("conversation_json", type=Path, help="메시지 객체 배열 JSON")
    p.add_argument("--worker-url", default="http://127.0.0.1:8000", help="Worker 베이스 URL")
    p.add_argument(
        "--test-ids",
        type=Path,
        help="test_ids.json — exam_id, participant_id, submission_id(제출 시) 사용",
    )
    p.add_argument("--exam-id", type=int, help="모든 메시지의 examId 덮어쓰기")
    p.add_argument("--participant-id", type=int, help="모든 메시지의 participantId 덮어쓰기")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--submit", action="store_true", help="save 후 submit 호출")
    p.add_argument("--code-file", type=Path, help="제출할 코드 파일 (--submit 시 필요)")
    p.add_argument("--submission-id", type=int, help="제출 ID (미지정 시 test_ids)")
    p.add_argument("--problem-id", type=int, default=1)
    p.add_argument("--spec-id", type=int, default=10, help="exam_participants.spec_id 와 일치")
    p.add_argument("--language", default="python3.11")
    args = p.parse_args()

    raw = args.conversation_json.read_text(encoding="utf-8")
    messages: list[dict[str, Any]] = json.loads(raw)
    if not isinstance(messages, list) or not messages:
        print("JSON 은 비어 있지 않은 배열이어야 합니다.", file=sys.stderr)
        return 2

    tid: dict[str, Any] = {}
    if args.test_ids:
        tid = _load_test_ids(args.test_ids)

    exam_id = args.exam_id or tid.get("exam_id")
    participant_id = args.participant_id or tid.get("participant_id")
    submission_id = args.submission_id or tid.get("submission_id")

    base = args.worker_url.rstrip("/")
    save_url = f"{base}/api/chat/save-message"
    submit_url = f"{base}/api/session/submit"

    with httpx.Client(timeout=120.0) as client:
        for i, msg in enumerate(messages):
            body = dict(msg)
            if exam_id is not None:
                body["examId"] = exam_id
            if participant_id is not None:
                body["participantId"] = participant_id
            for k in ("examId", "participantId", "turn", "role", "content"):
                if k not in body:
                    print(f"메시지 {i}: 필수 키 누락: {k}", file=sys.stderr)
                    return 2
            if args.dry_run:
                print(f"[DRY-RUN] POST {save_url} turn={body['turn']} role={body['role']}")
                continue
            r = client.post(save_url, json=body)
            print(f"save-message [{i}] turn={body['turn']} role={body['role']} -> {r.status_code}")
            if r.status_code >= 400:
                print(r.text[:2000], file=sys.stderr)
                return 1
            try:
                data = r.json()
                if not data.get("success", True):
                    print(data, file=sys.stderr)
                    return 1
            except Exception:
                pass

        if args.submit:
            if not args.code_file:
                print("--submit 이면 --code-file 필수입니다.", file=sys.stderr)
                return 2
            if exam_id is None or participant_id is None:
                print("제출에는 exam_id, participant_id 가 필요합니다 (--test-ids 또는 --exam-id/--participant-id).", file=sys.stderr)
                return 2
            if submission_id is None:
                print("제출에는 submission_id 가 필요합니다 (--submission-id 또는 test_ids.json).", file=sys.stderr)
                return 2
            code = args.code_file.read_text(encoding="utf-8")
            submit_body = {
                "examId": exam_id,
                "participantId": participant_id,
                "problemId": args.problem_id,
                "specId": args.spec_id,
                "finalCode": code,
                "language": args.language,
                "submissionId": submission_id,
            }
            if args.dry_run:
                print(f"[DRY-RUN] POST {submit_url} submissionId={submission_id}")
                return 0
            r = client.post(submit_url, json=submit_body, timeout=600.0)
            print(f"submit -> {r.status_code}")
            try:
                print(json.dumps(r.json(), ensure_ascii=False, indent=2)[:3000])
            except Exception:
                print(r.text[:3000])
            if r.status_code >= 400:
                return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
