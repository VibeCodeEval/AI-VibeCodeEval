"""
Judge0 단독 테스트 스크립트

목적:
1. Judge0 API 직접 호출 테스트
2. 제출 코드 형식 확인
3. 결과 수신 확인
4. 0점 원인 파악

사용법:
    uv run python test_scripts/test_judge0_unit.py
    uv run python test_scripts/test_judge0_unit.py <code_file.py>
"""
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.infrastructure.judge0.client import Judge0Client
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_simple_code():
    """간단한 Python 코드 테스트"""
    logger.info("=" * 60)
    logger.info("테스트 1: 간단한 Python 코드 실행")
    logger.info("=" * 60)
    
    client = Judge0Client()
    
    code = """print("Hello, World!")"""
    
    try:
        logger.info(f"[Test 1] 코드: {code}")
        logger.info(f"[Test 1] 코드 길이: {len(code)} 문자")
        logger.info(f"[Test 1] 코드 바이트: {len(code.encode('utf-8'))} bytes")
        
        result = await client.execute_code(
            code=code,
            language="python",
            stdin="",
            cpu_time_limit=5,
            memory_limit=128,
            wait=True
        )
        
        status_id = result.get("status", {}).get("id")
        status_desc = result.get("status", {}).get("description", "")
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        compile_output = result.get("compile_output", "")
        time = result.get("time", "0")
        memory = result.get("memory", "0")
        
        logger.info(f"[Test 1] 결과:")
        logger.info(f"  - Status ID: {status_id}")
        logger.info(f"  - Status: {status_desc}")
        logger.info(f"  - stdout: {stdout}")
        logger.info(f"  - stderr: {stderr}")
        logger.info(f"  - compile_output: {compile_output}")
        logger.info(f"  - time: {time}s")
        logger.info(f"  - memory: {memory}KB")
        
        if status_id == 3:  # Accepted
            logger.info("[Test 1] ✅ 성공!")
            return True
        else:
            logger.error(f"[Test 1] ❌ 실패 - Status ID: {status_id}")
            return False
            
    except Exception as e:
        logger.error(f"[Test 1] ❌ 오류: {str(e)}", exc_info=True)
        return False
    finally:
        await client.close()


async def test_code_with_input():
    """입력이 있는 코드 테스트"""
    logger.info("\n" + "=" * 60)
    logger.info("테스트 2: 입력이 있는 코드 실행")
    logger.info("=" * 60)
    
    client = Judge0Client()
    
    code = """n = int(input())
print(n * 2)"""
    
    stdin = "5"
    expected = "10"
    
    try:
        logger.info(f"[Test 2] 코드:\n{code}")
        logger.info(f"[Test 2] stdin: {stdin}")
        logger.info(f"[Test 2] expected: {expected}")
        
        result = await client.execute_code(
            code=code,
            language="python",
            stdin=stdin,
            expected_output=expected,
            cpu_time_limit=5,
            memory_limit=128,
            wait=True
        )
        
        status_id = result.get("status", {}).get("id")
        stdout = result.get("stdout", "").strip()
        
        logger.info(f"[Test 2] 결과:")
        logger.info(f"  - Status ID: {status_id}")
        logger.info(f"  - stdout: '{stdout}'")
        logger.info(f"  - expected: '{expected}'")
        
        if status_id == 3 and stdout == expected:
            logger.info("[Test 2] ✅ 성공! (출력 일치)")
            return True
        else:
            logger.warning(f"[Test 2] ⚠️ Status: {status_id}, 출력 불일치")
            return False
            
    except Exception as e:
        logger.error(f"[Test 2] ❌ 오류: {str(e)}", exc_info=True)
        return False
    finally:
        await client.close()


async def test_code_format_issues():
    """코드 형식 문제 테스트 (마크다운 코드 블록 등)"""
    logger.info("\n" + "=" * 60)
    logger.info("테스트 3: 코드 형식 문제 확인")
    logger.info("=" * 60)
    
    client = Judge0Client()
    
    # 다양한 형식의 코드 테스트
    test_cases = [
        {
            "name": "일반 코드",
            "code": "print('Hello')"
        },
        {
            "name": "마크다운 코드 블록 포함 (```python ... ```)",
            "code": "```python\nprint('Hello')\n```"
        },
        {
            "name": "마크다운 코드 블록 (``` ... ```)",
            "code": "```\nprint('Hello')\n```"
        },
        {
            "name": "들여쓰기 포함",
            "code": "def test():\n    print('Hello')\n    return 1\n\ntest()"
        },
        {
            "name": "특수 문자 포함",
            "code": "print('안녕하세요')\nprint('Hello, World!')"
        },
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        logger.info(f"\n[Test 3.{i}] {test_case['name']}")
        logger.info(f"코드:\n{test_case['code']}")
        
        try:
            result = await client.execute_code(
                code=test_case['code'],
                language="python",
                stdin="",
                cpu_time_limit=5,
                memory_limit=128,
                wait=True
            )
            
            status_id = result.get("status", {}).get("id")
            status_desc = result.get("status", {}).get("description", "")
            stdout = result.get("stdout", "")
            stderr = result.get("stderr", "")
            compile_output = result.get("compile_output", "")
            
            success = status_id == 3
            
            logger.info(f"  - Status: {status_desc} (ID: {status_id})")
            if stdout:
                logger.info(f"  - stdout: {stdout}")
            if stderr:
                logger.warning(f"  - stderr: {stderr}")
            if compile_output:
                logger.warning(f"  - compile_output: {compile_output}")
            
            if success:
                logger.info(f"  ✅ 성공")
            else:
                logger.error(f"  ❌ 실패")
            
            results.append({
                "name": test_case['name'],
                "success": success,
                "status_id": status_id,
                "status_desc": status_desc,
                "stdout": stdout,
                "stderr": stderr,
                "compile_output": compile_output
            })
            
        except Exception as e:
            logger.error(f"  ❌ 오류: {str(e)}")
            results.append({
                "name": test_case['name'],
                "success": False,
                "error": str(e)
            })
    
    # 결과 요약
    logger.info("\n" + "=" * 60)
    logger.info("테스트 3 결과 요약")
    logger.info("=" * 60)
    for result in results:
        status = "✅" if result.get("success") else "❌"
        logger.info(f"{status} {result['name']}")
        if not result.get("success"):
            if "error" in result:
                logger.info(f"   오류: {result['error']}")
            else:
                logger.info(f"   Status: {result.get('status_desc', 'Unknown')}")
                if result.get("compile_output"):
                    logger.info(f"   컴파일 오류: {result['compile_output'][:200]}")
    
    return results


async def test_actual_submission_code(code: str):
    """실제 제출 코드 테스트"""
    logger.info("\n" + "=" * 60)
    logger.info("테스트 4: 실제 제출 코드 테스트")
    logger.info("=" * 60)
    
    client = Judge0Client()
    
    # 코드 정리 (마크다운 코드 블록 제거)
    cleaned_code = code
    
    # 마크다운 코드 블록 제거
    if code.strip().startswith("```"):
        lines = code.split("\n")
        # 첫 줄과 마지막 줄 제거 (```python 또는 ```)
        if len(lines) > 2:
            cleaned_code = "\n".join(lines[1:-1])
        else:
            cleaned_code = ""
    
    logger.info(f"[Test 4] 원본 코드 길이: {len(code)} 문자")
    logger.info(f"[Test 4] 정리된 코드 길이: {len(cleaned_code)} 문자")
    logger.info(f"[Test 4] 원본 코드 (처음 200자):\n{code[:200]}")
    logger.info(f"[Test 4] 정리된 코드 (처음 200자):\n{cleaned_code[:200]}")
    
    # 원본 코드 테스트
    logger.info("\n[Test 4-1] 원본 코드로 실행")
    try:
        result1 = await client.execute_code(
            code=code,
            language="python",
            stdin="",
            cpu_time_limit=5,
            memory_limit=128,
            wait=True
        )
        
        status_id1 = result1.get("status", {}).get("id")
        logger.info(f"  - Status ID: {status_id1}")
        logger.info(f"  - stdout: {result1.get('stdout', '')}")
        logger.info(f"  - stderr: {result1.get('stderr', '')}")
        logger.info(f"  - compile_output: {result1.get('compile_output', '')}")
        
    except Exception as e:
        logger.error(f"  ❌ 오류: {str(e)}")
        result1 = None
    
    # 정리된 코드 테스트
    if cleaned_code != code:
        logger.info("\n[Test 4-2] 정리된 코드로 실행")
        try:
            result2 = await client.execute_code(
                code=cleaned_code,
                language="python",
                stdin="",
                cpu_time_limit=5,
                memory_limit=128,
                wait=True
            )
            
            status_id2 = result2.get("status", {}).get("id")
            logger.info(f"  - Status ID: {status_id2}")
            logger.info(f"  - stdout: {result2.get('stdout', '')}")
            logger.info(f"  - stderr: {result2.get('stderr', '')}")
            logger.info(f"  - compile_output: {result2.get('compile_output', '')}")
            
            if status_id2 == 3:
                logger.info("  ✅ 정리된 코드는 성공!")
                return True
            
        except Exception as e:
            logger.error(f"  ❌ 오류: {str(e)}")
    
    if result1 and result1.get("status", {}).get("id") == 3:
        return True
    
    return False


async def test_with_test_case():
    """테스트 케이스가 있는 코드 실행"""
    logger.info("\n" + "=" * 60)
    logger.info("테스트 5: 테스트 케이스 실행")
    logger.info("=" * 60)
    
    client = Judge0Client()
    
    code = """n = int(input())
print(n * 2)"""
    
    test_cases = [
        {"input": "5", "expected": "10"},
        {"input": "10", "expected": "20"},
    ]
    
    try:
        results = await client.execute_test_cases(
            code=code,
            language="python",
            test_cases=test_cases,
            cpu_time_limit=5,
            memory_limit=128
        )
        
        logger.info(f"[Test 5] 테스트 케이스 {len(test_cases)}개 실행")
        
        passed = 0
        for i, result in enumerate(results, 1):
            status = "✅" if result["passed"] else "❌"
            logger.info(f"{status} TC {i}: {result['input']} → {result['actual']} (expected: {result['expected']})")
            if result["passed"]:
                passed += 1
        
        logger.info(f"[Test 5] 통과: {passed}/{len(test_cases)}")
        
        return passed == len(test_cases)
        
    except Exception as e:
        logger.error(f"[Test 5] ❌ 오류: {str(e)}", exc_info=True)
        return False
    finally:
        await client.close()


async def main():
    """메인 함수"""
    logger.info("Judge0 단독 테스트 시작")
    logger.info(f"Judge0 API URL: {settings.JUDGE0_API_URL}")
    logger.info(f"RapidAPI 사용: {settings.JUDGE0_USE_RAPIDAPI}")
    
    results = {}
    
    # 테스트 1: 간단한 코드
    results["test1"] = await test_simple_code()
    
    # 테스트 2: 입력이 있는 코드
    results["test2"] = await test_code_with_input()
    
    # 테스트 3: 코드 형식 문제
    format_results = await test_code_format_issues()
    results["test3"] = any(r.get("success") for r in format_results)
    
    # 테스트 4: 실제 제출 코드 (명령줄 인자로 받기)
    if len(sys.argv) > 1:
        # 파일에서 코드 읽기
        code_file = sys.argv[1]
        try:
            with open(code_file, 'r', encoding='utf-8') as f:
                code = f.read()
            results["test4"] = await test_actual_submission_code(code)
        except Exception as e:
            logger.error(f"파일 읽기 실패: {str(e)}")
            results["test4"] = False
    else:
        logger.info("\n[Test 4] 건너뜀 (코드 파일 경로를 인자로 제공하세요)")
        logger.info("사용법: python test_scripts/test_judge0_unit.py <code_file.py>")
    
    # 테스트 5: 테스트 케이스
    results["test5"] = await test_with_test_case()
    
    # 종합 결과
    logger.info("\n" + "=" * 60)
    logger.info("종합 결과")
    logger.info("=" * 60)
    
    for test_name, result in results.items():
        status = "✅" if result else "❌"
        logger.info(f"{status} {test_name}: {result}")
    
    success_count = sum(1 for r in results.values() if r)
    total_count = len(results)
    
    logger.info(f"\n성공: {success_count}/{total_count}")
    
    if success_count == total_count:
        logger.info("✅ 모든 테스트 통과!")
        sys.exit(0)
    else:
        logger.error("❌ 일부 테스트 실패")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

