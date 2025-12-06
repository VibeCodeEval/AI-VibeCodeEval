"""
피보나치 문제를 DB에 저장하는 스크립트

[사용법]
uv run python test_scripts/insert_fibonacci_problem_to_db.py

[저장되는 데이터]
- Problem: "피보나치 수열 계산" (id=2, difficulty=EASY)
- ProblemSpec: spec_id=20, version=1
  - content_md: 문제 설명 (마크다운)
  - checker_json: 테스트 케이스, 정답 코드
  - rubric_json: 채점 기준, AI 가이드, 제약 조건, 키워드
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


# 피보나치 문제 데이터
FIBONACCI_PROBLEM_DATA = {
    "basic_info": {
        "title": "피보나치 수열 계산",
        "problem_id": "fibonacci",
        "description_summary": "피보나치 수열의 n번째 항을 계산하는 함수를 작성하세요.\n\n피보나치 수열은 다음과 같이 정의됩니다:\n- F(0) = 0\n- F(1) = 1\n- F(n) = F(n-1) + F(n-2) (n ≥ 2)",
        "input_format": "정수 n이 주어집니다. (0 ≤ n ≤ 30)",
        "output_format": "피보나치 수열의 n번째 항을 출력하세요."
    },
    "solution_code": """import sys

def fibonacci(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for i in range(2, n + 1):
        a, b = b, a + b
    return b

if __name__ == "__main__":
    n = int(sys.stdin.readline())
    print(fibonacci(n))
""",
    "test_cases": [
        {
            "description": "기본 케이스 1",
            "input": "0",
            "expected": "0",
            "is_sample": True
        },
        {
            "description": "기본 케이스 2",
            "input": "1",
            "expected": "1",
            "is_sample": True
        },
        {
            "description": "기본 케이스 3",
            "input": "2",
            "expected": "1",
            "is_sample": True
        },
        {
            "description": "기본 케이스 4",
            "input": "3",
            "expected": "2",
            "is_sample": False
        },
        {
            "description": "기본 케이스 5",
            "input": "5",
            "expected": "5",
            "is_sample": False
        },
        {
            "description": "기본 케이스 6",
            "input": "10",
            "expected": "55",
            "is_sample": False
        },
        {
            "description": "경계 케이스",
            "input": "30",
            "expected": "832040",
            "is_sample": False
        }
    ],
    "constraints": {
        "time_limit_sec": 1.0,
        "memory_limit_mb": 128
    },
    "ai_guide": {
        "hint": "재귀 또는 반복 방식으로 구현할 수 있습니다. n이 작으므로 두 방식 모두 가능합니다.",
        "keywords": ["피보나치", "재귀", "반복", "동적 계획법"]
    },
    "rubric": {
        "correctness": {
            "weight": 0.5,
            "description": "테스트 케이스 통과율"
        },
        "performance": {
            "weight": 0.25,
            "description": "시간/공간 복잡도"
        },
        "prompt": {
            "weight": 0.25,
            "description": "프롬프트 품질"
        }
    },
    "keywords": ["피보나치", "수열", "재귀", "반복", "DP"]
}


async def insert_fibonacci_problem():
    """피보나치 문제를 DB에 저장"""
    print("=" * 80)
    print("피보나치 문제 DB 저장")
    print("=" * 80)
    
    # DB 초기화
    await init_db()
    print("✅ DB 연결 완료")
    
    async with get_db_context() as db:
        try:
            # 1. Problem 생성/업데이트
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.problems (id, title, difficulty, status)
                VALUES (2, :title, 'EASY', 'PUBLISHED')
                ON CONFLICT (id) DO UPDATE
                SET title = EXCLUDED.title, difficulty = EXCLUDED.difficulty, status = EXCLUDED.status
            """), {"title": FIBONACCI_PROBLEM_DATA["basic_info"]["title"]})
            print("✅ Problem 생성/업데이트 완료 (ID: 2, 제목: 피보나치 수열 계산)")
            
            # 2. content_md 생성 (마크다운 형식)
            basic_info = FIBONACCI_PROBLEM_DATA["basic_info"]
            content_md = f"""# {basic_info["title"]}

## 문제 설명
{basic_info["description_summary"]}

## 입력 형식
{basic_info["input_format"]}

## 출력 형식
{basic_info["output_format"]}
"""
            
            # 3. checker_json 생성 (테스트 케이스 + 정답 코드)
            checker_json = {
                "solution_code": FIBONACCI_PROBLEM_DATA["solution_code"],
                "test_cases": FIBONACCI_PROBLEM_DATA["test_cases"]
            }
            
            # 4. rubric_json 생성 (채점 기준 + 제약 조건 + AI 가이드 + 키워드)
            rubric_json = {
                "rubric": FIBONACCI_PROBLEM_DATA["rubric"],
                "constraints": FIBONACCI_PROBLEM_DATA["constraints"],
                "ai_guide": FIBONACCI_PROBLEM_DATA["ai_guide"],
                "keywords": FIBONACCI_PROBLEM_DATA["keywords"]
            }
            
            # 5. ProblemSpec 생성/업데이트 (직접 SQL 사용 - spec_id가 PK)
            # JSON 문자열로 변환
            checker_json_str = json.dumps(checker_json, ensure_ascii=False)
            rubric_json_str = json.dumps(rubric_json, ensure_ascii=False)
            
            # PostgreSQL의 jsonb 타입 캐스팅을 위해 CAST 사용
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.problem_specs 
                (spec_id, problem_id, version, content_md, checker_json, rubric_json)
                VALUES (20, 2, 1, :content_md, CAST(:checker_json AS jsonb), CAST(:rubric_json AS jsonb))
                ON CONFLICT (spec_id) DO UPDATE
                SET content_md = EXCLUDED.content_md,
                    checker_json = EXCLUDED.checker_json,
                    rubric_json = EXCLUDED.rubric_json
            """), {
                "content_md": content_md,
                "checker_json": checker_json_str,
                "rubric_json": rubric_json_str
            })
            print("✅ ProblemSpec 생성/업데이트 완료 (spec_id: 20)")
            
            # 6. Problem의 current_spec_id 업데이트
            await db.execute(text("""
                UPDATE ai_vibe_coding_test.problems
                SET current_spec_id = 20
                WHERE id = 2
            """))
            print("✅ Problem.current_spec_id 업데이트 완료 (20)")
            
            # 7. exam_participants에 spec_id 연결 (기존 exam_id=1, participant_id=100 사용)
            await db.execute(text("""
                UPDATE ai_vibe_coding_test.exam_participants
                SET spec_id = 20
                WHERE exam_id = 1 AND participant_id = 100
            """))
            print("✅ exam_participants.spec_id 업데이트 완료 (spec_id: 20)")
            
            await db.commit()
            print("\n✅ 모든 데이터 저장 완료!")
            
            # 확인
            print("\n" + "=" * 80)
            print("저장된 데이터 확인")
            print("=" * 80)
            
            # Problem 확인
            result = await db.execute(text("""
                SELECT id, title, difficulty, status, current_spec_id
                FROM ai_vibe_coding_test.problems
                WHERE id = 2
            """))
            problem = result.fetchone()
            if problem:
                print(f"✅ Problem:")
                print(f"   - ID: {problem[0]}")
                print(f"   - 제목: {problem[1]}")
                print(f"   - 난이도: {problem[2]}")
                print(f"   - 상태: {problem[3]}")
                print(f"   - current_spec_id: {problem[4]}")
            
            # ProblemSpec 확인
            result = await db.execute(text("""
                SELECT spec_id, problem_id, version
                FROM ai_vibe_coding_test.problem_specs
                WHERE spec_id = 20
            """))
            spec = result.fetchone()
            if spec:
                print(f"\n✅ ProblemSpec:")
                print(f"   - spec_id: {spec[0]}")
                print(f"   - problem_id: {spec[1]}")
                print(f"   - version: {spec[2]}")
            
            print("\n" + "=" * 80)
            print("피보나치 문제 저장 완료!")
            print("=" * 80)
            
        except Exception as e:
            await db.rollback()
            print(f"\n❌ 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(insert_fibonacci_problem())

