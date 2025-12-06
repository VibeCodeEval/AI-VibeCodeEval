"""
피보나치 문제 전체 플로우 테스트

[테스트 시나리오]
1. 세션 생성
2. Turn 1: 문제 이해 질문
3. Turn 2: 구현 방식 질문
4. Turn 3: 최적화 질문
5. 코드 제출 (피보나치 수열 계산 코드)
6. 결과 확인
"""
import requests
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"

# 테스트 데이터
EXAM_ID = 1
PARTICIPANT_ID = 100
SPEC_ID = 20  # 피보나치 문제

# 피보나치 문제 해결 코드
FIBONACCI_CODE = """import sys

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
"""


def test_fibonacci_full_flow():
    """피보나치 문제 전체 플로우 테스트"""
    logger.info("=" * 80)
    logger.info("피보나치 문제 전체 플로우 테스트 시작")
    logger.info("=" * 80)
    
    try:
        # ========================================================================
        # 0단계: 세션 생성
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[0단계] 세션 생성")
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
            logger.error(f"❌ 세션 생성 실패: {start_response.status_code} - {start_response.text}")
            return False
        
        start_result = start_response.json()
        session_id = start_result.get("id")
        logger.info(f"✅ 세션 생성 완료 - session_id: {session_id}")
        
        # ========================================================================
        # 1단계: Turn 1 - 문제 이해 질문
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[1단계] Turn 1: 문제 이해 질문")
        logger.info("=" * 80)
        
        turn1_message = "피보나치 수열이 무엇인지 설명해주세요. 그리고 F(0)과 F(1)의 값은 무엇인가요?"
        
        turn1_response = requests.post(
            f"{BASE_URL}/api/session/{session_id}/messages",
            json={
                "role": "USER",
                "content": turn1_message
            },
            timeout=120
        )
        
        if turn1_response.status_code != 200:
            logger.error(f"❌ Turn 1 전송 실패: {turn1_response.status_code} - {turn1_response.text}")
            return False
        
        turn1_result = turn1_response.json()
        ai_message = turn1_result.get('aiMessage', {}).get('content', '')
        logger.info(f"✅ Turn 1 전송 완료")
        logger.info(f"   - Turn: {turn1_result.get('userMessage', {}).get('turn')}")
        logger.info(f"   - AI 응답: {ai_message[:100]}...")
        
        time.sleep(1)  # 상태 업데이트 대기
        
        # ========================================================================
        # 2단계: Turn 2 - 구현 방식 질문
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[2단계] Turn 2: 구현 방식 질문")
        logger.info("=" * 80)
        
        turn2_message = "피보나치 수열을 계산하는 방법에는 재귀와 반복 두 가지가 있다고 들었어요. 각각의 장단점을 알려주세요."
        
        turn2_response = requests.post(
            f"{BASE_URL}/api/session/{session_id}/messages",
            json={
                "role": "USER",
                "content": turn2_message
            },
            timeout=120
        )
        
        if turn2_response.status_code != 200:
            logger.error(f"❌ Turn 2 전송 실패: {turn2_response.status_code} - {turn2_response.text}")
            return False
        
        turn2_result = turn2_response.json()
        ai_message = turn2_result.get('aiMessage', {}).get('content', '')
        logger.info(f"✅ Turn 2 전송 완료")
        logger.info(f"   - Turn: {turn2_result.get('userMessage', {}).get('turn')}")
        logger.info(f"   - AI 응답: {ai_message[:100]}...")
        
        time.sleep(1)  # 상태 업데이트 대기
        
        # ========================================================================
        # 3단계: Turn 3 - 최적화 질문
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[3단계] Turn 3: 최적화 질문")
        logger.info("=" * 80)
        
        turn3_message = "반복 방식으로 구현할 때 시간 복잡도는 어떻게 되나요?"
        
        turn3_response = requests.post(
            f"{BASE_URL}/api/session/{session_id}/messages",
            json={
                "role": "USER",
                "content": turn3_message
            },
            timeout=120
        )
        
        if turn3_response.status_code != 200:
            logger.error(f"❌ Turn 3 전송 실패: {turn3_response.status_code} - {turn3_response.text}")
            return False
        
        turn3_result = turn3_response.json()
        ai_message = turn3_result.get('aiMessage', {}).get('content', '')
        logger.info(f"✅ Turn 3 전송 완료")
        logger.info(f"   - Turn: {turn3_result.get('userMessage', {}).get('turn')}")
        logger.info(f"   - AI 응답: {ai_message[:100]}...")
        
        time.sleep(2)  # 상태 업데이트 대기
        
        # ========================================================================
        # 4단계: 코드 제출
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[4단계] 코드 제출")
        logger.info("=" * 80)
        
        logger.info("코드 제출 중...")
        logger.info(f"코드 길이: {len(FIBONACCI_CODE)} bytes")
        logger.info(f"언어: python")
        
        submit_response = requests.post(
            f"{BASE_URL}/api/session/{session_id}/submit",
            json={
                "code": FIBONACCI_CODE,
                "lang": "python"
            },
            timeout=300  # 5분 타임아웃
        )
        
        if submit_response.status_code != 200:
            logger.error(f"❌ 코드 제출 실패 - status: {submit_response.status_code}")
            logger.error(f"   응답: {submit_response.text}")
            return False
        
        submit_result = submit_response.json()
        
        logger.info("✅ 코드 제출 완료")
        logger.info(f"   - Submission ID: {submit_result.get('submission_id')}")
        logger.info(f"   - 제출 성공: {submit_result.get('is_submitted')}")
        
        # ========================================================================
        # 5단계: 결과 확인
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[5단계] 결과 확인")
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
        # 6단계: 최종 요약
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("[6단계] 최종 요약")
        logger.info("=" * 80)
        
        logger.info("✅ 피보나치 문제 전체 플로우 테스트 완료!")
        logger.info(f"   - Session ID: {session_id}")
        logger.info(f"   - Submission ID: {submit_result.get('submission_id')}")
        logger.info(f"   - 채팅 턴: 3개")
        if final_scores:
            logger.info(f"   - 최종 점수: {final_scores.get('total_score')}")
            logger.info(f"   - 등급: {final_scores.get('grade')}")
        
        return True
        
    except requests.exceptions.Timeout:
        logger.error("❌ 타임아웃 발생 - 요청 처리 시간이 초과되었습니다.")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ 요청 실패: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"❌ 예외 발생: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    test_fibonacci_full_flow()

