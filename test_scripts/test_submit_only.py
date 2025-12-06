"""
코드 제출 Flow만 테스트하는 스크립트
"""
import requests
import logging
import json
from typing import Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"

# 테스트 데이터
EXAM_ID = 1
PARTICIPANT_ID = 100
SPEC_ID = 10  # 외판원 문제

# TSP 문제 해결 코드
TSP_CODE = """import sys
def solve():
    n = int(sys.stdin.readline())
    dist = [list(map(int, sys.stdin.readline().split())) for _ in range(n)]
    
    # 비트마스킹 DP
    INF = float('inf')
    dp = [[INF] * (1 << n) for _ in range(n)]
    dp[0][1] = 0  # 시작점 0, 방문한 도시: 0번만
    
    for mask in range(1, 1 << n):
        for current in range(n):
            if not (mask & (1 << current)):
                continue
            if dp[current][mask] == INF:
                continue
            
            # 다음 도시로 이동
            for next_city in range(n):
                if mask & (1 << next_city):
                    continue
                new_mask = mask | (1 << next_city)
                new_cost = dp[current][mask] + dist[current][next_city]
                if new_cost < dp[next_city][new_mask]:
                    dp[next_city][new_mask] = new_cost
    
    # 마지막 도시에서 시작점으로 돌아오기
    result = INF
    full_mask = (1 << n) - 1
    for last in range(1, n):
        if dp[last][full_mask] != INF:
            result = min(result, dp[last][full_mask] + dist[last][0])
    
    return int(result) if result != INF else -1

if __name__ == "__main__":
    print(solve())
"""


def test_submit_flow():
    """코드 제출 Flow 테스트"""
    logger.info("=" * 80)
    logger.info("코드 제출 Flow 테스트 시작")
    logger.info("=" * 80)
    
    try:
        # ========================================================================
        # 1단계: 세션 생성
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[1단계] 세션 생성")
        logger.info("=" * 80)
        
        start_response = requests.post(
            f"{BASE_URL}/api/session/start",
            json={
                "examId": EXAM_ID,
                "participantId": PARTICIPANT_ID,
                "specId": SPEC_ID
            },
            timeout=60
        )
        
        if start_response.status_code != 200:
            logger.error(f"❌ 세션 생성 실패 - status: {start_response.status_code}")
            logger.error(f"   응답: {start_response.text}")
            return
        
        start_result = start_response.json()
        session_id = start_result.get("id")
        
        logger.info(f"✅ 세션 생성 완료 - session_id: {session_id}")
        logger.info(f"   - examId: {start_result.get('examId')}")
        logger.info(f"   - participantId: {start_result.get('participantId')}")
        logger.info(f"   - specId: {start_result.get('specId')}")
        
        # ========================================================================
        # 2단계: 코드 제출
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[2단계] 코드 제출")
        logger.info("=" * 80)
        
        logger.info("코드 제출 중...")
        logger.info(f"코드 길이: {len(TSP_CODE)} bytes")
        logger.info(f"언어: python")
        
        submit_response = requests.post(
            f"{BASE_URL}/api/session/{session_id}/submit",
            json={
                "code": TSP_CODE,
                "lang": "python"
            },
            timeout=300  # 5분 타임아웃
        )
        
        if submit_response.status_code != 200:
            logger.error(f"❌ 코드 제출 실패 - status: {submit_response.status_code}")
            logger.error(f"   응답: {submit_response.text}")
            return
        
        submit_result = submit_response.json()
        
        logger.info("✅ 코드 제출 완료")
        logger.info(f"   - Submission ID: {submit_result.get('submission_id')}")
        logger.info(f"   - 제출 성공: {submit_result.get('is_submitted')}")
        
        # ========================================================================
        # 3단계: 결과 확인
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[3단계] 결과 확인")
        logger.info("=" * 80)
        
        final_scores = submit_result.get("final_scores")
        if final_scores:
            logger.info("최종 점수:")
            logger.info(f"   - Total: {final_scores.get('total_score')}")
            logger.info(f"   - Prompt: {final_scores.get('prompt_score')}")
            logger.info(f"   - Performance: {final_scores.get('performance_score')}")
            logger.info(f"   - Correctness: {final_scores.get('correctness_score')}")
            logger.info(f"   - Grade: {final_scores.get('grade')}")
        else:
            logger.warning("⚠️ 최종 점수가 없습니다.")
        
        turn_scores = submit_result.get("turn_scores")
        if turn_scores:
            logger.info(f"\n턴별 점수: {len(turn_scores)}개")
            for turn_key, turn_data in turn_scores.items():
                if isinstance(turn_data, dict):
                    score = turn_data.get("turn_score", 0)
                    logger.info(f"   - {turn_key}: {score}")
                else:
                    logger.info(f"   - {turn_key}: {turn_data}")
        else:
            logger.warning("⚠️ 턴별 점수가 없습니다.")
        
        # 에러 확인
        if submit_result.get("error"):
            logger.error(f"❌ 에러 발생: {submit_result.get('error_message')}")
        else:
            logger.info("\n✅ 에러 없음")
        
        # ========================================================================
        # 4단계: 최종 요약
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[4단계] 최종 요약")
        logger.info("=" * 80)
        
        logger.info("✅ 코드 제출 Flow 테스트 완료!")
        logger.info(f"   - Session ID: {session_id}")
        logger.info(f"   - Submission ID: {submit_result.get('submission_id')}")
        if final_scores:
            logger.info(f"   - 최종 점수: {final_scores.get('total_score')}")
            logger.info(f"   - 등급: {final_scores.get('grade')}")
        
    except requests.exceptions.Timeout:
        logger.error("❌ 타임아웃 발생 - 요청 처리 시간이 초과되었습니다.")
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ 요청 실패: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 예외 발생: {str(e)}", exc_info=True)


if __name__ == "__main__":
    test_submit_flow()

