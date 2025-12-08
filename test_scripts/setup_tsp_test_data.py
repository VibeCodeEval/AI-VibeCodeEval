"""
외판원 순회 문제를 위한 완전한 테스트 데이터 생성
Chat API와 Submit API에 필요한 모든 요소를 생성합니다.

[사용법]
uv run python test_scripts/setup_tsp_test_data.py

[생성되는 데이터]
- Exam (시험): ID=1
- Participant (참가자): ID=1, 2
- Problem (문제): ID=1 (외판원 순회) - 이미 존재하면 확인만
- ProblemSpec (문제 스펙): spec_id=10 (외판원 순회) - 이미 존재하면 확인만
- ExamParticipant (시험 참가자 연결): exam_id=1, participant_id=1,2, spec_id=10
- PromptSession (진행 중인 세션): id=1, exam_id=1, participant_id=1, spec_id=10, ended_at=NULL
- Submission (제출 기록): 선택적 생성
- test_tsp_ids.json: 생성된 ID 정보 저장
"""
import asyncio
import sys
import json
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.infrastructure.persistence.session import get_db_context, init_db


async def setup_tsp_test_data():
    """외판원 순회 문제를 위한 완전한 테스트 데이터 생성"""
    print("=" * 80)
    print("외판원 순회 문제 테스트 데이터 생성")
    print("=" * 80)
    
    # DB 초기화
    await init_db()
    print("✅ DB 연결 완료")
    
    async with get_db_context() as db:
        try:
            # 0. admins 테이블 구조 확인 및 기존 데이터 확인
            # 모든 컬럼 이름 조회
            columns_result = await db.execute(text("""
                SELECT column_name, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_schema = 'ai_vibe_coding_test' 
                AND table_name = 'admins'
                ORDER BY ordinal_position
            """))
            columns = {row.column_name: {'nullable': row.is_nullable == 'YES', 'default': row.column_default} 
                      for row in columns_result.fetchall()}
            
            print(f"📋 admins 테이블 컬럼: {', '.join(columns.keys())}")
            
            # 2FA 관련 컬럼 찾기 (언더스코어 있음/없음 모두 확인)
            fa_column_name = None
            for col_name in ['is_2fa_enabled', 'is2fa_enabled', 'is_2fa', 'is2fa']:
                if col_name in columns:
                    fa_column_name = col_name
                    break
            
            # 기존 데이터 확인
            existing_admin = await db.execute(text("""
                SELECT id, admin_number, email, role, is_active
                FROM ai_vibe_coding_test.admins 
                WHERE id = 1
            """))
            existing_row = existing_admin.fetchone()
            
            # 1. 테스트용 Admin 생성 또는 업데이트 (created_by용)
            if fa_column_name:
                # 2FA 컬럼이 있는 경우
                await db.execute(text(f"""
                    INSERT INTO ai_vibe_coding_test.admins (id, admin_number, email, password_hash, role, is_active, {fa_column_name})
                    VALUES (1, 'TEST_ADMIN_001', 'test@example.com', 'test_hash', 'ADMIN', true, false)
                    ON CONFLICT (id) DO UPDATE
                    SET admin_number = EXCLUDED.admin_number,
                        email = EXCLUDED.email,
                        password_hash = EXCLUDED.password_hash,
                        role = EXCLUDED.role,
                        is_active = EXCLUDED.is_active,
                        {fa_column_name} = COALESCE(EXCLUDED.{fa_column_name}, false)
                """))
            else:
                # 2FA 컬럼이 없는 경우
                await db.execute(text("""
                    INSERT INTO ai_vibe_coding_test.admins (id, admin_number, email, password_hash, role, is_active)
                    VALUES (1, 'TEST_ADMIN_001', 'test@example.com', 'test_hash', 'ADMIN', true)
                    ON CONFLICT (id) DO UPDATE
                    SET admin_number = EXCLUDED.admin_number,
                        email = EXCLUDED.email,
                        password_hash = EXCLUDED.password_hash,
                        role = EXCLUDED.role,
                        is_active = EXCLUDED.is_active
                """))
            
            if existing_row:
                print(f"✅ Admin 업데이트 완료 (ID: 1, 기존: {existing_row.admin_number})")
            else:
                print("✅ Admin 생성 완료 (ID: 1)")
            
            # 2. Exam 생성 (FK: created_by → admins.id)
            # Admin이 존재하는지 확인
            admin_check = await db.execute(text("""
                SELECT id FROM ai_vibe_coding_test.admins WHERE id = 1
            """))
            if admin_check.fetchone() is None:
                raise Exception("Admin (ID: 1)이 존재하지 않습니다. Admin을 먼저 생성하세요.")
            
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.exams (id, title, state, version, created_by)
                VALUES (1, '외판원 순회 테스트 시험', 'RUNNING', 1, 1)
                ON CONFLICT (id) DO UPDATE
                SET title = EXCLUDED.title, state = EXCLUDED.state, created_by = EXCLUDED.created_by
            """))
            print("✅ Exam 생성 완료 (ID: 1, Title: 외판원 순회 테스트 시험)")
            
            # 3. Participant 생성 (FK 없음 - 독립적)
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.participants (id, name)
                VALUES 
                    (1, '외판원 테스트 참가자 1'),
                    (2, '외판원 테스트 참가자 2')
                ON CONFLICT (id) DO UPDATE
                SET name = EXCLUDED.name
            """))
            print("✅ Participant 생성 완료 (ID: 1, 2)")
            
            # 3. Problem 확인 (외판원 순회 문제가 이미 DB에 있는지 확인)
            problem_result = await db.execute(text("""
                SELECT id, title, difficulty, status, current_spec_id
                FROM ai_vibe_coding_test.problems 
                WHERE id = 1
            """))
            problem_row = problem_result.fetchone()
            
            if problem_row:
                print(f"✅ Problem 확인 완료 (ID: 1, Title: {problem_row.title}, Difficulty: {problem_row.difficulty})")
                if problem_row.current_spec_id:
                    print(f"   - current_spec_id: {problem_row.current_spec_id}")
            else:
                print("⚠️  Problem (ID: 1)이 없습니다. 다음 명령을 먼저 실행하세요:")
                print("   uv run python scripts/insert_tsp_problem.py")
                raise Exception("Problem (ID: 1)이 없습니다. insert_tsp_problem.py를 먼저 실행하세요.")
            
            # 4. ProblemSpec 확인 (외판원 순회 문제 스펙이 이미 DB에 있는지 확인)
            spec_result = await db.execute(text("""
                SELECT spec_id, problem_id, version, content_md IS NOT NULL as has_content
                FROM ai_vibe_coding_test.problem_specs 
                WHERE spec_id = 10
            """))
            spec_row = spec_result.fetchone()
            
            if spec_row:
                print(f"✅ ProblemSpec 확인 완료 (spec_id: 10, problem_id: {spec_row.problem_id}, version: {spec_row.version})")
                if spec_row.has_content:
                    print("   - content_md: 있음")
                else:
                    print("   - content_md: 없음 (insert_tsp_problem.py 실행 필요)")
            else:
                print("⚠️  ProblemSpec (spec_id: 10)이 없습니다. 다음 명령을 먼저 실행하세요:")
                print("   uv run python scripts/insert_tsp_problem.py")
                raise Exception("ProblemSpec (spec_id: 10)이 없습니다. insert_tsp_problem.py를 먼저 실행하세요.")
            
            # 5. ExamParticipant 생성 (중요! - Chat/Submit API에서 examParticipantId로 사용)
            # FK: exam_id → exams.id, participant_id → participants.id, spec_id → problem_specs.spec_id
            # 모든 FK가 존재하는지 확인
            exam_check = await db.execute(text("""
                SELECT id FROM ai_vibe_coding_test.exams WHERE id = 1
            """))
            if exam_check.fetchone() is None:
                raise Exception("Exam (ID: 1)이 존재하지 않습니다.")
            
            participant_check = await db.execute(text("""
                SELECT id FROM ai_vibe_coding_test.participants WHERE id IN (1, 2)
            """))
            if len(participant_check.fetchall()) < 2:
                raise Exception("Participant (ID: 1 또는 2)가 존재하지 않습니다.")
            
            if spec_row is None:
                raise Exception("ProblemSpec (spec_id: 10)이 존재하지 않습니다.")
            
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.exam_participants 
                (exam_id, participant_id, spec_id, state, token_limit, token_used)
                VALUES 
                    (1, 1, 10, 'REGISTERED', 20000, 0),
                    (1, 2, 10, 'REGISTERED', 20000, 0)
                ON CONFLICT (exam_id, participant_id) DO UPDATE
                SET spec_id = EXCLUDED.spec_id, 
                    state = EXCLUDED.state,
                    token_limit = EXCLUDED.token_limit
            """))
            print("✅ ExamParticipant 생성 완료 (exam_id=1, participant_id=1,2, spec_id=10)")
            
            # ExamParticipant ID 조회 (API에서 사용할 examParticipantId)
            ep_result = await db.execute(text("""
                SELECT id, exam_id, participant_id, spec_id
                FROM ai_vibe_coding_test.exam_participants
                WHERE exam_id = 1 AND participant_id = 1
            """))
            ep_row = ep_result.fetchone()
            exam_participant_id = ep_row.id if ep_row else None
            
            # 6. PromptSession 생성 (테스트용 세션) - ended_at을 NULL로 설정 (진행 중인 세션)
            # FK: (exam_id, participant_id) → exam_participants(exam_id, participant_id), spec_id → problem_specs.spec_id
            # exam_participants가 존재하는지 확인
            ep_check = await db.execute(text("""
                SELECT id FROM ai_vibe_coding_test.exam_participants
                WHERE exam_id = 1 AND participant_id = 1
            """))
            if ep_check.fetchone() is None:
                raise Exception("ExamParticipant (exam_id=1, participant_id=1)이 존재하지 않습니다.")
            
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.prompt_sessions 
                (id, exam_id, participant_id, spec_id, total_tokens, started_at, ended_at)
                VALUES (1, 1, 1, 10, 0, NOW(), NULL)
                ON CONFLICT (id) DO UPDATE
                SET exam_id = EXCLUDED.exam_id,
                    participant_id = EXCLUDED.participant_id,
                    spec_id = EXCLUDED.spec_id,
                    ended_at = NULL  -- 진행 중인 세션으로 설정
            """))
            print("✅ PromptSession 생성 완료 (id=1, exam_id=1, participant_id=1, spec_id=10, ended_at=NULL)")
            
            # 7. Submission 생성 (선택적 - 제출 기록이 필요한 경우)
            # 제출 기록은 실제 제출 시 생성되므로 여기서는 생성하지 않음
            # 필요시 아래 코드를 활성화하여 생성 가능
            
            # 확인
            print("\n" + "=" * 80)
            print("생성된 데이터 확인")
            print("=" * 80)
            
            # ExamParticipant 상세 정보
            result = await db.execute(text("""
                SELECT 
                    ep.id as exam_participant_id,
                    ep.exam_id,
                    ep.participant_id,
                    ep.spec_id,
                    ep.state,
                    ep.token_limit,
                    ep.token_used,
                    e.title as exam_title,
                    e.state as exam_state,
                    p.name as participant_name,
                    pr.title as problem_title,
                    pr.difficulty as problem_difficulty,
                    ps.spec_id,
                    ps.version as spec_version
                FROM ai_vibe_coding_test.exam_participants ep
                JOIN ai_vibe_coding_test.exams e ON ep.exam_id = e.id
                JOIN ai_vibe_coding_test.participants p ON ep.participant_id = p.id
                JOIN ai_vibe_coding_test.problem_specs ps ON ep.spec_id = ps.spec_id
                JOIN ai_vibe_coding_test.problems pr ON ps.problem_id = pr.id
                WHERE ep.exam_id = 1 AND ep.participant_id = 1
            """))
            row = result.fetchone()
            
            if row:
                print(f"\n✅ ExamParticipant 정보:")
                print(f"   - ExamParticipant ID: {row.exam_participant_id} (API에서 examParticipantId로 사용)")
                print(f"   - Exam: {row.exam_title} (ID: {row.exam_id}, State: {row.exam_state})")
                print(f"   - Participant: {row.participant_name} (ID: {row.participant_id})")
                print(f"   - Problem: {row.problem_title} (Difficulty: {row.problem_difficulty})")
                print(f"   - Spec: spec_id={row.spec_id}, version={row.spec_version}")
                print(f"   - State: {row.state}")
                print(f"   - Token: {row.token_used}/{row.token_limit}")
            
            # 세션 확인
            session_result = await db.execute(text("""
                SELECT 
                    ps.id,
                    ps.exam_id,
                    ps.participant_id,
                    ps.spec_id,
                    ps.total_tokens,
                    ps.started_at,
                    ps.ended_at
                FROM ai_vibe_coding_test.prompt_sessions ps
                WHERE ps.id = 1
            """))
            session_row = session_result.fetchone()
            
            if session_row:
                print(f"\n✅ PromptSession 정보:")
                print(f"   - Session ID: {session_row.id}")
                print(f"   - Exam ID: {session_row.exam_id}")
                print(f"   - Participant ID: {session_row.participant_id}")
                print(f"   - Spec ID: {session_row.spec_id}")
                print(f"   - Total Tokens: {session_row.total_tokens}")
                print(f"   - Started At: {session_row.started_at}")
                print(f"   - Ended At: {session_row.ended_at} (NULL이면 진행 중인 세션)")
            
            # API 사용 가이드
            print("\n" + "=" * 80)
            print("✅ 외판원 순회 문제 테스트 데이터 생성 완료!")
            print("=" * 80)
            print("\n📋 API 사용 가이드:")
            print("\n1. Chat API (POST /api/chat/messages):")
            if row and session_row:
                print(f"   - examParticipantId: {row.exam_participant_id}")
                print(f"   - sessionId: {session_row.id} (또는 새로 생성)")
                print(f"   - problemId: 1")
                print(f"   - specVersion: {row.spec_version}")
            
            print("\n2. Submit API (POST /api/session/submit):")
            if row:
                print(f"   - examParticipantId: {row.exam_participant_id}")
                print(f"   - problemId: 1")
                print(f"   - specVersion: {row.spec_version}")
                print(f"   - language: python3.11 (또는 python3.10, python3.9, python3.8)")
                print(f"   - finalCode: 외판원 순회 문제 코드")
            
            print("\n3. 웹 인터페이스 사용:")
            if row and session_row:
                print(f"   - Session ID: {session_row.id}")
                print(f"   - Exam Participant ID: {row.exam_participant_id}")
                print(f"   - Problem ID: 1")
                print(f"   - Spec Version: {row.spec_version}")
            
            print("\n4. 다음 단계:")
            print("   1. 서버 실행: uv run python scripts/run_dev.py")
            print("   2. 웹 인터페이스: http://localhost:8000")
            print("   3. 파라미터 설정에서 위 값들을 입력하고 테스트 시작")
            
            # 8. test_tsp_ids.json 파일 생성
            test_ids = {
                "session_id": session_row.id if session_row else 1,
                "exam_participant_id": row.exam_participant_id if row else None,
                "exam_id": row.exam_id if row else 1,
                "participant_id": row.participant_id if row else 1,
                "problem_id": 1,
                "spec_id": row.spec_id if row else 10,
                "spec_version": row.spec_version if row else 1,
                "submission_id": None  # 제출 시 자동 생성
            }
            
            test_ids_file = project_root / "test_tsp_ids.json"
            with open(test_ids_file, "w", encoding="utf-8") as f:
                json.dump(test_ids, f, indent=2, ensure_ascii=False)
            print(f"\n💾 생성된 ID가 test_tsp_ids.json에 저장되었습니다.")
            print(f"   파일 위치: {test_ids_file}")
            print(f"\n📄 test_tsp_ids.json 내용:")
            print(json.dumps(test_ids, indent=2, ensure_ascii=False))
            
        except Exception as e:
            print(f"\n❌ 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(setup_tsp_test_data())

