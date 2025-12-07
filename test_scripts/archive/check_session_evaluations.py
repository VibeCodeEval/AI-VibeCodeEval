"""
Session의 평가 결과 확인
"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.infrastructure.persistence.session import get_db_context, init_db


async def check_session_evaluations(session_id: int):
    """Session의 평가 결과 확인"""
    await init_db()
    
    async with get_db_context() as db:
        print("=" * 80)
        print(f"Session {session_id}의 평가 결과 확인")
        print("=" * 80)
        
        # Turn Evaluations 확인
        print("\n[1] Turn Evaluations (TURN_EVAL)")
        result = await db.execute(text("""
            SELECT id, session_id, turn, evaluation_type, details, created_at
            FROM ai_vibe_coding_test.prompt_evaluations
            WHERE session_id = :session_id AND evaluation_type = 'TURN_EVAL'
            ORDER BY turn
        """), {"session_id": session_id})
        turn_evals = result.fetchall()
        
        if turn_evals:
            print(f"✅ {len(turn_evals)}개 Turn Evaluation 발견:\n")
            for eval_row in turn_evals:
                print(f"  ID: {eval_row[0]}, Turn: {eval_row[2]}")
                if isinstance(eval_row[4], dict):
                    score = eval_row[4].get('score', 'N/A')
                    intent = eval_row[4].get('intent', 'N/A')
                    print(f"    Score: {score}, Intent: {intent}")
                print(f"    Created: {eval_row[5]}")
                print()
        else:
            print("❌ Turn Evaluations 없음")
        
        # Holistic Flow Evaluation 확인
        print("\n[2] Holistic Flow Evaluation (HOLISTIC_FLOW)")
        result = await db.execute(text("""
            SELECT id, session_id, turn, evaluation_type, details, created_at
            FROM ai_vibe_coding_test.prompt_evaluations
            WHERE session_id = :session_id AND evaluation_type = 'HOLISTIC_FLOW'
        """), {"session_id": session_id})
        holistic = result.fetchone()
        
        if holistic:
            print("✅ Holistic Flow Evaluation 발견:\n")
            print(f"  ID: {holistic[0]}, Turn: {holistic[2]}")
            if isinstance(holistic[4], dict):
                score = holistic[4].get('score', 'N/A')
                print(f"    Score: {score}")
            print(f"    Created: {holistic[5]}")
        else:
            print("❌ Holistic Flow Evaluation 없음")
        
        # 최근 생성된 Submission 확인 (해당 세션의 exam_id, participant_id로)
        print("\n[3] 최근 생성된 Submission 확인")
        result = await db.execute(text("""
            SELECT s.id, s.exam_id, s.participant_id, s.status, 
                   LENGTH(s.code_inline) as code_len, s.created_at,
                   sc.total_score, sc.prompt_score, sc.perf_score, sc.correctness_score
            FROM ai_vibe_coding_test.submissions s
            LEFT JOIN ai_vibe_coding_test.scores sc ON s.id = sc.submission_id
            WHERE s.exam_id = (SELECT exam_id FROM ai_vibe_coding_test.prompt_sessions WHERE id = :session_id)
              AND s.participant_id = (SELECT participant_id FROM ai_vibe_coding_test.prompt_sessions WHERE id = :session_id)
            ORDER BY s.created_at DESC
            LIMIT 3
        """), {"session_id": session_id})
        submissions = result.fetchall()
        
        if submissions:
            print(f"✅ {len(submissions)}개 Submission 발견:\n")
            for sub in submissions:
                print(f"  Submission ID: {sub[0]}")
                print(f"    Status: {sub[3]}, Code 길이: {sub[4]} 문자")
                if sub[6] is not None:
                    print(f"    ✅ Score 존재:")
                    print(f"       Total: {sub[6]}, Prompt: {sub[7]}, Perf: {sub[8]}, Correct: {sub[9]}")
                else:
                    print(f"    ⏳ Score 없음")
                print(f"    Created: {sub[5]}")
                print()
        else:
            print("❌ Submission 없음")


if __name__ == "__main__":
    import json
    # test_ids.json에서 session_id 읽기
    test_ids_file = project_root / "test_ids.json"
    if test_ids_file.exists():
        with open(test_ids_file, "r", encoding="utf-8") as f:
            test_ids = json.load(f)
        session_id = test_ids.get("session_id", 1003)
    else:
        session_id = 1003
    
    asyncio.run(check_session_evaluations(session_id))

