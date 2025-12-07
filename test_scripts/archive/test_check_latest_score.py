"""
최근 생성된 Score 확인 (Judge0 결과 포함)
"""
import asyncio
import sys
import json
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.infrastructure.persistence.session import get_db_context


async def check_latest_score():
    """최근 생성된 Score 확인"""
    print("=" * 80)
    print("최근 생성된 Score 확인 (Judge0 결과 포함)")
    print("=" * 80)
    
    async with get_db_context() as db:
        # 최근 생성된 Score 조회
        query = text("""
            SELECT submission_id, prompt_score, perf_score, correctness_score, 
                   total_score, rubric_json, created_at
            FROM ai_vibe_coding_test.scores
            ORDER BY created_at DESC
            LIMIT 5
        """)
        result = await db.execute(query)
        scores = result.fetchall()
        
        if not scores:
            print("❌ Score가 없습니다.")
            return
        
        print(f"\n✅ 최근 생성된 Score: {len(scores)}개\n")
        
        for score in scores:
            submission_id, prompt_score, perf_score, correctness_score, total_score, rubric_json, created_at = score
            
            print(f"[Submission ID: {submission_id}]")
            print(f"  - Prompt Score: {prompt_score}")
            print(f"  - Performance Score: {perf_score}")
            print(f"  - Correctness Score: {correctness_score}")
            print(f"  - Total Score: {total_score}")
            print(f"  - Created: {created_at}")
            
            if rubric_json:
                rubric = rubric_json
                print(f"\n  [Rubric JSON 내용]")
                print(f"    - Grade: {rubric.get('grade')}")
                print(f"    - Total Score: {rubric.get('total_score')}")
                
                # Performance Details 확인
                perf_details = rubric.get('performance_details')
                if perf_details:
                    print(f"\n    [Performance Details]")
                    print(f"      - Execution Time: {perf_details.get('execution_time')}초")
                    print(f"      - Memory Used: {perf_details.get('memory_used_mb')}MB")
                    print(f"      - Skip Performance: {perf_details.get('skip_performance')}")
                    print(f"      - Skip Reason: {perf_details.get('skip_reason')}")
                else:
                    print(f"    ⚠️ Performance Details 없음")
                
                # Correctness Details 확인
                correct_details = rubric.get('correctness_details')
                if correct_details:
                    print(f"\n    [Correctness Details]")
                    print(f"      - Test Cases Passed: {correct_details.get('test_cases_passed')}")
                    print(f"      - Test Cases Total: {correct_details.get('test_cases_total')}")
                    print(f"      - Pass Rate: {correct_details.get('pass_rate')}%")
                else:
                    print(f"    ⚠️ Correctness Details 없음")
                
                # 전체 JSON 출력 (선택적)
                print(f"\n    [전체 Rubric JSON (처음 500자)]")
                json_str = json.dumps(rubric, indent=2, ensure_ascii=False)
                print(f"    {json_str[:500]}...")
            
            print("\n" + "-" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(check_latest_score())

