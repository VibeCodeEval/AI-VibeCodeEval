"""
Submit 테스트를 위한 데이터 준비
SessionId: 1000, SubmissionId: 1000

사전 조건: PostgreSQL 에 ai_vibe_coding_test 스키마와 테이블이 있어야 합니다.
  - 참가자 테이블이 `users` 인 DB(Core 연동)면 .env 에 VIBECODE_PARTICIPANT_TABLE=users
  - Core DB 는 exams.created_by·ends_at, users.phone, exam_participants.token_*,
    prompt_sessions.total_tokens 등 NOT NULL 이 많을 수 있음 — 스크립트가 기본값을 넣음.
  - exams.created_by: admins 가 비어 있으면 .env VIBECODE_SEED_EXAM_CREATED_BY=<admins.id>
  - init-db.sql 기본은 `participants` 테이블입니다.
  - Postgres 포트는 docker-compose.dev.yml 기준 5435 — .env DATABASE_URL 과 맞출 것.
"""
import asyncio
import re
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.core.config import get_settings
from app.infrastructure.persistence.session import get_db_context, init_db


def _print_schema_help() -> None:
    print(
        """
❌ 필요한 테이블이 없습니다 (예: participants / users, exams 등).

참가자 테이블만 `users` 인 경우 .env 에 VIBECODE_PARTICIPANT_TABLE=users 를 넣고 Worker/스크립트를 다시 실행하세요.

그 외에는 스키마를 만든 뒤 다시 실행하세요.

  [1] Docker로 Postgres 새로 띄우기 (init-db.sql 자동 실행, 빈 볼륨일 때만)
      cd 프로젝트루트
      docker compose -f docker-compose.dev.yml up -d postgres

  [2] 이미 Postgres가 있다면 SQL 파일 적용
      psql "<DATABASE_URL>" -f scripts/init-db.sql
      (또는 호스트/포트/유저에 맞게 -h -p -U -d -f scripts/init-db.sql)

  [3] 컨테이너는 있는데 테이블만 없을 때 (예시)
      Get-Content scripts\\init-db.sql | docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test

※ .env 의 DATABASE_URL 이 실제 접속 중인 DB(포트 5435 vs 5432 등)와 같은지 확인하세요.
""",
        file=sys.stderr,
    )


async def setup_submit_test_data():
    """Submit 테스트를 위한 데이터 생성"""
    print("=" * 80)
    print("Submit 테스트 데이터 준비")
    print("=" * 80)
    
    # DB 초기화
    await init_db()
    print("✅ DB 연결 완료")

    p_table = get_settings().VIBECODE_PARTICIPANT_TABLE
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", p_table):
        print(f"잘못된 VIBECODE_PARTICIPANT_TABLE: {p_table!r}", file=sys.stderr)
        raise SystemExit(2)
    print(f"📌 참가자 테이블: ai_vibe_coding_test.{p_table} (VIBECODE_PARTICIPANT_TABLE)")

    async with get_db_context() as db:
        try:
            # 최대 ID 조회하여 자동 증가
            try:
                exam_result = await db.execute(text("""
                    SELECT COALESCE(MAX(id), 0) + 1 FROM ai_vibe_coding_test.exams
                """))
                exam_id = exam_result.scalar()

                participant_result = await db.execute(
                    text(f"""
                    SELECT COALESCE(MAX(id), 0) + 1 FROM ai_vibe_coding_test.{p_table}
                """)
                )
                participant_id = participant_result.scalar()

                exam_participant_result = await db.execute(text("""
                    SELECT COALESCE(MAX(id), 0) + 1 FROM ai_vibe_coding_test.exam_participants
                """))
                exam_participant_id = exam_participant_result.scalar()

                session_result = await db.execute(text("""
                    SELECT COALESCE(MAX(id), 0) + 1 FROM ai_vibe_coding_test.prompt_sessions
                """))
                session_id = session_result.scalar()

                submission_result = await db.execute(text("""
                    SELECT COALESCE(MAX(id), 0) + 1 FROM ai_vibe_coding_test.submissions
                """))
                submission_id = submission_result.scalar()
            except ProgrammingError as e:
                orig = str(getattr(e, "orig", e))
                if "does not exist" in orig or "UndefinedTableError" in orig:
                    _print_schema_help()
                    raise SystemExit(2) from e
                raise
            
            print(f"📋 자동 생성된 ID:")
            print(f"   - Exam ID: {exam_id}")
            print(f"   - Participant ID: {participant_id}")
            print(f"   - ExamParticipant ID: {exam_participant_id}")
            print(f"   - Session ID: {session_id}")
            print(f"   - Submission ID: {submission_id}")
            print()

            # 백엔드 DB는 exams.created_by 가 NOT NULL 인 경우가 많음
            created_by = get_settings().VIBECODE_SEED_EXAM_CREATED_BY
            if created_by is None:
                admin_row = await db.execute(
                    text("SELECT MIN(id) FROM ai_vibe_coding_test.admins")
                )
                created_by = admin_row.scalar()
            if created_by is None:
                print(
                    "exams.created_by 가 필요한데 admins 행을 찾을 수 없습니다.\n"
                    "  .env 에 VIBECODE_SEED_EXAM_CREATED_BY=<관리자 admins.id> 를 넣으세요.",
                    file=sys.stderr,
                )
                raise SystemExit(2)
            print(f"📌 exams.created_by = {created_by}")

            # 1. Exam 생성 (Core DB는 ends_at NOT NULL 등 제약이 init-db.sql 보다 강할 수 있음)
            await db.execute(
                text("""
                INSERT INTO ai_vibe_coding_test.exams (
                    id, title, state, version, created_by,
                    starts_at, ends_at, created_at, updated_at
                )
                VALUES (
                    :exam_id, 'Submit 테스트 시험', 'RUNNING', 1, :created_by,
                    NOW(), NOW() + INTERVAL '365 days', NOW(), NOW()
                )
                ON CONFLICT (id) DO UPDATE
                SET title = EXCLUDED.title, state = EXCLUDED.state
            """),
                {"exam_id": exam_id, "created_by": created_by},
            )
            print(f"✅ Exam 생성 완료 (ID: {exam_id})")
            
            # 2. 참가자 행 생성 (Core users 는 phone NOT NULL 등이 흔함)
            if p_table == "users":
                # UNIQUE(phone) 대비 id 기반 더미 번호
                seed_phone = f"0109{participant_id:07d}"
                await db.execute(
                    text(f"""
                    INSERT INTO ai_vibe_coding_test.{p_table} (id, name, phone)
                    VALUES (:participant_id, 'Submit 테스트 사용자', :phone)
                    ON CONFLICT (id) DO UPDATE
                    SET name = EXCLUDED.name, phone = EXCLUDED.phone
                """),
                    {"participant_id": participant_id, "phone": seed_phone},
                )
            else:
                await db.execute(
                    text(f"""
                    INSERT INTO ai_vibe_coding_test.{p_table} (id, name)
                    VALUES (:participant_id, 'Submit 테스트 사용자')
                    ON CONFLICT (id) DO UPDATE
                    SET name = EXCLUDED.name
                """),
                    {"participant_id": participant_id},
                )
            print(f"✅ Participant 생성 완료 (ID: {participant_id})")
            
            # 3. Problem 생성 (ID: 1 - 외판원 문제)
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.problems (id, title, difficulty, status)
                VALUES (1, '외판원 순회', 'HARD', 'PUBLISHED')
                ON CONFLICT (id) DO UPDATE
                SET title = EXCLUDED.title, difficulty = EXCLUDED.difficulty, status = EXCLUDED.status
            """))
            print("✅ Problem 생성 완료 (ID: 1 - 외판원 순회)")
            
            # 4. ProblemSpec: Core DB 는 (problem_id, version) 유니크 — 기존 행이 있으면 재사용
            spec_row = await db.execute(
                text("""
                    SELECT spec_id FROM ai_vibe_coding_test.problem_specs
                    WHERE problem_id = 1 AND version = 1
                    ORDER BY spec_id
                    LIMIT 1
                """)
            )
            spec_id = spec_row.scalar()
            if spec_id is None:
                ns = await db.execute(
                    text(
                        "SELECT COALESCE(MAX(spec_id), 0) + 1 FROM ai_vibe_coding_test.problem_specs"
                    )
                )
                spec_id = ns.scalar()
                await db.execute(
                    text("""
                    INSERT INTO ai_vibe_coding_test.problem_specs (spec_id, problem_id, version, content_md)
                    VALUES (:spec_id, 1, 1, '외판원 순회 문제 스펙')
                """),
                    {"spec_id": spec_id},
                )
                print(f"✅ ProblemSpec 생성 완료 (spec_id: {spec_id})")
            else:
                print(
                    f"✅ 기존 ProblemSpec 사용 (spec_id: {spec_id}, problem_id=1, version=1)"
                )

            # 5. ExamParticipant 생성
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.exam_participants (
                    id, exam_id, participant_id, spec_id, state,
                    token_limit, token_used, joined_at
                )
                VALUES (
                    :exam_participant_id, :exam_id, :participant_id, :spec_id, 'IN_PROGRESS',
                    1000000, 0, NOW()
                )
                ON CONFLICT (id) DO UPDATE
                SET exam_id = EXCLUDED.exam_id, 
                    participant_id = EXCLUDED.participant_id,
                    spec_id = EXCLUDED.spec_id,
                    state = EXCLUDED.state
            """), {
                "exam_participant_id": exam_participant_id,
                "exam_id": exam_id,
                "participant_id": participant_id,
                "spec_id": spec_id,
            })
            print(f"✅ ExamParticipant 생성 완료 (ID: {exam_participant_id})")
            
            # 6. PromptSession 생성 - ended_at을 NULL로 설정 (진행 중인 세션)
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.prompt_sessions (
                    id, exam_id, participant_id, spec_id, started_at, ended_at, total_tokens
                )
                VALUES (:session_id, :exam_id, :participant_id, :spec_id, NOW(), NULL, 0)
                ON CONFLICT (id) DO UPDATE
                SET exam_id = EXCLUDED.exam_id,
                    participant_id = EXCLUDED.participant_id,
                    spec_id = EXCLUDED.spec_id,
                    started_at = COALESCE(prompt_sessions.started_at, EXCLUDED.started_at),
                    ended_at = NULL  -- 진행 중인 세션으로 설정
            """), {
                "session_id": session_id,
                "exam_id": exam_id,
                "participant_id": participant_id,
                "spec_id": spec_id,
            })
            print(f"✅ PromptSession 생성 완료 (ID: {session_id})")
            
            # 7. Submission 생성 - 제출 전 상태
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.submissions (id, exam_id, participant_id, spec_id, lang, code_inline, status)
                VALUES (:submission_id, :exam_id, :participant_id, :spec_id, 'python3.11', '', 'QUEUED')
                ON CONFLICT (id) DO UPDATE
                SET exam_id = EXCLUDED.exam_id,
                    participant_id = EXCLUDED.participant_id,
                    spec_id = EXCLUDED.spec_id,
                    lang = EXCLUDED.lang,
                    status = EXCLUDED.status
            """), {
                "submission_id": submission_id,
                "exam_id": exam_id,
                "participant_id": participant_id,
                "spec_id": spec_id,
            })
            print(f"✅ Submission 생성 완료 (ID: {submission_id})")
            
            await db.commit()
            print("\n✅ 모든 테스트 데이터 생성 완료!")
            print("\n생성된 데이터:")
            print(f"  - Exam: ID={exam_id}")
            print(f"  - Participant: ID={participant_id}")
            print("  - Problem: ID=1 (외판원 순회)")
            print(f"  - ProblemSpec: spec_id={spec_id}")
            print(
                f"  - ExamParticipant: ID={exam_participant_id} (exam_id={exam_id}, participant_id={participant_id}, spec_id={spec_id})"
            )
            print(f"  - PromptSession: ID={session_id}")
            print(f"  - Submission: ID={submission_id}")
            
            # 생성된 ID를 파일에 저장 (다른 스크립트에서 사용)
            import json
            test_ids = {
                "session_id": session_id,
                "submission_id": submission_id,
                "exam_participant_id": exam_participant_id,
                "exam_id": exam_id,
                "participant_id": participant_id,
                "spec_id": spec_id,
            }
            with open("test_ids.json", "w", encoding="utf-8") as f:
                json.dump(test_ids, f, indent=2, ensure_ascii=False)
            print(f"\n💾 생성된 ID가 test_ids.json에 저장되었습니다.")
            print(f"   다른 테스트 스크립트에서 이 파일을 읽어서 사용할 수 있습니다.")
            
        except Exception as e:
            await db.rollback()
            print(f"\n❌ 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(setup_submit_test_data())

