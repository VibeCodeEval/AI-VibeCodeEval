"""
채팅 세션 더미 데이터 생성 스크립트

[사용법]
uv run python test_scripts/create_dummy_chat_sessions.py [세션 개수]

[기능]
- 여러 개의 채팅 세션을 생성
- 각 세션마다 필요한 모든 데이터 자동 생성
- API 테스트에 필요한 정보를 JSON 파일로 저장
- 기존 세션이 있어도 계속 추가 생성 가능

[예시]
uv run python test_scripts/create_dummy_chat_sessions.py 5  # 5개 세션 생성
"""
import asyncio
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.infrastructure.persistence.session import get_db_context, init_db


async def ensure_base_data(db) -> int:
    """기본 데이터가 있는지 확인하고 없으면 생성"""
    # Admin 확인 및 생성
    admin_result = await db.execute(text("""
        SELECT id FROM ai_vibe_coding_test.admins WHERE id = 1
    """))
    if not admin_result.fetchone():
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
                ON CONFLICT (id) DO NOTHING
            """))
        else:
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.admins 
                (id, admin_number, email, password_hash, role, is_active)
                VALUES (1, 'TEST_ADMIN_001', 'test@example.com', 'test_hash', 'ADMIN', true)
                ON CONFLICT (id) DO NOTHING
            """))
    
    # Exam 확인 및 생성
    exam_result = await db.execute(text("""
        SELECT id FROM ai_vibe_coding_test.exams WHERE id = 1
    """))
    if not exam_result.fetchone():
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
                VALUES (1, '더미 데이터 테스트 시험', 'RUNNING', 1, 1, NOW(), NOW() + INTERVAL '7 days')
                ON CONFLICT (id) DO NOTHING
            """))
        else:
            # 선택적인 경우
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.exams (id, title, state, version, created_by)
                VALUES (1, '더미 데이터 테스트 시험', 'RUNNING', 1, 1)
                ON CONFLICT (id) DO NOTHING
            """))
    
    # Problem 및 ProblemSpec 확인 (외판원 순회 문제 사용)
    problem_result = await db.execute(text("""
        SELECT id, current_spec_id, title 
        FROM ai_vibe_coding_test.problems 
        WHERE id = 1
    """))
    problem_row = problem_result.fetchone()
    
    if not problem_row:
        raise Exception("Problem (ID: 1)이 없습니다. insert_tsp_problem.py를 먼저 실행하세요.")
    
    # current_spec_id가 있으면 사용, 없으면 problem_specs에서 찾기
    spec_id = problem_row.current_spec_id
    
    if not spec_id:
        # current_spec_id가 없으면 problem_id=1인 첫 번째 spec 찾기
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
            raise Exception("Problem (ID: 1)에 대한 ProblemSpec이 없습니다.")
    
    # spec_id 확인
    spec_check = await db.execute(text("""
        SELECT spec_id FROM ai_vibe_coding_test.problem_specs WHERE spec_id = :spec_id
    """), {"spec_id": spec_id})
    if not spec_check.fetchone():
        raise Exception(f"ProblemSpec (spec_id: {spec_id})이 없습니다.")
    
    print(f"✅ Problem 확인: ID=1, Title={problem_row.title}, current_spec_id={spec_id}")
    
    return spec_id  # spec_id 반환


async def get_next_session_id(db) -> int:
    """다음 사용 가능한 세션 ID 조회"""
    result = await db.execute(text("""
        SELECT COALESCE(MAX(id), 0) + 1 as next_id
        FROM ai_vibe_coding_test.prompt_sessions
    """))
    row = result.fetchone()
    return row.next_id if row else 1


async def get_next_participant_id(db) -> int:
    """다음 사용 가능한 참가자 ID 조회"""
    result = await db.execute(text("""
        SELECT COALESCE(MAX(id), 0) + 1 as next_id
        FROM ai_vibe_coding_test.participants
    """))
    row = result.fetchone()
    return row.next_id if row else 1


async def create_chat_session(
    db,
    session_id: int,
    participant_id: int,
    exam_id: int = 1,
    spec_id: int = 1  # 기본값을 1로 변경 (외판원 순회 문제의 current_spec_id)
) -> Dict[str, Any]:
    """채팅 세션 생성"""
    # 1. Participant 생성
    await db.execute(text("""
        INSERT INTO ai_vibe_coding_test.participants (id, name)
        VALUES (:participant_id, :name)
        ON CONFLICT (id) DO UPDATE
        SET name = EXCLUDED.name
    """), {"participant_id": participant_id, "name": f"테스트 참가자 {participant_id}"})
    
    # 2. ExamParticipant 생성
    await db.execute(text("""
        INSERT INTO ai_vibe_coding_test.exam_participants 
        (exam_id, participant_id, spec_id, state, token_limit, token_used)
        VALUES (:exam_id, :participant_id, :spec_id, 'REGISTERED', 20000, 0)
        ON CONFLICT (exam_id, participant_id) DO UPDATE
        SET spec_id = EXCLUDED.spec_id, 
            state = EXCLUDED.state,
            token_limit = EXCLUDED.token_limit
    """), {
        "exam_id": exam_id,
        "participant_id": participant_id,
        "spec_id": spec_id
    })
    
    # ExamParticipant ID 조회
    ep_result = await db.execute(text("""
        SELECT id FROM ai_vibe_coding_test.exam_participants
        WHERE exam_id = :exam_id AND participant_id = :participant_id
    """), {"exam_id": exam_id, "participant_id": participant_id})
    ep_row = ep_result.fetchone()
    exam_participant_id = ep_row.id if ep_row else None
    
    # 3. PromptSession 생성
    await db.execute(text("""
        INSERT INTO ai_vibe_coding_test.prompt_sessions 
        (id, exam_id, participant_id, spec_id, total_tokens, started_at, ended_at)
        VALUES (:session_id, :exam_id, :participant_id, :spec_id, 0, NOW(), NULL)
        ON CONFLICT (id) DO UPDATE
        SET exam_id = EXCLUDED.exam_id,
            participant_id = EXCLUDED.participant_id,
            spec_id = EXCLUDED.spec_id,
            ended_at = NULL
    """), {
        "session_id": session_id,
        "exam_id": exam_id,
        "participant_id": participant_id,
        "spec_id": spec_id
    })
    
    # 4. 세션 정보 조회
    result = await db.execute(text("""
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
        WHERE ps.id = :session_id
    """), {"session_id": session_id})
    
    row = result.fetchone()
    if row:
        return {
            "sessionId": row.session_id,
            "examParticipantId": row.exam_participant_id,
            "problemId": row.problem_id,
            "specVersion": row.spec_version,
            "participantId": row.participant_id,
            "examId": row.exam_id,
            "specId": row.spec_id
        }
    return None


async def create_dummy_sessions(count: int = 5):
    """더미 채팅 세션 생성"""
    print("=" * 80)
    print(f"채팅 세션 더미 데이터 생성 (개수: {count})")
    print("=" * 80)
    
    # DB 초기화
    await init_db()
    print("✅ DB 연결 완료")
    
    async with get_db_context() as db:
        try:
            # 기본 데이터 확인 및 생성
            print("\n📋 기본 데이터 확인 중...")
            spec_id = await ensure_base_data(db)
            print("✅ 기본 데이터 확인 완료")
            
            # 현재 세션 ID 확인
            start_session_id = await get_next_session_id(db)
            start_participant_id = await get_next_participant_id(db)
            
            print(f"\n📝 세션 생성 시작 (session_id: {start_session_id}부터, spec_id: {spec_id})")
            print("-" * 80)
            
            created_sessions: List[Dict[str, Any]] = []
            
            for i in range(count):
                session_id = start_session_id + i
                participant_id = start_participant_id + i
                
                session_info = await create_chat_session(
                    db, session_id, participant_id, exam_id=1, spec_id=spec_id
                )
                
                if session_info:
                    created_sessions.append(session_info)
                    print(f"✅ 세션 {i+1}/{count}: session_id={session_id}, "
                          f"examParticipantId={session_info['examParticipantId']}")
                else:
                    print(f"❌ 세션 {i+1}/{count}: 생성 실패 (session_id={session_id})")
            
            print("-" * 80)
            print(f"\n✅ 총 {len(created_sessions)}개 세션 생성 완료")
            
            # JSON 파일로 저장
            output_file = project_root / "test_chat_sessions.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(created_sessions, f, indent=2, ensure_ascii=False)
            print(f"\n💾 세션 정보가 {output_file}에 저장되었습니다.")
            
            # API 호출 예시 출력
            if created_sessions:
                print("\n📄 API 호출 예시 (첫 번째 세션):")
                first = created_sessions[0]
                print(f"   POST /api/chat/messages")
                print(f"   {{")
                print(f"     \"sessionId\": {first['sessionId']},")
                print(f"     \"examParticipantId\": {first['examParticipantId']},")
                print(f"     \"turnId\": 1,")
                print(f"     \"role\": \"USER\",")
                print(f"     \"content\": \"이 문제를 해결하는 방법을 알려주세요.\",")
                print(f"     \"context\": {{")
                print(f"       \"problemId\": {first['problemId']},")
                print(f"       \"specVersion\": {first['specVersion']}")
                print(f"     }}")
                print(f"   }}")
                
                print(f"\n📋 생성된 세션 목록:")
                for i, sess in enumerate(created_sessions, 1):
                    print(f"   {i}. sessionId={sess['sessionId']}, "
                          f"examParticipantId={sess['examParticipantId']}, "
                          f"participantId={sess['participantId']}")
            
        except Exception as e:
            print(f"\n❌ 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
            raise


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="채팅 세션 더미 데이터 생성",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  uv run python test_scripts/create_dummy_chat_sessions.py 5
  uv run python test_scripts/create_dummy_chat_sessions.py 10
        """
    )
    parser.add_argument(
        "count",
        type=int,
        nargs="?",
        default=5,
        help="생성할 세션 개수 (기본값: 5)"
    )
    
    args = parser.parse_args()
    
    if args.count < 1:
        print("❌ 세션 개수는 1 이상이어야 합니다.")
        sys.exit(1)
    
    asyncio.run(create_dummy_sessions(args.count))


if __name__ == "__main__":
    main()

