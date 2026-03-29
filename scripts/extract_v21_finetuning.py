#!/usr/bin/env python
"""
v2.1 Finetuning 데이터 추출 (Step 06)

PostgreSQL에서 v21_summary/code_quality_metrics가 포함된 평가 데이터를 추출하여
AI 학습용 JSONL을 생성합니다.

- 대상: scores.rubric_json에 integrated_evaluation(code_quality_metrics 등)이 있는 레코드
- 결합: 해당 세션의 prompt_messages(질문/답변) + v1 코드, 최종 Grade
- 출력: instruction, context, metrics, label 구조의 JSONL

사용법:
    python scripts/extract_v21_finetuning.py
    python scripts/extract_v21_finetuning.py --output v21_finetuning.jsonl
    python scripts/extract_v21_finetuning.py --print-example   # Mock A학점 1건 출력 (DB 불필요)
    python scripts/extract_v21_finetuning.py --phase2-only    # instruction에 Phase 2 프롬프트만
"""

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv(project_root / ".env")

SCHEMA = "ai_vibe_coding_test"


def get_db_config() -> dict:
    """환경 변수에서 DB 설정 읽기"""
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5435")),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "database": os.getenv("POSTGRES_DB", "ai_vibe_coding_test"),
    }


def connect_db():
    """PostgreSQL 연결"""
    config = get_db_config()
    print(f"[INFO] DB 연결: {config['host']}:{config['port']}/{config['database']}")
    return psycopg2.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        database=config["database"],
    )


# v2.1 평가가 있는 Score 조회 (integrated_evaluation 존재)
SQL_SCORES_V21 = f"""
SET search_path TO {SCHEMA};

SELECT
    s.submission_id,
    s.rubric_json,
    sub.exam_id,
    sub.participant_id,
    sub.spec_id,
    sub.created_at AS submission_created_at
FROM {SCHEMA}.scores s
JOIN {SCHEMA}.submissions sub ON sub.id = s.submission_id
WHERE s.rubric_json IS NOT NULL
  AND s.rubric_json ? 'integrated_evaluation'
  AND s.rubric_json->'integrated_evaluation' IS NOT NULL
  AND s.rubric_json->'integrated_evaluation' != 'null'::jsonb
ORDER BY s.submission_id;
"""


def get_session_id_for_submission(
    conn, rubric_json: dict, exam_id: int, participant_id: int, spec_id: int, submission_created_at
) -> int | None:
    """rubric_json의 session_id 사용, 없으면 (exam_id, participant_id, spec_id) + 시간으로 세션 추론"""
    sid = None
    if isinstance(rubric_json, dict):
        sid = rubric_json.get("session_id")
        if sid is not None:
            return int(sid)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"""
            SET search_path TO {SCHEMA};
            SELECT id FROM {SCHEMA}.prompt_sessions
            WHERE exam_id = %s AND participant_id = %s AND spec_id = %s
              AND ended_at IS NOT NULL
              AND ended_at <= %s
            ORDER BY ended_at DESC
            LIMIT 1;
            """,
            (exam_id, participant_id, spec_id, submission_created_at),
        )
        row = cur.fetchone()
        return int(row["id"]) if row else None


def get_user_prompts_and_v1_code(
    conn, session_id: int
) -> tuple[list[tuple[int, str]], str | None, int | None]:
    """
    세션의 사용자 프롬프트 (turn, content), v1 코드, v1 저장 턴 번호 반환.

    Returns:
        (prompts_with_turn, v1_code, v1_turn)
        - prompts_with_turn: [(turn, content), ...] (USER만, turn 오름차순)
        - v1_code: Phase 1 SAVE 시 저장된 코드 (없으면 None)
        - v1_turn: v1이 저장된 메시지의 turn (없으면 None). 이 턴 이후가 Phase 2.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"""
            SET search_path TO {SCHEMA};
            SELECT turn, role, content, meta
            FROM {SCHEMA}.prompt_messages
            WHERE session_id = %s
            ORDER BY turn;
            """,
            (session_id,),
        )
        rows = cur.fetchall()

    prompts = []
    v1_code = None
    v1_turn = None
    for r in rows:
        role = (r.get("role") or "").upper()
        if role == "USER":
            prompts.append((r["turn"], (r["content"] or "").strip()))
        if v1_code is None and r.get("meta") and isinstance(r["meta"], dict):
            if r["meta"].get("is_v1_checkpoint") and r["meta"].get("code_snapshot"):
                v1_code = r["meta"].get("code_snapshot") or ""
                v1_turn = r["turn"]

    prompts.sort(key=lambda x: x[0])
    return prompts, v1_code, v1_turn


def build_metrics(
    integrated_evaluation: dict | None,
    rubric_json: dict | None = None,
) -> dict:
    """code_quality_metrics에서 ΔCC, AST 매칭 등 추출. rubric_json에서 is_correct(Judge0 통과) 추가."""
    out = {}
    if integrated_evaluation and isinstance(integrated_evaluation, dict):
        cqm = integrated_evaluation.get("code_quality_metrics") or {}
        delta_cc = cqm.get("delta_cc") or {}
        out = {
            "delta_cc_pct": delta_cc.get("delta_cc_pct"),
            "ast_pattern_matched": cqm.get("ast_pattern_matched"),
            "ast_applicable": cqm.get("ast_applicable"),
            "has_v1": cqm.get("has_v1"),
            "junior_grade": cqm.get("junior_grade"),
        }
    # Judge0 통과 여부: 동작하면서 설계가 깔끔한 코드 학습용
    if rubric_json is not None and isinstance(rubric_json, dict):
        correctness = rubric_json.get("correctness_score")
        out["is_correct"] = correctness is not None and float(correctness) >= 99.5
    return out


def print_mock_example():
    """DB 없이 A학점 세션 1건이 JSONL로 추출된 모양을 터미널에 출력 (instruction, metrics 확인용)."""
    # V2.1 예시 문제: 스마트 게이트 2026 (Phase 1 → Phase 2 요구사항 변경)
    mock = {
        "submission_id": 9001,
        "session_id": 100,
        "instruction": [
            "공항 게이트 보안·수하물 과금 로직 구현해줘. 여권 만료, 항공편 상태, 좌석별 수하물 허용량 체크하고, 규칙은 인터페이스로 분리해줘.",
            "SAVE",
            "요구사항 바뀌었어. threat_level이 HIGH면 기존 규칙보다 우선해서 전부 SECURITY_CHECK로 보내도록 SecurityRule을 BaseRule 상속해서 추가해줘.",
            "누적 과금 3명 나온 항공편은 4번째부터 허용 무게 -5kg 적용해줘. GateManager는 전략 패턴 유지해줘.",
        ],
        "instruction_phase2": [
            "요구사항 바뀌었어. threat_level이 HIGH면 기존 규칙보다 우선해서 전부 SECURITY_CHECK로 보내도록 SecurityRule을 BaseRule 상속해서 추가해줘.",
            "누적 과금 3명 나온 항공편은 4번째부터 허용 무게 -5kg 적용해줘. GateManager는 전략 패턴 유지해줘.",
        ],
        "context": "class BaseRule:\n    def check(self, passenger): ...\n\nclass PassportRule(BaseRule): ...\nclass LuggageRule(BaseRule): ...\n\nclass GateManager:\n    def __init__(self, rules): self.rules = rules\n    def process(self, passenger):\n        for r in self.rules: r.check(passenger)\n",
        "metrics": {
            "delta_cc_pct": -15.2,
            "ast_pattern_matched": True,
            "ast_applicable": True,
            "has_v1": True,
            "junior_grade": False,
            "is_correct": True,
        },
        "label": "A",
    }
    print("[Mock 예제] A학점 세션 1건 JSONL 추출 예시 (DB 미연결)")
    print("-" * 60)
    print(json.dumps(mock, ensure_ascii=False, indent=2))
    print("-" * 60)
    print("instruction: 세션 전체 사용자 프롬프트 (Phase 1 + Phase 2)")
    print("instruction_phase2: v1 SAVE 이후 프롬프트만 (요구사항 변경 대응 지시문)")
    print("metrics: code_quality_metrics 기반 (ΔCC, AST 매칭 등)")


def main():
    parser = argparse.ArgumentParser(description="v2.1 Finetuning JSONL 추출")
    parser.add_argument(
        "--output",
        "-o",
        default="v21_finetuning.jsonl",
        help="출력 JSONL 파일 경로 (기본: v21_finetuning.jsonl)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="출력 디렉터리 (미지정 시 현재 디렉터리)",
    )
    parser.add_argument(
        "--print-example",
        "--example",
        action="store_true",
        dest="print_example",
        help="DB 연결 없이 Mock A학점 JSONL 예시 1건을 터미널에 출력 후 종료",
    )
    parser.add_argument(
        "--phase2-only",
        action="store_true",
        help="instruction 필드에 Phase 2(v1 SAVE 이후) 프롬프트만 넣음. 요구사항 변경 대응 지시문만 학습 시 사용",
    )
    args = parser.parse_args()

    if args.print_example:
        print_mock_example()
        return

    out_path = Path(args.output)
    if args.output_dir:
        out_path = Path(args.output_dir) / out_path.name
    out_path = out_path.resolve()

    conn = connect_db()
    grade_counter: Counter = Counter()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(SQL_SCORES_V21)
            rows = cur.fetchall()

        if not rows:
            print("[INFO] v2.1 평가 데이터(integrated_evaluation)가 없습니다.")
            return

        print(f"[INFO] v2.1 Score 레코드 수: {len(rows)}")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        skipped_no_session = 0
        skipped_no_instruction = 0

        with open(out_path, "w", encoding="utf-8") as f:
            for row in rows:
                submission_id = row["submission_id"]
                rubric_json = row["rubric_json"] or {}
                grade = (rubric_json.get("grade") or "").strip().upper()
                if grade:
                    grade_counter[grade] += 1

                integrated = rubric_json.get("integrated_evaluation")
                session_id = get_session_id_for_submission(
                    conn,
                    rubric_json,
                    row["exam_id"],
                    row["participant_id"],
                    row["spec_id"],
                    row["submission_created_at"],
                )
                if not session_id:
                    skipped_no_session += 1
                    continue

                prompts_with_turn, context, v1_turn = get_user_prompts_and_v1_code(
                    conn, session_id
                )
                instruction_all = [c for _, c in prompts_with_turn if c]
                instruction_phase2 = (
                    [c for t, c in prompts_with_turn if c and v1_turn is not None and t > v1_turn]
                    if v1_turn is not None
                    else []
                )
                if not instruction_all:
                    skipped_no_instruction += 1
                    continue

                metrics = build_metrics(integrated, rubric_json=rubric_json)
                # --phase2-only 이면 instruction에 Phase 2만; 아니면 전체
                instruction_main = (
                    instruction_phase2 if args.phase2_only else instruction_all
                )
                record = {
                    "submission_id": submission_id,
                    "session_id": session_id,
                    "instruction": instruction_main,
                    "context": context or "",
                    "metrics": metrics,
                    "label": grade or "?",
                }
                record["instruction_phase2"] = instruction_phase2
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1

        print(f"[INFO] 작성된 레코드: {written} -> {out_path}")
        if skipped_no_session:
            print(f"[WARN] 세션 매칭 실패로 건너뜀: {skipped_no_session}")
        if skipped_no_instruction:
            print(f"[WARN] 사용자 프롬프트 없음으로 건너뜀: {skipped_no_instruction}")

        # Grade 분포 출력
        if grade_counter:
            print("\n[Grade 분포]")
            for g in ("A", "B", "C", "D", "F"):
                cnt = grade_counter.get(g, 0)
                bar = "█" * min(cnt, 80) + ("…" if cnt > 80 else "")
                print(f"  {g}: {cnt:4d}  {bar}")
            other = sum(v for k, v in grade_counter.items() if k not in "ABCDEF")
            if other:
                print(f"  기타: {other:4d}  (빈 값 또는 비표준 등급)")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
