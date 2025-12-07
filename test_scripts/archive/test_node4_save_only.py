"""
4번 노드 저장 기능만 테스트하는 스크립트
DB 제약 조건 수정 후 저장이 정상적으로 작동하는지 확인
"""
import asyncio
import json
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.session import get_db_context
from app.application.services.evaluation_storage_service import EvaluationStorageService

# 프로젝트 루트
project_root = Path(__file__).parent


async def test_node4_save():
    """4번 노드 저장 기능 테스트"""
    print("=" * 80)
    print("4번 노드 저장 기능 테스트")
    print("=" * 80)
    
    # test_ids.json에서 세션 ID 읽기
    test_ids_path = project_root / "test_ids.json"
    if not test_ids_path.exists():
        print("❌ test_ids.json 파일이 없습니다. 먼저 setup_submit_test_data.py를 실행하세요.")
        return
    
    with open(test_ids_path, "r", encoding="utf-8") as f:
        test_ids = json.load(f)
    
    session_id = test_ids["session_id"]
    print(f"\n📋 테스트 세션 ID: {session_id}")
    
    # 테스트용 turn_log 데이터 생성
    turn_log = {
        "prompt_evaluation_details": {
            "intent": "HINT_OR_QUERY",
            "score": 35.0,
            "analysis": "평가 완료",
            "rubrics": [
                {
                    "criterion": "프롬프트 명확성",
                    "score": 35.0,
                    "feedback": "평가 완료"
                }
            ],
            "detailed_evaluations": {},
            "detailed_feedback": []
        },
        "comprehensive_reasoning": "테스트용 평가 결과",
        "intent_types": ["HINT_OR_QUERY"],
        "evaluations": {},
        "detailed_feedback": [],
        "turn_score": 35.0,
        "is_guardrail_failed": False,
        "guardrail_message": None,
    }
    
    print(f"\n📝 테스트 데이터:")
    print(f"   - Turn: 1")
    print(f"   - Score: {turn_log['turn_score']}")
    print(f"   - Intent: {turn_log['prompt_evaluation_details']['intent']}")
    
    # DB 연결 및 저장 테스트
    try:
        async with get_db_context() as db:
            # 먼저 테스트용 메시지 생성 (Foreign Key 제약 조건을 위해)
            print(f"\n📝 테스트용 메시지 생성 중...")
            from app.infrastructure.persistence.models.sessions import PromptMessage, PromptRoleEnum
            
            # 기존 메시지 확인
            from sqlalchemy import select
            existing_msg = await db.execute(
                select(PromptMessage).where(
                    PromptMessage.session_id == session_id,
                    PromptMessage.turn == 1
                )
            )
            msg = existing_msg.scalar_one_or_none()
            
            if not msg:
                # 메시지 생성
                test_message = PromptMessage(
                    session_id=session_id,
                    turn=1,
                    role=PromptRoleEnum.USER,
                    content="테스트 메시지",
                    token_count=10
                )
                db.add(test_message)
                await db.flush()
                print(f"✅ 테스트용 메시지 생성 완료")
            else:
                print(f"✅ 기존 메시지 사용 (ID: {msg.id})")
            
            storage_service = EvaluationStorageService(db)
            
            print(f"\n💾 저장 시도 중...")
            result = await storage_service.save_turn_evaluation(
                session_id=session_id,
                turn=1,
                turn_log=turn_log
            )
            
            if result:
                print(f"✅ 저장 성공!")
                print(f"   - Evaluation ID: {result.id}")
                print(f"   - Session ID: {result.session_id}")
                print(f"   - Turn: {result.turn}")
                print(f"   - Evaluation Type: {result.evaluation_type}")
                print(f"   - Score: {result.details.get('score')}")
                
                # 커밋
                await db.commit()
                print(f"\n✅ 커밋 완료!")
                
                # 저장된 데이터 확인
                print(f"\n🔍 저장된 데이터 확인 중...")
                query = text("""
                    SELECT id, session_id, turn, evaluation_type, details->>'score' as score
                    FROM ai_vibe_coding_test.prompt_evaluations
                    WHERE session_id = :session_id AND turn = :turn
                """)
                result_check = await db.execute(query, {"session_id": session_id, "turn": 1})
                row = result_check.fetchone()
                
                if row:
                    print(f"✅ DB에서 확인됨:")
                    print(f"   - ID: {row[0]}")
                    print(f"   - Session ID: {row[1]}")
                    print(f"   - Turn: {row[2]}")
                    print(f"   - Evaluation Type: {row[3]}")
                    print(f"   - Score: {row[4]}")
                else:
                    print(f"❌ DB에서 데이터를 찾을 수 없습니다.")
            else:
                print(f"❌ 저장 실패 (result가 None)")
                await db.rollback()
                
    except Exception as e:
        print(f"\n❌ 오류 발생:")
        print(f"   {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_node4_save())

