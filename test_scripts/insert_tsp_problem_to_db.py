"""
하드코딩된 외판원 문제를 DB에 저장하는 스크립트

[사용법]
uv run python test_scripts/insert_tsp_problem_to_db.py

[저장되는 데이터]
- Problem: "외판원 순회" (id=1, difficulty=HARD)
- ProblemSpec: spec_id=10, version=1
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
from sqlalchemy.dialects.postgresql import JSONB
from app.infrastructure.persistence.session import get_db_context, init_db
from app.infrastructure.persistence.models.problems import Problem, ProblemSpec
from app.domain.langgraph.utils.problem_info import HARDCODED_PROBLEM_SPEC


async def insert_tsp_problem():
    """외판원 문제를 DB에 저장"""
    print("=" * 80)
    print("외판원 문제 DB 저장")
    print("=" * 80)
    
    # DB 초기화
    await init_db()
    print("✅ DB 연결 완료")
    
    # 하드코딩된 데이터 가져오기
    tsp_data = HARDCODED_PROBLEM_SPEC[10]
    
    async with get_db_context() as db:
        try:
            # 1. Problem 생성/업데이트
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.problems (id, title, difficulty, status)
                VALUES (1, :title, 'HARD', 'PUBLISHED')
                ON CONFLICT (id) DO UPDATE
                SET title = EXCLUDED.title, difficulty = EXCLUDED.difficulty, status = EXCLUDED.status
            """), {"title": tsp_data["basic_info"]["title"]})
            print("✅ Problem 생성/업데이트 완료 (ID: 1, 제목: 외판원 순회)")
            
            # 2. content_md 생성 (마크다운 형식)
            basic_info = tsp_data["basic_info"]
            content_md = f"""# {basic_info["title"]} (백준 {basic_info["problem_id"]}번)

## 문제 설명
{basic_info["description_summary"]}

## 입력 형식
{basic_info["input_format"]}

## 출력 형식
{basic_info["output_format"]}
"""
            
            # 3. checker_json 생성 (테스트 케이스 + 정답 코드)
            checker_json = {
                "solution_code": tsp_data["solution_code"],
                "test_cases": tsp_data["test_cases"]
            }
            
            # 4. rubric_json 생성 (채점 기준 + 제약 조건 + AI 가이드 + 키워드)
            rubric_json = {
                "rubric": tsp_data["rubric"],
                "constraints": tsp_data["constraints"],
                "ai_guide": tsp_data["ai_guide"],
                "keywords": tsp_data["keywords"]
            }
            
            # 5. ProblemSpec 생성/업데이트 (직접 SQL 사용 - spec_id가 PK)
            # JSON 문자열로 변환
            checker_json_str = json.dumps(checker_json, ensure_ascii=False)
            rubric_json_str = json.dumps(rubric_json, ensure_ascii=False)
            
            # PostgreSQL의 jsonb 타입 캐스팅을 위해 CAST 사용
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.problem_specs 
                (spec_id, problem_id, version, content_md, checker_json, rubric_json)
                VALUES (10, 1, 1, :content_md, CAST(:checker_json AS jsonb), CAST(:rubric_json AS jsonb))
                ON CONFLICT (spec_id) DO UPDATE
                SET content_md = EXCLUDED.content_md,
                    checker_json = EXCLUDED.checker_json,
                    rubric_json = EXCLUDED.rubric_json
            """), {
                "content_md": content_md,
                "checker_json": checker_json_str,
                "rubric_json": rubric_json_str
            })
            print("✅ ProblemSpec 생성/업데이트 완료 (spec_id: 10)")
            
            # 6. Problem의 current_spec_id 업데이트
            await db.execute(text("""
                UPDATE ai_vibe_coding_test.problems
                SET current_spec_id = 10
                WHERE id = 1
            """))
            print("✅ Problem.current_spec_id 업데이트 완료 (10)")
            
            # 확인
            print("\n" + "=" * 80)
            print("저장된 데이터 확인")
            print("=" * 80)
            
            # Problem 확인
            result = await db.execute(text("""
                SELECT id, title, difficulty, status, current_spec_id
                FROM ai_vibe_coding_test.problems
                WHERE id = 1
            """))
            problem = result.fetchone()
            if problem:
                print(f"✅ Problem:")
                print(f"   - ID: {problem.id}")
                print(f"   - 제목: {problem.title}")
                print(f"   - 난이도: {problem.difficulty}")
                print(f"   - 상태: {problem.status}")
                print(f"   - 현재 스펙 ID: {problem.current_spec_id}")
            
            # ProblemSpec 확인
            result = await db.execute(text("""
                SELECT spec_id, problem_id, version, 
                       LENGTH(content_md) as content_length,
                       checker_json->>'solution_code' IS NOT NULL as has_solution,
                       jsonb_array_length(checker_json->'test_cases') as test_case_count,
                       rubric_json->'rubric' IS NOT NULL as has_rubric,
                       rubric_json->'ai_guide' IS NOT NULL as has_ai_guide
                FROM ai_vibe_coding_test.problem_specs
                WHERE spec_id = 10
            """))
            spec = result.fetchone()
            if spec:
                print(f"\n✅ ProblemSpec:")
                print(f"   - Spec ID: {spec.spec_id}")
                print(f"   - Problem ID: {spec.problem_id}")
                print(f"   - Version: {spec.version}")
                print(f"   - Content MD 길이: {spec.content_length} bytes")
                print(f"   - 정답 코드 포함: {spec.has_solution}")
                print(f"   - 테스트 케이스 수: {spec.test_case_count}")
                print(f"   - 채점 기준 포함: {spec.has_rubric}")
                print(f"   - AI 가이드 포함: {spec.has_ai_guide}")
            
            print("\n" + "=" * 80)
            print("✅ 외판원 문제 DB 저장 완료!")
            print("=" * 80)
            print("\n이제 get_problem_info() 함수가 DB에서 조회합니다.")
            print("하드코딩 딕셔너리는 Fallback으로만 사용됩니다.")
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(insert_tsp_problem())

