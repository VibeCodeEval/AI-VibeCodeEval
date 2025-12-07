"""
Submit 테스트를 위한 데이터 준비
SessionId: 1000, SubmissionId: 1000
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.infrastructure.persistence.session import get_db_context, init_db


async def setup_submit_test_data():
    """Submit 테스트를 위한 데이터 생성"""
    print("=" * 80)
    print("Submit 테스트 데이터 준비")
    print("=" * 80)
    
    # DB 초기화
    await init_db()
    print("✅ DB 연결 완료")
    
    async with get_db_context() as db:
        try:
            # 최대 ID 조회하여 자동 증가
            # Exam ID
            exam_result = await db.execute(text("""
                SELECT COALESCE(MAX(id), 0) + 1 FROM ai_vibe_coding_test.exams
            """))
            exam_id = exam_result.scalar()
            
            # Participant ID
            participant_result = await db.execute(text("""
                SELECT COALESCE(MAX(id), 0) + 1 FROM ai_vibe_coding_test.participants
            """))
            participant_id = participant_result.scalar()
            
            # ExamParticipant ID
            exam_participant_result = await db.execute(text("""
                SELECT COALESCE(MAX(id), 0) + 1 FROM ai_vibe_coding_test.exam_participants
            """))
            exam_participant_id = exam_participant_result.scalar()
            
            # Session ID
            session_result = await db.execute(text("""
                SELECT COALESCE(MAX(id), 0) + 1 FROM ai_vibe_coding_test.prompt_sessions
            """))
            session_id = session_result.scalar()
            
            # Submission ID
            submission_result = await db.execute(text("""
                SELECT COALESCE(MAX(id), 0) + 1 FROM ai_vibe_coding_test.submissions
            """))
            submission_id = submission_result.scalar()
            
            print(f"📋 자동 생성된 ID:")
            print(f"   - Exam ID: {exam_id}")
            print(f"   - Participant ID: {participant_id}")
            print(f"   - ExamParticipant ID: {exam_participant_id}")
            print(f"   - Session ID: {session_id}")
            print(f"   - Submission ID: {submission_id}")
            print()
            
            # 1. Exam 생성
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.exams (id, title, state, version)
                VALUES (:exam_id, 'Submit 테스트 시험', 'RUNNING', 1)
                ON CONFLICT (id) DO UPDATE
                SET title = EXCLUDED.title, state = EXCLUDED.state
            """), {"exam_id": exam_id})
            print(f"✅ Exam 생성 완료 (ID: {exam_id})")
            
            # 2. Participant 생성
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.participants (id, name)
                VALUES (:participant_id, 'Submit 테스트 사용자')
                ON CONFLICT (id) DO UPDATE
                SET name = EXCLUDED.name
            """), {"participant_id": participant_id})
            print(f"✅ Participant 생성 완료 (ID: {participant_id})")
            
            # 3. Problem 생성 (ID: 1 - 외판원 문제)
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.problems (id, title, difficulty, status)
                VALUES (1, '외판원 순회', 'HARD', 'PUBLISHED')
                ON CONFLICT (id) DO UPDATE
                SET title = EXCLUDED.title, difficulty = EXCLUDED.difficulty, status = EXCLUDED.status
            """))
            print("✅ Problem 생성 완료 (ID: 1 - 외판원 순회)")
            
            # 4. ProblemSpec 생성 (spec_id: 10 - 외판원 문제 스펙)
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.problem_specs (spec_id, problem_id, version, content_md)
                VALUES (10, 1, 1, '외판원 순회 문제 스펙')
                ON CONFLICT (spec_id) DO UPDATE
                SET problem_id = EXCLUDED.problem_id, version = EXCLUDED.version
            """))
            print("✅ ProblemSpec 생성 완료 (spec_id: 10)")
            
            # 5. ExamParticipant 생성
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.exam_participants (id, exam_id, participant_id, spec_id, state)
                VALUES (:exam_participant_id, :exam_id, :participant_id, 10, 'IN_PROGRESS')
                ON CONFLICT (id) DO UPDATE
                SET exam_id = EXCLUDED.exam_id, 
                    participant_id = EXCLUDED.participant_id,
                    spec_id = EXCLUDED.spec_id,
                    state = EXCLUDED.state
            """), {
                "exam_participant_id": exam_participant_id,
                "exam_id": exam_id,
                "participant_id": participant_id
            })
            print(f"✅ ExamParticipant 생성 완료 (ID: {exam_participant_id})")
            
            # 6. PromptSession 생성 - ended_at을 NULL로 설정 (진행 중인 세션)
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.prompt_sessions (id, exam_id, participant_id, spec_id, started_at, ended_at)
                VALUES (:session_id, :exam_id, :participant_id, 10, NOW(), NULL)
                ON CONFLICT (id) DO UPDATE
                SET exam_id = EXCLUDED.exam_id,
                    participant_id = EXCLUDED.participant_id,
                    spec_id = EXCLUDED.spec_id,
                    started_at = COALESCE(prompt_sessions.started_at, EXCLUDED.started_at),
                    ended_at = NULL  -- 진행 중인 세션으로 설정
            """), {
                "session_id": session_id,
                "exam_id": exam_id,
                "participant_id": participant_id
            })
            print(f"✅ PromptSession 생성 완료 (ID: {session_id})")
            
            # 7. Submission 생성 - 제출 전 상태
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.submissions (id, exam_id, participant_id, spec_id, lang, code_inline, status)
                VALUES (:submission_id, :exam_id, :participant_id, 10, 'python3.11', '', 'QUEUED')
                ON CONFLICT (id) DO UPDATE
                SET exam_id = EXCLUDED.exam_id,
                    participant_id = EXCLUDED.participant_id,
                    spec_id = EXCLUDED.spec_id,
                    lang = EXCLUDED.lang,
                    status = EXCLUDED.status
            """), {
                "submission_id": submission_id,
                "exam_id": exam_id,
                "participant_id": participant_id
            })
            print(f"✅ Submission 생성 완료 (ID: {submission_id})")
            
            await db.commit()
            print("\n✅ 모든 테스트 데이터 생성 완료!")
            print("\n생성된 데이터:")
            print(f"  - Exam: ID={exam_id}")
            print(f"  - Participant: ID={participant_id}")
            print("  - Problem: ID=1 (외판원 순회)")
            print("  - ProblemSpec: spec_id=10")
            print(f"  - ExamParticipant: ID={exam_participant_id} (exam_id={exam_id}, participant_id={participant_id}, spec_id=10)")
            print(f"  - PromptSession: ID={session_id}")
            print(f"  - Submission: ID={submission_id}")
            
            # 생성된 ID를 파일에 저장 (다른 스크립트에서 사용)
            import json
            test_ids = {
                "session_id": session_id,
                "submission_id": submission_id,
                "exam_participant_id": exam_participant_id,
                "exam_id": exam_id,
                "participant_id": participant_id
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

