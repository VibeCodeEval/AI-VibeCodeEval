"""
Judge0 코드 제출 및 평가 테스트 스크립트

실제 Flow를 따라:
1. problem_info.py에서 TC와 정답 가져오기
2. 코드 제출
3. Judge0 실행
4. 결과 비교 및 점수 계산

사용법:
    # 코드 파일로 제출
    uv run python test_scripts/test_judge0_submit.py --code-file your_code.py
    
    # 코드 직접 입력
    uv run python test_scripts/test_judge0_submit.py --code "print('Hello')"
    
    # 특정 spec_id 사용 (기본값: 10)
    uv run python test_scripts/test_judge0_submit.py --code-file code.py --spec-id 10
"""
import asyncio
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.infrastructure.judge0.client import Judge0Client
from app.domain.langgraph.utils.problem_info import get_problem_info_sync
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def clean_code(code: str) -> str:
    """코드 정리 (마크다운 코드 블록 제거)"""
    if not code:
        return ""
    
    cleaned = code.strip()
    
    # 마크다운 코드 블록 제거
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if len(lines) >= 3:
            # 첫 줄 (```python 또는 ```)과 마지막 줄 (```) 제거
            cleaned = "\n".join(lines[1:-1])
    
    return cleaned.strip()


def calculate_correctness_score(test_case_results: list) -> Dict[str, Any]:
    """
    Correctness 점수 계산 (실제 Flow와 동일)
    
    Args:
        test_case_results: Judge0 실행 결과 리스트
        
    Returns:
        점수 정보 딕셔너리
    """
    if not test_case_results:
        return {
            "score": 0.0,
            "passed": 0,
            "total": 0,
            "passed_rate": 0.0
        }
    
    passed_count = sum(1 for r in test_case_results if r.get("passed", False))
    total_count = len(test_case_results)
    
    # 실제 Flow와 동일: 통과하면 100점, 실패하면 0점
    if passed_count == total_count:
        score = 100.0
    else:
        score = 0.0
    
    return {
        "score": score,
        "passed": passed_count,
        "total": total_count,
        "passed_rate": (passed_count / total_count * 100) if total_count > 0 else 0.0
    }


def calculate_performance_score(
    execution_time: float,
    memory_used_mb: float,
    time_limit_sec: float = 1.0,
    memory_limit_mb: float = 128.0
) -> Dict[str, Any]:
    """
    Performance 점수 계산 (실제 Flow와 동일)
    
    Args:
        execution_time: 실행 시간 (초)
        memory_used_mb: 메모리 사용량 (MB)
        time_limit_sec: 시간 제한 (초)
        memory_limit_mb: 메모리 제한 (MB)
        
    Returns:
        점수 정보 딕셔너리
    """
    # 시간 점수 (60% 가중치)
    if execution_time <= time_limit_sec:
        time_score = 100.0
    else:
        # 초과 시 감점
        time_score = max(0.0, 100.0 * (1.0 - (execution_time - time_limit_sec) / time_limit_sec))
    
    # 메모리 점수 (40% 가중치)
    if memory_used_mb <= memory_limit_mb:
        memory_score = 100.0
    else:
        # 초과 시 감점
        memory_score = max(0.0, 100.0 * (1.0 - (memory_used_mb - memory_limit_mb) / memory_limit_mb))
    
    # 가중 평균
    performance_score = time_score * 0.6 + memory_score * 0.4
    
    return {
        "score": performance_score,
        "time_score": time_score,
        "memory_score": memory_score,
        "execution_time": execution_time,
        "memory_used_mb": memory_used_mb,
        "time_limit_sec": time_limit_sec,
        "memory_limit_mb": memory_limit_mb
    }


async def test_submit_code(
    code: str,
    spec_id: Optional[int] = None,
    test_cases: Optional[list] = None,
    constraints: Optional[Dict[str, Any]] = None,
    language: str = "python",
    use_first_tc_only: bool = True
) -> Dict[str, Any]:
    """
    코드 제출 및 평가 (실제 Flow 따라가기)
    
    Args:
        code: 제출할 코드
        spec_id: 문제 스펙 ID (하드코딩 딕셔너리 키, 기본값: 10)
        test_cases: 테스트 케이스 리스트 (직접 제공 시 spec_id 무시)
        constraints: 제약 조건 (직접 제공 시 spec_id 무시)
        language: 프로그래밍 언어
        use_first_tc_only: 첫 번째 TC만 사용 여부 (실제 Flow와 동일)
        
    Returns:
        평가 결과 딕셔너리
    """
    logger.info("=" * 80)
    logger.info("Judge0 코드 제출 및 평가 시작")
    logger.info("=" * 80)
    
    problem_context = None
    problem_title = "테스트 문제"
    
    # 1. 테스트 케이스 가져오기
    if test_cases:
        # 직접 제공된 테스트 케이스 사용
        logger.info(f"\n[1단계] 직접 제공된 테스트 케이스 사용")
        test_cases_raw = test_cases
        if constraints:
            timeout = constraints.get("time_limit_sec") or 1.0
            memory_limit = constraints.get("memory_limit_mb") or 128
        else:
            timeout = 1.0
            memory_limit = 128
            logger.warning("⚠️ 제약 조건이 제공되지 않아 기본값 사용 (timeout: 1.0초, memory: 128MB)")
    elif spec_id:
        # spec_id로 하드코딩 딕셔너리에서 가져오기 (실제 Flow와 동일)
        logger.info(f"\n[1단계] 문제 정보 가져오기 - spec_id: {spec_id}")
        logger.warning("⚠️ spec_id는 하드코딩 딕셔너리(HARDCODED_PROBLEM_SPEC)의 키로만 사용됩니다.")
        logger.warning("⚠️ DB에서 정보를 가져오는 로직은 없습니다.")
        
        problem_context = get_problem_info_sync(spec_id)
        
        if not problem_context or not problem_context.get("test_cases"):
            logger.error(f"❌ 문제 정보를 찾을 수 없습니다 - spec_id: {spec_id}")
            logger.error(f"   사용 가능한 spec_id: {list(get_problem_info_sync.__globals__.get('HARDCODED_PROBLEM_SPEC', {}).keys())}")
            return {"error": "Problem not found"}
        
        problem_title = problem_context.get("basic_info", {}).get("title", "알 수 없음")
        logger.info(f"✅ 문제: {problem_title}")
        
        test_cases_raw = problem_context.get("test_cases", [])
        constraints = problem_context.get("constraints", {})
        timeout = constraints.get("time_limit_sec") or 1.0
        memory_limit = constraints.get("memory_limit_mb") or 128
    else:
        logger.error("❌ spec_id 또는 test_cases를 제공해주세요")
        return {"error": "spec_id or test_cases required"}
    
    # 2. 테스트 케이스 추출 (실제 Flow와 동일)
    logger.info(f"\n[2단계] 테스트 케이스 추출")
    
    if not test_cases_raw:
        logger.error("❌ 테스트 케이스가 없습니다")
        return {"error": "No test cases"}
    
    logger.info(f"✅ 총 {len(test_cases_raw)}개의 테스트 케이스 발견")
    
    # 실제 Flow와 동일: 첫 번째 TC만 사용 (API 제한)
    if use_first_tc_only:
        first_tc = test_cases_raw[0]
        test_cases = [{
            "input": first_tc.get("input", "") if isinstance(first_tc, dict) else str(first_tc),
            "expected": first_tc.get("expected", "") if isinstance(first_tc, dict) else "",
            "description": first_tc.get("description", "기본 케이스") if isinstance(first_tc, dict) else "케이스 1"
        }]
        logger.info(f"⚠️ 첫 번째 테스트 케이스만 사용 (API 제한) - {test_cases[0]['description']}")
    else:
        test_cases = [
            {
                "input": tc.get("input", "") if isinstance(tc, dict) else str(tc),
                "expected": tc.get("expected", "") if isinstance(tc, dict) else "",
                "description": tc.get("description", f"케이스 {i+1}") if isinstance(tc, dict) else f"케이스 {i+1}"
            }
            for i, tc in enumerate(test_cases_raw)
        ]
        logger.info(f"✅ 모든 테스트 케이스 사용 ({len(test_cases)}개)")
    
    # 3. 제약 조건 확인
    logger.info(f"\n[3단계] 제약 조건")
    logger.info(f"  - 시간 제한: {timeout}초")
    logger.info(f"  - 메모리 제한: {memory_limit}MB")
    logger.info(f"  - 언어: {language}")
    
    # 4. 코드 형식 확인 (실제 Flow와 동일: 코드 정리 없음)
    logger.info(f"\n[4단계] 코드 형식 확인")
    logger.info(f"  - 코드 길이: {len(code)} 문자")
    logger.info(f"  - 코드 바이트 (UTF-8): {len(code.encode('utf-8'))} bytes")
    newline_type = "\\n (LF)" if "\n" in code else "없음"
    logger.info(f"  - 줄바꿈: {newline_type}")
    
    # 마크다운 코드 블록 확인 (경고만)
    if code.strip().startswith("```"):
        logger.warning("  ⚠️ 마크다운 코드 블록이 포함되어 있습니다!")
        logger.warning("  ⚠️ 실제 Flow에서는 코드를 정리하지 않으므로 Judge0 실행이 실패할 수 있습니다.")
        logger.warning("  ⚠️ 테스트를 위해 마크다운 코드 블록을 제거합니다.")
        cleaned_code = clean_code(code)
        logger.info(f"  - 정리된 코드 길이: {len(cleaned_code)} 문자")
    else:
        # 실제 Flow와 동일: 코드 그대로 사용
        cleaned_code = code
        logger.info("  ✅ 순수 코드 (마크다운 코드 블록 없음)")
    
    # 5. Judge0 실행
    logger.info(f"\n[5단계] Judge0 실행")
    logger.info(f"  - 테스트 케이스: {len(test_cases)}개")
    
    client = Judge0Client()
    
    try:
        # Judge0Client.execute_test_cases 사용 (실제 Flow와 동일)
        # 실제 Flow에서는 code_content를 그대로 사용 (정리 없음)
        # 하지만 마크다운 코드 블록이 있으면 제거 (테스트 목적)
        test_case_results = await client.execute_test_cases(
            code=cleaned_code,
            language=language,
            test_cases=[
                {
                    "input": tc["input"],
                    "expected": tc["expected"]
                }
                for tc in test_cases
            ],
            cpu_time_limit=timeout,
            memory_limit=memory_limit
        )
        
        # 6. 결과 출력
        logger.info(f"\n[6단계] Judge0 실행 결과")
        logger.info("=" * 80)
        
        for i, (tc, result) in enumerate(zip(test_cases, test_case_results), 1):
            status_icon = "✅" if result.get("passed") else "❌"
            logger.info(f"\n{status_icon} 테스트 케이스 {i}: {tc['description']}")
            logger.info(f"  입력: {tc['input'][:100]}{'...' if len(tc['input']) > 100 else ''}")
            logger.info(f"  예상 출력: {tc['expected']}")
            logger.info(f"  실제 출력: {result.get('actual', '')}")
            logger.info(f"  통과 여부: {'✅ 통과' if result.get('passed') else '❌ 실패'}")
            logger.info(f"  Judge0 Status: {result.get('status_description', 'Unknown')} (ID: {result.get('status_id', 'N/A')})")
            logger.info(f"  실행 시간: {result.get('time', '0')}초")
            logger.info(f"  메모리 사용: {result.get('memory', '0')}KB")
            
            if result.get("stderr"):
                logger.warning(f"  stderr: {result['stderr']}")
            if result.get("compile_output"):
                logger.warning(f"  컴파일 출력: {result['compile_output']}")
        
        # 7. 점수 계산
        logger.info(f"\n[7단계] 점수 계산")
        logger.info("=" * 80)
        
        # Correctness 점수
        correctness_info = calculate_correctness_score(test_case_results)
        logger.info(f"\n📊 Correctness 점수")
        logger.info(f"  점수: {correctness_info['score']:.1f}점")
        logger.info(f"  통과: {correctness_info['passed']}/{correctness_info['total']}")
        logger.info(f"  통과율: {correctness_info['passed_rate']:.1f}%")
        
        # Performance 점수 (첫 번째 결과 사용)
        if test_case_results:
            first_result = test_case_results[0]
            execution_time = float(first_result.get("time", "0"))
            memory_used_kb = int(first_result.get("memory", "0"))
            memory_used_mb = memory_used_kb / 1024.0
            
            performance_info = calculate_performance_score(
                execution_time=execution_time,
                memory_used_mb=memory_used_mb,
                time_limit_sec=timeout,
                memory_limit_mb=memory_limit
            )
            
            logger.info(f"\n⚡ Performance 점수")
            logger.info(f"  점수: {performance_info['score']:.1f}점")
            logger.info(f"  시간 점수: {performance_info['time_score']:.1f}점 (실행 시간: {execution_time:.3f}초)")
            logger.info(f"  메모리 점수: {performance_info['memory_score']:.1f}점 (메모리: {memory_used_mb:.2f}MB)")
        
        # 최종 결과
        logger.info(f"\n" + "=" * 80)
        logger.info("최종 결과")
        logger.info("=" * 80)
        logger.info(f"✅ Correctness: {correctness_info['score']:.1f}점")
        if test_case_results:
            logger.info(f"⚡ Performance: {performance_info['score']:.1f}점")
            final_score = (correctness_info['score'] * 0.5 + performance_info['score'] * 0.25)
            logger.info(f"📈 종합 점수 (Correctness 50% + Performance 25%): {final_score:.1f}점")
        else:
            logger.info(f"⚡ Performance: 계산 불가")
        
        return {
            "success": True,
            "problem_title": problem_title,
            "test_cases": test_cases,
            "test_case_results": test_case_results,
            "correctness": correctness_info,
            "performance": performance_info if test_case_results else None,
            "final_score": final_score if test_case_results else correctness_info['score']
        }
        
    except Exception as e:
        logger.error(f"❌ Judge0 실행 실패: {str(e)}", exc_info=True)
        return {"error": str(e)}
    finally:
        await client.close()


async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="Judge0 코드 제출 및 평가 테스트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 코드 파일로 제출
  python test_scripts/test_judge0_submit.py --code-file solution.py
  
  # 코드 직접 입력
  python test_scripts/test_judge0_submit.py --code "print('Hello')"
  
  # 모든 TC 사용 (첫 번째만 사용하지 않음)
  python test_scripts/test_judge0_submit.py --code-file solution.py --all-tc
        """
    )
    
    parser.add_argument(
        "--code-file",
        type=str,
        help="제출할 코드 파일 경로"
    )
    
    parser.add_argument(
        "--code",
        type=str,
        help="제출할 코드 (직접 입력)"
    )
    
    parser.add_argument(
        "--spec-id",
        type=int,
        default=None,
        help="문제 스펙 ID (하드코딩 딕셔너리 키, 기본값: 10). --test-cases 사용 시 무시됨"
    )
    
    parser.add_argument(
        "--test-cases",
        type=str,
        help="테스트 케이스 JSON 파일 경로 (예: [{\"input\": \"...\", \"expected\": \"...\"}])"
    )
    
    parser.add_argument(
        "--constraints",
        type=str,
        help="제약 조건 JSON 파일 경로 (예: {\"time_limit_sec\": 1.0, \"memory_limit_mb\": 128})"
    )
    
    parser.add_argument(
        "--language",
        type=str,
        default="python",
        help="프로그래밍 언어 (기본값: python)"
    )
    
    parser.add_argument(
        "--all-tc",
        action="store_true",
        help="모든 테스트 케이스 사용 (기본값: 첫 번째만 사용)"
    )
    
    args = parser.parse_args()
    
    # 코드 가져오기
    code = None
    
    if args.code_file:
        code_path = Path(args.code_file)
        if not code_path.exists():
            logger.error(f"❌ 파일을 찾을 수 없습니다: {args.code_file}")
            sys.exit(1)
        
        try:
            with open(code_path, 'r', encoding='utf-8') as f:
                code = f.read()
            logger.info(f"✅ 코드 파일 읽기 완료: {args.code_file}")
        except Exception as e:
            logger.error(f"❌ 파일 읽기 실패: {str(e)}")
            sys.exit(1)
    
    elif args.code:
        code = args.code
        logger.info("✅ 코드 직접 입력 완료")
    
    else:
        logger.error("❌ --code-file 또는 --code 옵션을 제공해주세요")
        parser.print_help()
        sys.exit(1)
    
    if not code or not code.strip():
        logger.error("❌ 코드가 비어있습니다")
        sys.exit(1)
    
    # 테스트 케이스 가져오기
    test_cases = None
    if args.test_cases:
        import json
        test_cases_path = Path(args.test_cases)
        if not test_cases_path.exists():
            logger.error(f"❌ 테스트 케이스 파일을 찾을 수 없습니다: {args.test_cases}")
            sys.exit(1)
        
        try:
            with open(test_cases_path, 'r', encoding='utf-8') as f:
                test_cases = json.load(f)
            logger.info(f"✅ 테스트 케이스 파일 읽기 완료: {args.test_cases}")
        except Exception as e:
            logger.error(f"❌ 테스트 케이스 파일 읽기 실패: {str(e)}")
            sys.exit(1)
    
    # 제약 조건 가져오기
    constraints = None
    if args.constraints:
        import json
        constraints_path = Path(args.constraints)
        if not constraints_path.exists():
            logger.error(f"❌ 제약 조건 파일을 찾을 수 없습니다: {args.constraints}")
            sys.exit(1)
        
        try:
            with open(constraints_path, 'r', encoding='utf-8') as f:
                constraints = json.load(f)
            logger.info(f"✅ 제약 조건 파일 읽기 완료: {args.constraints}")
        except Exception as e:
            logger.error(f"❌ 제약 조건 파일 읽기 실패: {str(e)}")
            sys.exit(1)
    
    # spec_id 기본값 설정
    if not args.spec_id and not test_cases:
        args.spec_id = 10
        logger.info("⚠️ spec_id가 제공되지 않아 기본값 10 사용")
    
    # Judge0 설정 확인
    if not settings.JUDGE0_API_URL:
        logger.error("❌ JUDGE0_API_URL이 설정되지 않았습니다")
        sys.exit(1)
    
    logger.info(f"Judge0 API URL: {settings.JUDGE0_API_URL}")
    logger.info(f"RapidAPI 사용: {settings.JUDGE0_USE_RAPIDAPI}")
    
    # 실행
    result = await test_submit_code(
        code=code,
        spec_id=args.spec_id,
        test_cases=test_cases,
        constraints=constraints,
        language=args.language,
        use_first_tc_only=not args.all_tc
    )
    
    if "error" in result:
        logger.error(f"❌ 평가 실패: {result['error']}")
        sys.exit(1)
    
    # 성공
    logger.info("\n✅ 평가 완료!")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())

