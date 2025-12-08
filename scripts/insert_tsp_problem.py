"""
외판원 순회 문제를 problems와 problem_specs 테이블에 삽입
problem_info.py의 하드코딩된 정보를 기반으로 DB에 삽입
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
from app.domain.langgraph.utils.problem_info import HARDCODED_PROBLEM_SPEC


async def insert_tsp_problem():
    """외판원 순회 문제를 DB에 삽입"""
    print("=" * 80)
    print("외판원 순회 문제 DB 삽입")
    print("=" * 80)
    
    # DB 초기화
    await init_db()
    print("✅ DB 연결 완료")
    
    # problem_info.py에서 외판원 문제 정보 가져오기
    tsp_spec = HARDCODED_PROBLEM_SPEC.get(10)
    if not tsp_spec:
        print("❌ spec_id=10인 외판원 문제 정보를 찾을 수 없습니다.")
        return
    
    basic_info = tsp_spec.get("basic_info", {})
    constraints = tsp_spec.get("constraints", {})
    ai_guide = tsp_spec.get("ai_guide", {})
    solution_code = tsp_spec.get("solution_code", "")
    test_cases = tsp_spec.get("test_cases", [])
    rubric = tsp_spec.get("rubric", {})
    keywords = tsp_spec.get("keywords", [])
    
    async with get_db_context() as db:
        try:
            # 1. Problem 삽입 (id=1)
            problem_id = 1
            problem_title = basic_info.get("title", "외판원 순회")
            problem_description = basic_info.get("description_summary", "")
            
            # content_md 생성 (문제 설명)
            content_md = f"""# {problem_title}

## 문제 설명
{problem_description}

## 입력 형식
{basic_info.get("input_format", "")}

## 출력 형식
{basic_info.get("output_format", "")}

## 제약 조건
- 시간 제한: {constraints.get("time_limit_sec", 1.0)}초
- 메모리 제한: {constraints.get("memory_limit_mb", 128)}MB
- 변수 범위: {json.dumps(constraints.get("variable_ranges", {}), ensure_ascii=False)}

## 알고리즘 힌트
{constraints.get("logic_reasoning", "")}
"""
            
            tags_json = json.dumps(keywords, ensure_ascii=False)
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.problems (id, title, difficulty, status, tags)
                VALUES (:problem_id, :title, 'HARD', 'PUBLISHED', CAST(:tags AS jsonb))
                ON CONFLICT (id) DO UPDATE
                SET title = EXCLUDED.title,
                    difficulty = EXCLUDED.difficulty,
                    status = EXCLUDED.status,
                    tags = EXCLUDED.tags
            """), {
                "problem_id": problem_id,
                "title": problem_title,
                "tags": tags_json
            })
            print(f"✅ Problem 삽입 완료 (ID: {problem_id}, Title: {problem_title})")
            
            # 2. ProblemSpec 삽입 (spec_id=10)
            spec_id = 10
            spec_version = 1
            
            # rubric_json 생성 (채점 기준)
            rubric_json = {
                "correctness": rubric.get("correctness", {}),
                "performance": rubric.get("performance", {}),
                "code_quality": rubric.get("code_quality", {}),
                "test_cases": test_cases,
                "solution_code": solution_code,
                "ai_guide": ai_guide
            }
            
            # checker_json 생성 (테스트 케이스 정보)
            checker_json = {
                "test_cases": test_cases,
                "solution_code": solution_code
            }
            
            checker_json_str = json.dumps(checker_json, ensure_ascii=False)
            rubric_json_str = json.dumps(rubric_json, ensure_ascii=False)
            await db.execute(text("""
                INSERT INTO ai_vibe_coding_test.problem_specs 
                (spec_id, problem_id, version, content_md, checker_json, rubric_json)
                VALUES (:spec_id, :problem_id, :version, :content_md, CAST(:checker_json AS jsonb), CAST(:rubric_json AS jsonb))
                ON CONFLICT (spec_id) DO UPDATE
                SET problem_id = EXCLUDED.problem_id,
                    version = EXCLUDED.version,
                    content_md = EXCLUDED.content_md,
                    checker_json = EXCLUDED.checker_json,
                    rubric_json = EXCLUDED.rubric_json
            """), {
                "spec_id": spec_id,
                "problem_id": problem_id,
                "version": spec_version,
                "content_md": content_md,
                "checker_json": checker_json_str,
                "rubric_json": rubric_json_str
            })
            print(f"✅ ProblemSpec 삽입 완료 (spec_id: {spec_id}, problem_id: {problem_id}, version: {spec_version})")
            
            # 3. problems 테이블의 current_spec_id 업데이트
            await db.execute(text("""
                UPDATE ai_vibe_coding_test.problems
                SET current_spec_id = :spec_id
                WHERE id = :problem_id
            """), {
                "spec_id": spec_id,
                "problem_id": problem_id
            })
            print(f"✅ Problem.current_spec_id 업데이트 완료 (current_spec_id: {spec_id})")
            
            await db.commit()
            
            print("\n" + "=" * 80)
            print("✅ 외판원 순회 문제 삽입 완료!")
            print("=" * 80)
            print(f"\n삽입된 데이터:")
            print(f"  - Problem: ID={problem_id}, Title={problem_title}")
            print(f"  - ProblemSpec: spec_id={spec_id}, problem_id={problem_id}, version={spec_version}")
            print(f"  - 테스트 케이스: {len(test_cases)}개")
            print(f"  - 키워드: {', '.join(keywords)}")
            
        except Exception as e:
            await db.rollback()
            print(f"\n❌ 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(insert_tsp_problem())

