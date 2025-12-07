"""
최근 생성된 Submission과 Score 확인
"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.infrastructure.persistence.session import get_db_context, init_db


async def check_recent_submissions():
    """최근 생성된 Submission과 Score 확인"""
    await init_db()
    
    async with get_db_context() as db:
        # 최근 5개 Submission 조회
        print("=" * 80)
        print("최근 생성된 Submission 확인")
        print("=" * 80)
        
        result = await db.execute(text("""
            SELECT id, exam_id, participant_id, spec_id, lang, status, 
                   LENGTH(code_inline) as code_len, created_at
            FROM ai_vibe_coding_test.submissions
            ORDER BY created_at DESC
            LIMIT 5
        """))
        submissions = result.fetchall()
        
        if submissions:
            print(f"\n✅ 최근 {len(submissions)}개 Submission 발견:\n")
            for sub in submissions:
                print(f"  Submission ID: {sub[0]}")
                print(f"    Exam ID: {sub[1]}, Participant ID: {sub[2]}")
                print(f"    Language: {sub[4]}, Status: {sub[5]}")
                print(f"    Code 길이: {sub[6]} 문자")
                print(f"    Created: {sub[7]}")
                
                # 해당 Submission의 Score 확인
                score_result = await db.execute(text("""
                    SELECT submission_id, prompt_score, perf_score, correctness_score,
                           total_score, created_at
                    FROM ai_vibe_coding_test.scores
                    WHERE submission_id = :submission_id
                """), {"submission_id": sub[0]})
                score = score_result.fetchone()
                
                if score:
                    print(f"    ✅ Score 존재:")
                    print(f"       Prompt: {score[1]}, Perf: {score[2]}, Correct: {score[3]}")
                    print(f"       Total: {score[4]}")
                else:
                    print(f"    ⏳ Score 없음")
                print()
        else:
            print("❌ Submission을 찾을 수 없습니다.")
        
        # 최근 5개 Score 조회
        print("=" * 80)
        print("최근 생성된 Score 확인")
        print("=" * 80)
        
        score_result = await db.execute(text("""
            SELECT submission_id, prompt_score, perf_score, correctness_score,
                   total_score, created_at
            FROM ai_vibe_coding_test.scores
            ORDER BY created_at DESC
            LIMIT 5
        """))
        scores = score_result.fetchall()
        
        if scores:
            print(f"\n✅ 최근 {len(scores)}개 Score 발견:\n")
            for score in scores:
                print(f"  Submission ID: {score[0]}")
                print(f"    Prompt: {score[1]}, Perf: {score[2]}, Correct: {score[3]}")
                print(f"    Total: {score[4]}")
                print(f"    Created: {score[5]}")
                print()
        else:
            print("❌ Score를 찾을 수 없습니다.")
        
        # Session 1002의 평가 결과 확인
        print("=" * 80)
        print("Session 1002의 평가 결과 확인")
        print("=" * 80)
        
        eval_result = await db.execute(text("""
            SELECT id, session_id, turn, evaluation_type, details, created_at
            FROM ai_vibe_coding_test.prompt_evaluations
            WHERE session_id = 1002
            ORDER BY created_at DESC
        """))
        evals = eval_result.fetchall()
        
        if evals:
            print(f"\n✅ {len(evals)}개 평가 결과 발견:\n")
            for eval_row in evals:
                print(f"  ID: {eval_row[0]}, Turn: {eval_row[2]}, Type: {eval_row[3]}")
                if isinstance(eval_row[4], dict):
                    score = eval_row[4].get('score', 'N/A')
                    print(f"    Score: {score}")
                print(f"    Created: {eval_row[5]}")
                print()
        else:
            print("❌ 평가 결과를 찾을 수 없습니다.")


if __name__ == "__main__":
    asyncio.run(check_recent_submissions())

