"""
외판원 문제(TSP) 전체 플로우 테스트

[테스트 시나리오]
1. 세션 생성
2. Turn 1: 전략 수립 질문
3. Turn 2: 알고리즘 질문
4. Turn 3: 구현 방식 질문
5. 코드 제출 (외판원 문제 해결 코드)
6. 결과 확인:
   - TC 1개만 사용 (DB에서)
   - 정답 확인
   - 정답 맞으면 성능 체크
   - 정답 틀리면 성능 0점
"""
import asyncio
import sys
from pathlib import Path
import requests
import json
import time

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API 기본 URL
BASE_URL = "http://localhost:8000"

# 테스트 데이터
EXAM_ID = 1
PARTICIPANT_ID = 100
SPEC_ID = 10  # 외판원 문제


def test_submit_tsp_full_flow():
    """외판원 문제 전체 플로우 테스트"""
    logger.info("=" * 80)
    logger.info("외판원 문제(TSP) 전체 플로우 테스트 시작")
    logger.info("=" * 80)
    
    try:
        # ========================================================================
        # 0단계: 세션 생성
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[0단계] 세션 생성")
        logger.info("=" * 80)
        
        # 세션 시작 API 호출
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
            logger.error(f"❌ 세션 생성 실패: {start_response.status_code} - {start_response.text}")
            return False
        
        start_result = start_response.json()
        session_id = start_result.get("id")
        logger.info(f"✅ 세션 생성 완료 - session_id: {session_id}")
        
        # ========================================================================
        # 1단계: 전략 수립 질문 (Turn 1)
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[1단계] Turn 1: 전략 수립 질문")
        logger.info("=" * 80)
        
        turn1_message = (
            "외판원 순회(TSP) 문제를 풀려고 합니다. N이 16 이하로 작다는 점에 착안하여, "
            "완전 탐색 대신 **비트마스킹을 활용한 DP(Dynamic Programming)**로 접근하고 싶습니다. "
            "상태를 dp[current_city][visited_bitmask]로 정의할 때, 점화식 수립을 위한 힌트를 주세요. (코드는 주지 마세요.)"
        )
        
        turn1_response = requests.post(
            f"{BASE_URL}/api/session/{session_id}/messages",
            json={
                "role": "USER",
                "content": turn1_message
            },
            timeout=60
        )
        
        if turn1_response.status_code != 200:
            logger.error(f"❌ Turn 1 전송 실패: {turn1_response.status_code} - {turn1_response.text}")
            return False
        
        turn1_result = turn1_response.json()
        turn1_user_msg = turn1_result.get("userMessage", {})
        turn1_ai_msg = turn1_result.get("aiMessage", {})
        turn1_turn = turn1_user_msg.get("turn") if turn1_user_msg else None
        ai_message = turn1_ai_msg.get('content', '') if turn1_ai_msg else ''
        logger.info(f"✅ Turn 1 전송 완료")
        logger.info(f"   - Turn: {turn1_turn}")
        logger.info(f"   - AI 응답: {ai_message[:150] if ai_message else 'N/A'}...")
        
        # AI 응답이 완료될 때까지 대기 (최대 30초)
        if not ai_message:
            logger.warning("⚠️ AI 응답이 없습니다. 대기 중...")
            for i in range(30):
                time.sleep(1)
                # DB에서 메시지 확인 (선택적)
                # 여기서는 단순히 대기만 함
                if i % 5 == 0:
                    logger.info(f"   대기 중... ({i+1}/30초)")
        
        time.sleep(2)  # 추가 안정화 대기
        
        # ========================================================================
        # 2단계: 알고리즘 질문 (Turn 2)
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[2단계] Turn 2: 알고리즘 질문")
        logger.info("=" * 80)
        
        turn2_message = "비트마스킹을 썼을 때와 안썼을 때 시간복잡도 차이를 알려주세요"
        
        turn2_response = requests.post(
            f"{BASE_URL}/api/session/{session_id}/messages",
            json={
                "role": "USER",
                "content": turn2_message
            },
            timeout=60
        )
        
        if turn2_response.status_code != 200:
            logger.error(f"❌ Turn 2 전송 실패: {turn2_response.status_code} - {turn2_response.text}")
            return False
        
        turn2_result = turn2_response.json()
        turn2_user_msg = turn2_result.get("userMessage", {})
        turn2_ai_msg = turn2_result.get("aiMessage", {})
        turn2_turn = turn2_user_msg.get("turn") if turn2_user_msg else None
        ai_message = turn2_ai_msg.get('content', '') if turn2_ai_msg else ''
        logger.info(f"✅ Turn 2 전송 완료")
        logger.info(f"   - Turn: {turn2_turn}")
        logger.info(f"   - AI 응답: {ai_message[:150] if ai_message else 'N/A'}...")
        
        # AI 응답이 완료될 때까지 대기 (최대 30초)
        if not ai_message:
            logger.warning("⚠️ AI 응답이 없습니다. 대기 중...")
            for i in range(30):
                time.sleep(1)
                if i % 5 == 0:
                    logger.info(f"   대기 중... ({i+1}/30초)")
        
        time.sleep(2)  # 추가 안정화 대기
        
        # ========================================================================
        # 3단계: 구현 방식 질문 (Turn 3)
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[3단계] Turn 3: 구현 방식 질문")
        logger.info("=" * 80)
        
        turn3_message = "dp 이외에 구현 방식을 알려주세요"
        
        turn3_response = requests.post(
            f"{BASE_URL}/api/session/{session_id}/messages",
            json={
                "role": "USER",
                "content": turn3_message
            },
            timeout=60
        )
        
        if turn3_response.status_code != 200:
            logger.error(f"❌ Turn 3 전송 실패: {turn3_response.status_code} - {turn3_response.text}")
            return False
        
        turn3_result = turn3_response.json()
        turn3_user_msg = turn3_result.get("userMessage", {})
        turn3_ai_msg = turn3_result.get("aiMessage", {})
        turn3_turn = turn3_user_msg.get("turn") if turn3_user_msg else None
        ai_message = turn3_ai_msg.get('content', '') if turn3_ai_msg else ''
        logger.info(f"✅ Turn 3 전송 완료")
        logger.info(f"   - Turn: {turn3_turn}")
        logger.info(f"   - AI 응답: {ai_message[:150] if ai_message else 'N/A'}...")
        
        # AI 응답이 완료될 때까지 대기 (최대 30초)
        if not ai_message:
            logger.warning("⚠️ AI 응답이 없습니다. 대기 중...")
            for i in range(30):
                time.sleep(1)
                if i % 5 == 0:
                    logger.info(f"   대기 중... ({i+1}/30초)")
        
        time.sleep(2)  # 추가 안정화 대기 - 제출 전 최종 대기
        
        # ========================================================================
        # 4단계: 코드 제출 (외판원 문제 해결 코드)
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[4단계] 코드 제출")
        logger.info("=" * 80)
        
        # 외판원 문제 해결 코드 (비트마스킹 DP)
        tsp_code = """import sys

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
        
        logger.info("코드 제출 중...")
        logger.info(f"코드 길이: {len(tsp_code)} bytes")
        logger.info(f"언어: python")
        logger.info(f"시간 제한: 1초 이하")
        logger.info(f"메모리 제한: 128MB")
        
        submit_response = requests.post(
            f"{BASE_URL}/api/chat/submit",
            json={
                "exam_id": EXAM_ID,
                "participant_id": PARTICIPANT_ID,
                "spec_id": SPEC_ID,
                "session_id": f"session_{session_id}",  # Redis 형식으로 변환
                "code": tsp_code,
                "lang": "python"
            },
            timeout=300  # 5분 타임아웃 (평가 시간 고려)
        )
        
        if submit_response.status_code != 200:
            logger.error(f"❌ 코드 제출 실패: {submit_response.status_code} - {submit_response.text}")
            return False
        
        submit_result = submit_response.json()
        
        if submit_result.get("error"):
            logger.error(f"❌ 코드 제출 오류: {submit_result.get('error_message')}")
            return False
        
        logger.info("✅ 코드 제출 완료")
        logger.info(f"   - Submission ID: {submit_result.get('submission_id')}")
        logger.info(f"   - 제출 성공: {submit_result.get('is_submitted')}")
        
        final_scores = submit_result.get("final_scores")
        if final_scores:
            logger.info(f"   - 최종 점수:")
            logger.info(f"     * Total: {final_scores.get('total_score', 'N/A')}")
            logger.info(f"     * Prompt: {final_scores.get('prompt_score', 'N/A')}")
            logger.info(f"     * Performance: {final_scores.get('performance_score', 'N/A')}")
            logger.info(f"     * Correctness: {final_scores.get('correctness_score', 'N/A')}")
            logger.info(f"     * Grade: {final_scores.get('grade', 'N/A')}")
            
            # Correctness 상세 정보
            correctness_details = final_scores.get("correctness_details")
            if correctness_details:
                logger.info(f"   - Correctness 상세:")
                logger.info(f"     * 테스트 케이스 통과: {correctness_details.get('test_cases_passed', 'N/A')}/{correctness_details.get('test_cases_total', 'N/A')}")
                logger.info(f"     * 통과율: {correctness_details.get('pass_rate', 'N/A')}%")
            
            # Performance 상세 정보
            performance_details = final_scores.get("performance_details")
            if performance_details:
                logger.info(f"   - Performance 상세:")
                logger.info(f"     * 실행 시간: {performance_details.get('execution_time', 'N/A')}초")
                logger.info(f"     * 메모리 사용량: {performance_details.get('memory_used_mb', 'N/A')}MB")
                logger.info(f"     * 성능 평가 건너뜀: {performance_details.get('skip_performance', False)}")
                if performance_details.get("skip_reason"):
                    logger.info(f"     * 건너뛴 이유: {performance_details.get('skip_reason')}")
        
        turn_scores = submit_result.get("turn_scores")
        if turn_scores:
            logger.info(f"   - 턴별 점수: {turn_scores}")
        
        submission_id = submit_result.get("submission_id")
        if not submission_id:
            logger.error("❌ Submission ID가 없습니다.")
            return False
        
        # ========================================================================
        # 5단계: 결과 검증
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[5단계] 결과 검증")
        logger.info("=" * 80)
        
        # 정답 확인
        correctness_score = final_scores.get("correctness_score", 0) if final_scores else 0
        if correctness_score > 0:
            logger.info(f"✅ 정답 확인: Correctness Score = {correctness_score}")
            logger.info("   → 성능 평가 진행됨")
        else:
            logger.warning(f"⚠️ 정답 틀림: Correctness Score = {correctness_score}")
            logger.warning("   → 성능 평가 0점 처리 예상")
        
        # 성능 점수 확인
        performance_score = final_scores.get("performance_score", 0) if final_scores else 0
        if correctness_score > 0:
            if performance_score > 0:
                logger.info(f"✅ 성능 평가 완료: Performance Score = {performance_score}")
            else:
                logger.warning(f"⚠️ 성능 평가 실패: Performance Score = {performance_score}")
        else:
            if performance_score == 0:
                logger.info(f"✅ 예상대로 성능 0점 처리됨: Performance Score = {performance_score}")
            else:
                logger.warning(f"⚠️ 정답 틀렸는데 성능 점수가 있음: Performance Score = {performance_score}")
        
        # ========================================================================
        # 6단계: 최종 요약
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[6단계] 최종 요약")
        logger.info("=" * 80)
        
        logger.info("✅ 전체 플로우 테스트 완료!")
        logger.info(f"   - Session ID: {session_id}")
        logger.info(f"   - Submission ID: {submission_id}")
        logger.info(f"   - 채팅 턴: 3개")
        logger.info(f"   - 최종 점수: {final_scores.get('total_score', 'N/A') if final_scores else 'N/A'}")
        logger.info(f"   - 등급: {final_scores.get('grade', 'N/A') if final_scores else 'N/A'}")
        
        return True
        
    except requests.exceptions.Timeout:
        logger.error("❌ 요청 타임아웃 발생")
        return False
    except requests.exceptions.ConnectionError:
        logger.error("❌ 서버 연결 실패 - 서버가 실행 중인지 확인하세요.")
        return False
    except Exception as e:
        logger.error(f"❌ 테스트 실패: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    success = test_submit_tsp_full_flow()
    sys.exit(0 if success else 1)

