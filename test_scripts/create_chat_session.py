"""
채팅 세션 생성 스크립트

[사용법]
uv run python test_scripts/create_chat_session.py

[기능]
- 현재 DB 상태 확인
- session_id 1로 채팅 세션 생성
- API 테스트에 필요한 모든 데이터 준비
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


async def create_chat_session():
    """채팅 세션 생성 (session_id=1)"""
    print("=" * 80)
    print("채팅 세션 생성")
    print("=" * 80)
    
    # DB 초기화
    await init_db()
    print("✅ DB 연결 완료")
    
    async with get_db_context() as db:
        try:
            # 1. 현재 DB 상태 확인
            print("\n📋 현재 DB 상태 확인")
            print("-" * 80)
            
            # Admin 확인
            admin_result = await db.execute(text("""
                SELECT id, admin_number, email, role, is_active
                FROM ai_vibe_coding_test.admins 
                WHERE id = 1
            """))
            admin = admin_result.fetchone()
            if admin:
                print(f"✅ Admin: ID={admin.id}, {admin.admin_number}")
            else:
                print("⚠️  Admin (ID: 1) 없음 - 생성 필요")
            
            # Exam 확인
            exam_result = await db.execute(text("""
                SELECT id, title, state
                FROM ai_vibe_coding_test.exams 
                WHERE id = 1
            """))
            exam = exam_result.fetchone()
            if exam:
                print(f"✅ Exam: ID={exam.id}, {exam.title}")
            else:
                print("⚠️  Exam (ID: 1) 없음 - 생성 필요")
            
            # Participant 확인
            participant_result = await db.execute(text("""
                SELECT id, name
                FROM ai_vibe_coding_test.participants 
                WHERE id = 1
            """))
            participant = participant_result.fetchone()
            if participant:
                print(f"✅ Participant: ID={participant.id}, {participant.name}")
            else:
                print("⚠️  Participant (ID: 1) 없음 - 생성 필요")
            
            # Problem 확인 (외판원 순회 문제)
            problem_result = await db.execute(text("""
                SELECT id, title, difficulty, status, current_spec_id
                FROM ai_vibe_coding_test.problems 
                WHERE id = 1
            """))
            problem = problem_result.fetchone()
            if problem:
                print(f"✅ Problem: ID={problem.id}, {problem.title}, current_spec_id={problem.current_spec_id}")
                spec_id = problem.current_spec_id
                
                # current_spec_id가 없으면 problem_specs에서 찾기
                if not spec_id:
                    spec_result = await db.execute(text("""
                        SELECT spec_id FROM ai_vibe_coding_test.problem_specs 
                        WHERE problem_id = 1 
                        ORDER BY version ASC 
                        LIMIT 1
                    """))
                    spec_row = spec_result.fetchone()
                    if spec_row:
                        spec_id = spec_row.spec_id
                    else:
                        print("⚠️  Problem (ID: 1)에 대한 ProblemSpec이 없습니다.")
                        spec_id = None
                else:
                    # spec_id 확인
                    spec_check = await db.execute(text("""
                        SELECT spec_id, problem_id, version
                        FROM ai_vibe_coding_test.problem_specs 
                        WHERE spec_id = :spec_id
                    """), {"spec_id": spec_id})
                    spec = spec_check.fetchone()
                    if spec:
                        print(f"✅ ProblemSpec: spec_id={spec.spec_id}, version={spec.version}")
                    else:
                        print(f"⚠️  ProblemSpec (spec_id: {spec_id}) 없음")
                        spec_id = None
            else:
                print("⚠️  Problem (ID: 1) 없음 - insert_tsp_problem.py 실행 필요")
                spec_id = None
            
            # ExamParticipant 확인
            ep_result = await db.execute(text("""
                SELECT id, exam_id, participant_id, spec_id, state
                FROM ai_vibe_coding_test.exam_participants 
                WHERE exam_id = 1 AND participant_id = 1
            """))
            ep = ep_result.fetchone()
            if ep:
                print(f"✅ ExamParticipant: ID={ep.id}, exam_id={ep.exam_id}, participant_id={ep.participant_id}")
                exam_participant_id = ep.id
            else:
                print("⚠️  ExamParticipant 없음 - 생성 필요")
                exam_participant_id = None
            
            # PromptSession 확인
            session_result = await db.execute(text("""
                SELECT id, exam_id, participant_id, spec_id, total_tokens, started_at, ended_at
                FROM ai_vibe_coding_test.prompt_sessions 
                WHERE id = 1
            """))
            session = session_result.fetchone()
            if session:
                print(f"✅ PromptSession: ID={session.id}, ended_at={session.ended_at}")
            else:
                print("⚠️  PromptSession (ID: 1) 없음 - 생성 필요")
            
            print("-" * 80)
            
            # 2. 필요한 데이터가 없으면 생성
            if not admin:
                print("\n📝 Admin 생성 중...")
                # 컬럼 이름 확인
                columns_result = await db.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns 
                    WHERE table_schema = 'ai_vibe_coding_test' 
                    AND table_name = 'admins'
                """))
                columns = [row.column_name for row in columns_result.fetchall()]
                
                fa_column = None
                for col in ['is_2fa_enabled', 'is2fa_enabled', 'is_2fa', 'is2fa']:
                    if col in columns:
                        fa_column = col
                        break
                
                if fa_column:
                    await db.execute(text(f"""
                        INSERT INTO ai_vibe_coding_test.admins 
                        (id, admin_number, email, password_hash, role, is_active, {fa_column})
                        VALUES (1, 'TEST_ADMIN_001', 'test@example.com', 'test_hash', 'ADMIN', true, false)
                        ON CONFLICT (id) DO UPDATE
                        SET admin_number = EXCLUDED.admin_number,
                            email = EXCLUDED.email,
                            role = EXCLUDED.role,
                            is_active = EXCLUDED.is_active
                    """))
                else:
                    await db.execute(text("""
                        INSERT INTO ai_vibe_coding_test.admins 
                        (id, admin_number, email, password_hash, role, is_active)
                        VALUES (1, 'TEST_ADMIN_001', 'test@example.com', 'test_hash', 'ADMIN', true)
                        ON CONFLICT (id) DO UPDATE
                        SET admin_number = EXCLUDED.admin_number,
                            email = EXCLUDED.email,
                            role = EXCLUDED.role,
                            is_active = EXCLUDED.is_active
                    """))
                print("✅ Admin 생성 완료")
            
            if not exam:
                print("\n📝 Exam 생성 중...")
                # exams 테이블의 컬럼 확인
                exam_columns_result = await db.execute(text("""
                    SELECT column_name, is_nullable
                    FROM information_schema.columns 
                    WHERE table_schema = 'ai_vibe_coding_test' 
                    AND table_name = 'exams'
                    AND column_name IN ('starts_at', 'ends_at')
                """))
                exam_columns = {row.column_name: row.is_nullable == 'YES' for row in exam_columns_result.fetchall()}
                
                # starts_at, ends_at가 필수인지 확인하고 적절히 처리
                starts_at_required = not exam_columns.get('starts_at', True)
                ends_at_required = not exam_columns.get('ends_at', True)
                
                if starts_at_required or ends_at_required:
                    # 필수인 경우 현재 시간과 미래 시간 설정
                    await db.execute(text("""
                        INSERT INTO ai_vibe_coding_test.exams 
                        (id, title, state, version, created_by, starts_at, ends_at)
                        VALUES (1, '테스트 시험', 'RUNNING', 1, 1, NOW(), NOW() + INTERVAL '7 days')
                        ON CONFLICT (id) DO UPDATE
                        SET title = EXCLUDED.title, state = EXCLUDED.state
                    """))
                else:
                    # 선택적인 경우
                    await db.execute(text("""
                        INSERT INTO ai_vibe_coding_test.exams (id, title, state, version, created_by)
                        VALUES (1, '테스트 시험', 'RUNNING', 1, 1)
                        ON CONFLICT (id) DO UPDATE
                        SET title = EXCLUDED.title, state = EXCLUDED.state
                    """))
                print("✅ Exam 생성 완료")
            
            if not participant:
                print("\n📝 Participant 생성 중...")
                await db.execute(text("""
                    INSERT INTO ai_vibe_coding_test.participants (id, name)
                    VALUES (1, '테스트 참가자')
                    ON CONFLICT (id) DO UPDATE
                    SET name = EXCLUDED.name
                """))
                print("✅ Participant 생성 완료")
            
            if not problem or not spec_id:
                print("\n❌ Problem 또는 ProblemSpec이 없습니다.")
                print("   다음 명령을 먼저 실행하세요:")
                print("   uv run python scripts/insert_tsp_problem.py")
                return
            
            if not ep:
                print(f"\n📝 ExamParticipant 생성 중... (spec_id: {spec_id})")
                await db.execute(text("""
                    INSERT INTO ai_vibe_coding_test.exam_participants 
                    (exam_id, participant_id, spec_id, state, token_limit, token_used)
                    VALUES (1, 1, :spec_id, 'REGISTERED', 20000, 0)
                    ON CONFLICT (exam_id, participant_id) DO UPDATE
                    SET spec_id = EXCLUDED.spec_id, 
                        state = EXCLUDED.state,
                        token_limit = EXCLUDED.token_limit
                """), {"spec_id": spec_id})
                # ExamParticipant ID 조회
                ep_result = await db.execute(text("""
                    SELECT id FROM ai_vibe_coding_test.exam_participants
                    WHERE exam_id = 1 AND participant_id = 1
                """))
                ep_row = ep_result.fetchone()
                exam_participant_id = ep_row.id if ep_row else None
                print(f"✅ ExamParticipant 생성 완료 (ID: {exam_participant_id})")
            
            # 3. PromptSession 생성 (session_id=1)
            print(f"\n📝 PromptSession 생성 중... (spec_id: {spec_id})")
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.prompt_sessions 
                (id, exam_id, participant_id, spec_id, total_tokens, started_at, ended_at)
                VALUES (1, 1, 1, :spec_id, 0, NOW(), NULL)
                ON CONFLICT (id) DO UPDATE
                SET exam_id = EXCLUDED.exam_id,
                    participant_id = EXCLUDED.participant_id,
                    spec_id = EXCLUDED.spec_id,
                    ended_at = NULL
            """), {"spec_id": spec_id})
            print("✅ PromptSession 생성 완료 (ID: 1)")
            
            # 4. 최종 확인 및 정보 출력
            print("\n" + "=" * 80)
            print("✅ 채팅 세션 생성 완료!")
            print("=" * 80)
            
            # 최종 정보 조회
            final_result = await db.execute(text("""
                SELECT 
                    ps.id as session_id,
                    ps.exam_id,
                    ps.participant_id,
                    ps.spec_id,
                    ep.id as exam_participant_id,
                    pr.id as problem_id,
                    pspec.version as spec_version
                FROM ai_vibe_coding_test.prompt_sessions ps
                JOIN ai_vibe_coding_test.exam_participants ep 
                    ON ps.exam_id = ep.exam_id AND ps.participant_id = ep.participant_id
                JOIN ai_vibe_coding_test.problem_specs pspec ON ps.spec_id = pspec.spec_id
                JOIN ai_vibe_coding_test.problems pr ON pspec.problem_id = pr.id
                WHERE ps.id = 1
            """))
            final_row = final_result.fetchone()
            
            if final_row:
                print(f"\n📋 API 테스트 정보:")
                print(f"   - sessionId: {final_row.session_id}")
                print(f"   - examParticipantId: {final_row.exam_participant_id}")
                print(f"   - problemId: {final_row.problem_id}")
                print(f"   - specVersion: {final_row.spec_version}")
                print(f"   - participantId: {final_row.participant_id}")
                
                # JSON 파일로 저장
                test_info = {
                    "sessionId": final_row.session_id,
                    "examParticipantId": final_row.exam_participant_id,
                    "problemId": final_row.problem_id,
                    "specVersion": final_row.spec_version,
                    "participantId": final_row.participant_id,
                    "examId": final_row.exam_id,
                    "specId": final_row.spec_id
                }
                
                test_file = project_root / "test_chat_session.json"
                with open(test_file, "w", encoding="utf-8") as f:
                    json.dump(test_info, f, indent=2, ensure_ascii=False)
                print(f"\n💾 테스트 정보가 {test_file}에 저장되었습니다.")
                
                print(f"\n📄 API 호출 예시:")
                print(f"   POST /api/chat/messages")
                print(f"   {{")
                print(f"     \"sessionId\": {final_row.session_id},")
                print(f"     \"examParticipantId\": {final_row.exam_participant_id},")
                print(f"     \"turnId\": 1,")
                print(f"     \"role\": \"USER\",")
                print(f"     \"content\": \"이 문제를 해결하는 방법을 알려주세요.\",")
                print(f"     \"context\": {{")
                print(f"       \"problemId\": {final_row.problem_id},")
                print(f"       \"specVersion\": {final_row.spec_version}")
                print(f"     }}")
                print(f"   }}")
            else:
                print("❌ 세션 정보를 조회할 수 없습니다.")
            
        except Exception as e:
            print(f"\n❌ 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(create_chat_session())

