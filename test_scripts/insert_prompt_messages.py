"""
prompt_messages 테이블에 테스트 메시지 데이터 삽입

[사용법]
uv run python test_scripts/insert_prompt_messages.py

[필요 조건]
- prompt_sessions 테이블에 세션이 존재해야 함 (FK 제약 조건)
- 기존 세션 ID를 사용하거나, 새 세션을 먼저 생성해야 함

[생성되는 데이터]
- prompt_messages: 지정된 세션에 메시지 추가
"""

import asyncio
import sys
import json
from pathlib import Path
from typing import List, Dict, Any

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.infrastructure.persistence.session import get_db_context, init_db


async def insert_prompt_messages(
    session_id: int,
    messages: List[Dict[str, Any]]
):
    """
    prompt_messages 테이블에 메시지 삽입
    
    Args:
        session_id: prompt_sessions 테이블의 세션 ID
        messages: 삽입할 메시지 리스트
            [
                {
                    "turn": 1,
                    "role": "USER",  # 또는 "AI"
                    "content": "메시지 내용",
                    "token_count": 10,  # 선택적
                    "meta": {}  # 선택적
                },
                ...
            ]
    """
    print("=" * 80)
    print("prompt_messages 테이블에 메시지 삽입")
    print("=" * 80)
    
    # DB 초기화
    await init_db()
    print("✅ DB 연결 완료")
    
    async with get_db_context() as db:
        try:
            # 1. 세션 존재 확인
            session_check = await db.execute(
                text("""
                    SELECT id, exam_id, participant_id, spec_id, started_at, ended_at
                    FROM ai_vibe_coding_test.prompt_sessions
                    WHERE id = :session_id
                """),
                {"session_id": session_id}
            )
            session_row = session_check.fetchone()
            
            if not session_row:
                raise ValueError(f"❌ 세션 ID {session_id}가 존재하지 않습니다. 먼저 세션을 생성하세요.")
            
            print(f"\n✅ 세션 확인 완료:")
            print(f"   - Session ID: {session_row.id}")
            print(f"   - Exam ID: {session_row.exam_id}")
            print(f"   - Participant ID: {session_row.participant_id}")
            print(f"   - Spec ID: {session_row.spec_id}")
            print(f"   - Started At: {session_row.started_at}")
            print(f"   - Ended At: {session_row.ended_at}")
            
            # 2. 기존 메시지 확인 (turn 중복 방지)
            existing_turns = await db.execute(
                text("""
                    SELECT turn FROM ai_vibe_coding_test.prompt_messages
                    WHERE session_id = :session_id
                """),
                {"session_id": session_id}
            )
            existing_turn_set = {row.turn for row in existing_turns.fetchall()}
            
            if existing_turn_set:
                print(f"\n⚠️  기존 메시지가 있습니다 (turn: {sorted(existing_turn_set)})")
                print("   중복된 turn은 건너뜁니다.")
            
            # 3. 메시지 삽입
            inserted_count = 0
            skipped_count = 0
            
            for msg in messages:
                turn = msg["turn"]
                role = msg["role"].upper()  # 'USER' 또는 'AI'
                content = msg["content"]
                token_count = msg.get("token_count", 0)
                meta = msg.get("meta", {})
                
                # turn 중복 체크
                if turn in existing_turn_set:
                    print(f"   ⏭️  Turn {turn} 건너뜀 (이미 존재)")
                    skipped_count += 1
                    continue
                
                # role 유효성 검사
                if role not in ["USER", "AI"]:
                    print(f"   ❌ Turn {turn}: 잘못된 role '{role}' (USER 또는 AI만 가능)")
                    skipped_count += 1
                    continue
                
                # 메시지 삽입
                await db.execute(
                    text("""
                        INSERT INTO ai_vibe_coding_test.prompt_messages
                        (session_id, turn, role, content, token_count, meta)
                        VALUES (:session_id, :turn, CAST(:role AS ai_vibe_coding_test.prompt_role_enum), :content, :token_count, CAST(:meta AS jsonb))
                        ON CONFLICT (session_id, turn) DO NOTHING
                    """),
                    {
                        "session_id": session_id,
                        "turn": turn,
                        "role": role,
                        "content": content,
                        "token_count": token_count,
                        "meta": json.dumps(meta) if meta else "{}"
                    }
                )
                
                print(f"   ✅ Turn {turn} 삽입 완료 ({role}): {content[:50]}...")
                inserted_count += 1
            
            # 커밋
            await db.commit()
            
            print("\n" + "=" * 80)
            print(f"✅ 메시지 삽입 완료!")
            print(f"   - 삽입된 메시지: {inserted_count}개")
            print(f"   - 건너뛴 메시지: {skipped_count}개")
            print("=" * 80)
            
            # 4. 삽입된 메시지 확인
            result = await db.execute(
                text("""
                    SELECT id, turn, role, content, token_count, created_at
                    FROM ai_vibe_coding_test.prompt_messages
                    WHERE session_id = :session_id
                    ORDER BY turn
                """),
                {"session_id": session_id}
            )
            messages_list = result.fetchall()
            
            print(f"\n📋 세션 {session_id}의 모든 메시지 ({len(messages_list)}개):")
            for msg in messages_list:
                print(f"   Turn {msg.turn} [{msg.role}]: {msg.content[:80]}...")
            
        except Exception as e:
            await db.rollback()
            print(f"\n❌ 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
            raise


async def main():
    """기본 테스트 메시지 삽입 예시"""
    
    # 기존 세션 ID 사용 (test_tsp_ids.json에서 가져오거나 직접 지정)
    session_id = 1  # 기본값: 기존 세션 ID
    
    # 삽입할 메시지 리스트
    messages = [
        {
            "turn": 1,
            "role": "USER",
            "content": "외판원 순회 문제를 풀고 싶어요. 어떻게 시작해야 할까요?",
            "token_count": 20,
            "meta": {}
        },
        {
            "turn": 2,
            "role": "AI",
            "content": "외판원 순회 문제는 여러 도시를 한 번씩만 방문하고 시작점으로 돌아오는 최단 경로를 찾는 문제입니다. 동적 계획법이나 백트래킹을 사용할 수 있습니다.",
            "token_count": 50,
            "meta": {}
        },
        {
            "turn": 3,
            "role": "USER",
            "content": "동적 계획법으로 풀어보고 싶어요. 힌트를 주실 수 있나요?",
            "token_count": 25,
            "meta": {}
        },
        {
            "turn": 4,
            "role": "AI",
            "content": "동적 계획법을 사용하려면, 방문한 도시 집합과 현재 위치를 상태로 사용하는 점화식을 세울 수 있습니다. 비트마스킹을 활용하면 집합을 효율적으로 표현할 수 있습니다.",
            "token_count": 60,
            "meta": {}
        }
    ]
    
    await insert_prompt_messages(session_id, messages)


if __name__ == "__main__":
    asyncio.run(main())

