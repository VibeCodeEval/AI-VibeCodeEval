"""
DB에서 문제 정보를 조회하여 Judge0 테스트

[Judge0 호출 최소화]
- DB에서 문제 정보 조회 (TC, solution_code 포함)
- TC 1개만 사용하여 Judge0 호출 최소화
- 정답 코드와 제출 코드 비교 테스트

[테스트 내용]
1. DB에서 문제 정보 조회 (spec_id=10, 외판원 문제)
2. TC 1개 추출
3. 정답 코드로 Judge0 실행 (정답 확인)
4. 제출 코드로 Judge0 실행 (정확성 확인)
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from app.infrastructure.persistence.session import get_db_context
from app.infrastructure.repositories.exam_repository import ExamRepository
from app.domain.queue import create_queue_adapter, JudgeTask, JudgeResult
from app.infrastructure.judge0.client import Judge0Client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 테스트 데이터
SPEC_ID = 10  # 외판원 문제


async def test_judge0_with_db_problem():
    """DB에서 문제 정보를 조회하여 Judge0 테스트"""
    logger.info("=" * 80)
    logger.info("DB 문제 정보 기반 Judge0 테스트 시작")
    logger.info("=" * 80)
    
    try:
        # ========================================================================
        # 1단계: DB에서 문제 정보 조회
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[1단계] DB에서 문제 정보 조회")
        logger.info("=" * 80)
        
        async with get_db_context() as db:
            exam_repo = ExamRepository(db)
            spec = await exam_repo.get_problem_spec_with_problem(SPEC_ID)
            
            if not spec or not spec.problem:
                logger.error(f"❌ 문제 정보 없음 - spec_id: {SPEC_ID}")
                return False
            
            logger.info(f"✅ 문제 정보 조회 성공")
            logger.info(f"   - Problem ID: {spec.problem.id}")
            logger.info(f"   - 제목: {spec.problem.title}")
            logger.info(f"   - Spec ID: {spec.id}")
            
            # checker_json에서 TC와 solution_code 추출
            checker_json = spec.checker_json
            if not checker_json or not isinstance(checker_json, dict):
                logger.error("❌ checker_json이 없거나 dict 형식이 아님")
                return False
            
            test_cases = checker_json.get("test_cases", [])
            solution_code = checker_json.get("solution_code")
            
            if not test_cases:
                logger.error("❌ 테스트 케이스가 없음")
                return False
            
            if not solution_code:
                logger.error("❌ 정답 코드가 없음")
                return False
            
            logger.info(f"✅ 문제 정보 추출 완료")
            logger.info(f"   - 테스트 케이스 개수: {len(test_cases)}개")
            logger.info(f"   - 정답 코드 길이: {len(solution_code)} bytes")
            
            # TC 1개만 사용 (Judge0 호출 최소화)
            first_tc = test_cases[0]
            tc_input = first_tc.get("input", "")
            tc_expected = first_tc.get("expected", "")
            tc_description = first_tc.get("description", "기본 케이스")
            
            logger.info(f"   - 사용할 TC: {tc_description}")
            logger.info(f"   - 입력: {tc_input[:100]}...")
            logger.info(f"   - 예상 출력: {tc_expected}")
        
        # ========================================================================
        # 2단계: 정답 코드로 Judge0 실행 (정답 확인)
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[2단계] 정답 코드로 Judge0 실행 (정답 확인)")
        logger.info("=" * 80)
        
        judge0_client = Judge0Client()
        
        try:
            logger.info("정답 코드 실행 중...")
            solution_result = await judge0_client.execute_code(
                code=solution_code,
                language="python",
                stdin=tc_input,
                expected_output=tc_expected,
                wait=True
            )
            
            status_id = solution_result.get("status", {}).get("id")
            stdout = solution_result.get("stdout", "").strip()
            
            if status_id == 3:  # Accepted
                logger.info(f"✅ 정답 코드 실행 성공")
                logger.info(f"   - 출력: {stdout}")
                logger.info(f"   - 예상 출력: {tc_expected}")
                logger.info(f"   - 일치 여부: {stdout == tc_expected}")
            else:
                logger.warning(f"⚠️ 정답 코드 실행 실패 - status_id: {status_id}")
                logger.warning(f"   - stderr: {solution_result.get('stderr', '')}")
                return False
        except Exception as e:
            logger.error(f"❌ 정답 코드 실행 중 오류: {str(e)}", exc_info=True)
            return False
        finally:
            await judge0_client.close()
        
        # ========================================================================
        # 3단계: DB에서 제출 코드 조회
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[3단계] DB에서 제출 코드 조회")
        logger.info("=" * 80)
        
        async with get_db_context() as db:
            from app.infrastructure.repositories.submission_repository import SubmissionRepository
            submission_repo = SubmissionRepository(db)
            
            # 최신 제출 코드 조회 (spec_id로)
            from sqlalchemy import select, desc
            from app.infrastructure.persistence.models.submissions import Submission
            
            query = select(Submission).where(
                Submission.spec_id == SPEC_ID
            ).order_by(desc(Submission.created_at)).limit(1)
            
            result = await db.execute(query)
            submission = result.scalar_one_or_none()
            
            if not submission or not submission.code_inline:
                logger.warning("⚠️ DB에 제출 코드가 없습니다. 하드코딩된 코드를 사용합니다.")
                # 하드코딩된 코드 사용
                submission_code = """import sys

def tsp(current, visited):
    # 모든 도시를 방문한 경우
    if visited == (1 << N) - 1:
        # 출발 도시(0)로 돌아갈 수 있는 경우
        if W[current][0] != 0:
            return W[current][0]
        else:
            return float('inf')
    
    # 이미 계산된 경우 (Memoization)
    if dp[current][visited] != -1:
        return dp[current][visited]
    
    dp[current][visited] = float('inf')
    for i in range(N):
        # i번 도시를 아직 방문하지 않았고, 가는 길이 있는 경우
        if not (visited & (1 << i)) and W[current][i] != 0:
            dp[current][visited] = min(dp[current][visited], tsp(i, visited | (1 << i)) + W[current][i])
    
    return dp[current][visited]

N = int(sys.stdin.readline())
W = [list(map(int, sys.stdin.readline().split())) for _ in range(N)]
dp = [[-1] * (1 << N) for _ in range(N)]
print(tsp(0, 1))
"""
            else:
                submission_code = submission.code_inline
                logger.info(f"✅ DB에서 제출 코드 조회 성공")
                logger.info(f"   - Submission ID: {submission.id}")
                logger.info(f"   - 언어: {submission.lang}")
                logger.info(f"   - 상태: {submission.status.value}")
                logger.info(f"   - 코드 길이: {len(submission_code)} bytes")
                logger.info(f"   - 코드 미리보기: {submission_code[:100]}...")
        
        # ========================================================================
        # 4단계: 제출 코드로 Judge0 실행 (정확성 확인)
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[4단계] 제출 코드로 Judge0 실행 (정확성 확인)")
        logger.info("=" * 80)
        
        judge0_client = Judge0Client()
        
        try:
            logger.info("제출 코드 실행 중...")
            submission_result = await judge0_client.execute_code(
                code=submission_code,
                language="python",
                stdin=tc_input,
                expected_output=tc_expected,
                wait=True
            )
            
            status_id = submission_result.get("status", {}).get("id")
            stdout = submission_result.get("stdout", "").strip()
            stderr = submission_result.get("stderr", "")
            execution_time = float(submission_result.get("time", "0"))
            memory_used = int(submission_result.get("memory", "0")) * 1024  # KB to bytes
            
            logger.info(f"제출 코드 실행 결과:")
            logger.info(f"   - Status ID: {status_id} ({'Accepted' if status_id == 3 else 'Failed'})")
            logger.info(f"   - 출력: {stdout}")
            logger.info(f"   - 예상 출력: {tc_expected}")
            logger.info(f"   - 일치 여부: {stdout == tc_expected}")
            
            if stderr:
                logger.warning(f"   - stderr: {stderr}")
            
            logger.info(f"   - 실행 시간: {execution_time}초")
            logger.info(f"   - 메모리 사용량: {memory_used / 1024 / 1024:.2f}MB")
            
            # 정확성 점수 계산
            if status_id == 3 and stdout == tc_expected:
                correctness_score = 100.0
                logger.info(f"✅ 정답 확인 - Correctness Score: {correctness_score}")
            else:
                correctness_score = 0.0
                logger.warning(f"❌ 정답 틀림 - Correctness Score: {correctness_score}")
            
            # 성능 점수 계산 (1초 이하, 128MB 이하)
            time_limit = 1.0
            memory_limit_mb = 128
            
            if correctness_score > 0:
                time_score = 100.0 if execution_time <= time_limit else max(0, 100 * (1 - execution_time / time_limit))
                memory_score = 100.0 if memory_used / 1024 / 1024 <= memory_limit_mb else max(0, 100 * (1 - (memory_used / 1024 / 1024) / memory_limit_mb))
                performance_score = (time_score * 0.6 + memory_score * 0.4)
                logger.info(f"✅ 성능 평가 완료 - Performance Score: {performance_score:.2f}")
                logger.info(f"   - 시간 점수: {time_score:.2f} (실행 시간: {execution_time:.3f}초, 제한: {time_limit}초)")
                logger.info(f"   - 메모리 점수: {memory_score:.2f} (사용량: {memory_used / 1024 / 1024:.2f}MB, 제한: {memory_limit_mb}MB)")
            else:
                performance_score = 0.0
                logger.info(f"⚠️ 정답 틀림으로 인해 성능 평가 0점 처리 - Performance Score: {performance_score}")
            
        except Exception as e:
            logger.error(f"❌ 제출 코드 실행 중 오류: {str(e)}", exc_info=True)
            return False
        finally:
            await judge0_client.close()
        
        # ========================================================================
        # 5단계: 최종 요약
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[5단계] 최종 요약")
        logger.info("=" * 80)
        
        async with get_db_context() as db:
            exam_repo = ExamRepository(db)
            spec = await exam_repo.get_problem_spec_with_problem(SPEC_ID)
        
        logger.info("✅ Judge0 테스트 완료!")
        logger.info(f"   - 문제: {spec.problem.title}")
        logger.info(f"   - 테스트 케이스: {tc_description}")
        logger.info(f"   - 정답 코드 실행: 성공")
        logger.info(f"   - 제출 코드 실행: {'성공' if correctness_score > 0 else '실패'}")
        logger.info(f"   - Correctness Score: {correctness_score}")
        logger.info(f"   - Performance Score: {performance_score:.2f}")
        logger.info(f"   - Judge0 호출 횟수: 2회 (정답 코드 1회 + 제출 코드 1회)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 테스트 실패: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(test_judge0_with_db_problem())
    sys.exit(0 if success else 1)


