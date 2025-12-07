"""
웹 API 테스트를 위한 테스트 데이터 준비 스크립트

[사용법]
uv run python test_scripts/setup_web_test_data.py

[생성되는 데이터]
- Exam (시험): ID=1
- Participant (참가자/User): ID=1
- Problem (문제): ID=1
- ProblemSpec (문제 스펙): spec_id=10
- ExamParticipant (시험 참가자 연결): exam_id=1, participant_id=1, spec_id=10
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.infrastructure.persistence.session import get_db_context, init_db


async def setup_test_data():
    """웹 테스트를 위한 기본 데이터 생성"""
    print("=" * 80)
    print("웹 API 테스트 데이터 준비")
    print("=" * 80)
    
    # DB 초기화
    await init_db()
    print("✅ DB 연결 완료")
    
    async with get_db_context() as db:
        try:
            # 1. Exam 생성
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.exams (id, title, state, version)
                VALUES (1, '웹 테스트 시험', 'WAITING', 1)
                ON CONFLICT (id) DO UPDATE
                SET title = EXCLUDED.title, state = EXCLUDED.state
            """))
            print("✅ Exam 생성 완료 (ID: 1)")
            
            # 2. Participant 생성
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.participants (id, name)
                VALUES 
                    (1, '웹 테스트 참가자 1'),
                    (100, '웹 테스트 참가자 100')
                ON CONFLICT (id) DO UPDATE
                SET name = EXCLUDED.name
            """))
            print("✅ Participant 생성 완료 (ID: 1, 100)")
            
            # 3. Problem 생성
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.problems (id, title, difficulty, status)
                VALUES (1, '피보나치 수열 계산', 'MEDIUM', 'PUBLISHED')
                ON CONFLICT (id) DO UPDATE
                SET title = EXCLUDED.title, difficulty = EXCLUDED.difficulty, status = EXCLUDED.status
            """))
            print("✅ Problem 생성 완료 (ID: 1)")
            
            # 4. ProblemSpec 생성
            problem_spec_content = """
# 피보나치 수열 계산 문제

## 문제 설명
피보나치 수열의 n번째 항을 계산하는 함수를 작성하세요.

## 제약 조건
- n은 0 이상의 정수입니다.
- 재귀 또는 반복 방식 모두 가능합니다.

## 예시
- fibonacci(0) = 0
- fibonacci(1) = 1
- fibonacci(2) = 1
- fibonacci(3) = 2
- fibonacci(4) = 3
"""
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.problem_specs (spec_id, problem_id, version, content_md)
                VALUES (10, 1, 1, :content)
                ON CONFLICT (spec_id) DO UPDATE
                SET content_md = EXCLUDED.content_md
            """), {"content": problem_spec_content})
            print("✅ ProblemSpec 생성 완료 (spec_id: 10)")
            
            # 5. ExamParticipant 생성 (중요!)
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.exam_participants 
                (exam_id, participant_id, spec_id, state, token_limit, token_used)
                VALUES 
                    (1, 1, 10, 'REGISTERED', 20000, 0),
                    (1, 100, 10, 'REGISTERED', 20000, 0)
                ON CONFLICT (exam_id, participant_id) DO UPDATE
                SET spec_id = EXCLUDED.spec_id, state = EXCLUDED.state
            """))
            print("✅ ExamParticipant 생성 완료 (exam_id=1, participant_id=1,100, spec_id=10)")
            
            # 6. PromptSession 생성 (테스트용 세션)
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.prompt_sessions 
                (id, exam_id, participant_id, spec_id, total_tokens, started_at)
                VALUES (1, 1, 1, 10, 0, NOW())
                ON CONFLICT (id) DO UPDATE
                SET exam_id = EXCLUDED.exam_id,
                    participant_id = EXCLUDED.participant_id,
                    spec_id = EXCLUDED.spec_id
            """))
            print("✅ PromptSession 생성 완료 (id=1, exam_id=1, participant_id=1, spec_id=10)")
            
            # 확인
            print("\n" + "=" * 80)
            print("생성된 데이터 확인")
            print("=" * 80)
            
            result = await db.execute(text("""
                SELECT 
                    ep.id as exam_participant_id,
                    ep.exam_id,
                    ep.participant_id,
                    ep.spec_id,
                    ep.state,
                    e.title as exam_title,
                    p.name as participant_name,
                    pr.title as problem_title
                FROM ai_vibe_coding_test.exam_participants ep
                JOIN ai_vibe_coding_test.exams e ON ep.exam_id = e.id
                JOIN ai_vibe_coding_test.participants p ON ep.participant_id = p.id
                JOIN ai_vibe_coding_test.problem_specs ps ON ep.spec_id = ps.spec_id
                JOIN ai_vibe_coding_test.problems pr ON ps.problem_id = pr.id
                WHERE ep.exam_id = 1 AND ep.participant_id = 1
            """))
            row = result.fetchone()
            
            if row:
                print(f"✅ ExamParticipant ID: {row.exam_participant_id} (API에서 examParticipantId로 사용)")
                print(f"✅ Exam: {row.exam_title} (ID: {row.exam_id})")
                print(f"✅ Participant: {row.participant_name} (ID: {row.participant_id})")
                print(f"✅ Problem: {row.problem_title} (Spec ID: {row.spec_id})")
                print(f"✅ State: {row.state}")
            
            # 세션 확인
            session_result = await db.execute(text("""
                SELECT 
                    ps.id,
                    ps.exam_id,
                    ps.participant_id,
                    ps.spec_id,
                    ps.total_tokens,
                    ps.started_at
                FROM ai_vibe_coding_test.prompt_sessions ps
                WHERE ps.id = 1
            """))
            session_row = session_result.fetchone()
            
            if session_row:
                print(f"\n✅ Session: ID={session_row.id}, exam_id={session_row.exam_id}, participant_id={session_row.participant_id}, spec_id={session_row.spec_id}")
                print(f"   - API 테스트 시 sessionId={session_row.id}, examParticipantId={row.exam_participant_id} 사용")
            
            print("\n" + "=" * 80)
            print("✅ 테스트 데이터 준비 완료!")
            print("=" * 80)
            print("\n다음 단계:")
            print("1. 서버 실행: uv run python scripts/run_dev.py")
            print("2. API 문서 확인: http://localhost:8000/docs")
            print("3. 테스트 시작: docs/Web_API_Test_Guide.md 참고")
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(setup_test_data())

