"""
Submit 테스트 결과 확인
test_ids.json에서 자동으로 생성된 ID 사용
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text, select
from app.infrastructure.persistence.session import get_db_context, init_db


async def check_submit_result():
    """Submit 테스트 결과 확인"""
    # test_ids.json에서 ID 읽기
    test_ids_file = project_root / "test_ids.json"
    if test_ids_file.exists():
        with open(test_ids_file, "r", encoding="utf-8") as f:
            test_ids = json.load(f)
        session_id = test_ids.get("session_id", 1000)
        submission_id = test_ids.get("submission_id", 1000)
    else:
        print("⚠️  test_ids.json 파일을 찾을 수 없습니다.")
        print("   기본값 사용: SessionId=1000, SubmissionId=1000")
        session_id = 1000
        submission_id = 1000
    
    print("=" * 80)
    print("Submit 테스트 결과 확인")
    print(f"SessionId: {session_id}, SubmissionId: {submission_id}")
    print("=" * 80)
    
    await init_db()
    
    async with get_db_context() as db:
        try:
            # 1. Submission 상태 확인
            print("\n[1] Submission 상태 확인")
            submission_result = await db.execute(text("""
                SELECT id, exam_id, participant_id, spec_id, lang, status, code_inline, created_at
                FROM ai_vibe_coding_test.submissions
                WHERE id = :submission_id
            """), {"submission_id": submission_id})
            submission = submission_result.fetchone()
            
            if submission:
                print(f"✅ Submission 발견:")
                print(f"   ID: {submission[0]}")
                print(f"   Status: {submission[5]}")
                print(f"   Language: {submission[4]}")
                print(f"   Code 길이: {len(submission[6]) if submission[6] else 0} 문자")
                print(f"   Created: {submission[7]}")
            else:
                print("❌ Submission을 찾을 수 없습니다.")
            
            # 2. Scores 확인
            print("\n[2] Scores 확인")
            scores_result = await db.execute(text("""
                SELECT submission_id, prompt_score, perf_score, correctness_score, 
                       total_score, rubric_json, created_at
                FROM ai_vibe_coding_test.scores
                WHERE submission_id = :submission_id
            """), {"submission_id": submission_id})
            score = scores_result.fetchone()
            
            if score:
                print(f"✅ Score 발견:")
                print(f"   Submission ID: {score[0]}")
                print(f"   Prompt Score: {score[1]}")
                print(f"   Performance Score: {score[2]}")
                print(f"   Correctness Score: {score[3]}")
                print(f"   Total Score: {score[4]}")
                if score[5]:
                    rubric = score[5]
                    if isinstance(rubric, dict):
                        print(f"   Grade: {rubric.get('grade', 'N/A')}")
                        print(f"   Rubric JSON: {json.dumps(rubric, indent=2, ensure_ascii=False)[:200]}...")
                print(f"   Created: {score[6]}")
            else:
                print("⏳ Score가 아직 생성되지 않았습니다. (평가 진행 중일 수 있음)")
            
            # 3. Prompt Evaluations 확인 (Turn Evaluations)
            print("\n[3] Turn Evaluations 확인")
            turn_eval_result = await db.execute(text("""
                SELECT id, session_id, turn, evaluation_type, details, created_at
                FROM ai_vibe_coding_test.prompt_evaluations
                WHERE session_id = :session_id AND evaluation_type = 'TURN_EVAL'
                ORDER BY turn
            """), {"session_id": session_id})
            turn_evals = turn_eval_result.fetchall()
            
            if turn_evals:
                print(f"✅ Turn Evaluations 발견: {len(turn_evals)}개")
                for eval_row in turn_evals:
                    print(f"   Turn {eval_row[2]}: Score={eval_row[4].get('score', 'N/A') if isinstance(eval_row[4], dict) else 'N/A'}")
            else:
                print("⏳ Turn Evaluations가 아직 생성되지 않았습니다.")
            
            # 4. Holistic Flow Evaluation 확인
            print("\n[4] Holistic Flow Evaluation 확인")
            holistic_result = await db.execute(text("""
                SELECT id, session_id, turn, evaluation_type, details, created_at
                FROM ai_vibe_coding_test.prompt_evaluations
                WHERE session_id = :session_id AND evaluation_type = 'HOLISTIC_FLOW'
            """), {"session_id": session_id})
            holistic = holistic_result.fetchone()
            
            if holistic:
                print(f"✅ Holistic Flow Evaluation 발견:")
                print(f"   Score: {holistic[4].get('score', 'N/A') if isinstance(holistic[4], dict) else 'N/A'}")
                print(f"   Created: {holistic[5]}")
            else:
                print("⏳ Holistic Flow Evaluation이 아직 생성되지 않았습니다.")
            
            # 5. Session 상태 확인
            print("\n[5] Session 상태 확인")
            session_result = await db.execute(text("""
                SELECT id, exam_id, participant_id, spec_id, started_at, ended_at
                FROM ai_vibe_coding_test.prompt_sessions
                WHERE id = :session_id
            """), {"session_id": session_id})
            session = session_result.fetchone()
            
            if session:
                print(f"✅ Session 발견:")
                print(f"   ID: {session[0]}")
                print(f"   Started: {session[4]}")
                print(f"   Ended: {session[5] if session[5] else '진행 중'}")
            else:
                print("❌ Session을 찾을 수 없습니다.")
            
            print("\n" + "=" * 80)
            print("결과 확인 완료")
            print("=" * 80)
            
        except Exception as e:
            print(f"\n❌ 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    import json
    asyncio.run(check_submit_result())

