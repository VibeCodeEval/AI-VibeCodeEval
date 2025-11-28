"""
실제 채팅/제출 플로우 테스트 스크립트
로그를 확인하여 그래프 노드 진행 상황 추적
"""
import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
SESSION_ID = f"test-session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

async def test_chat_message(message: str, turn_num: int):
    """일반 채팅 메시지 전송"""
    print(f"\n{'='*80}")
    print(f"[Turn {turn_num}] 일반 채팅 테스트")
    print(f"{'='*80}")
    print(f"메시지: {message}")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/chat/message",
            json={
                "session_id": SESSION_ID,
                "exam_id": 1,
                "participant_id": 100,
                "spec_id": 10,
                "message": message
            }
        )
        
        result = response.json()
        print(f"\n[응답 상태] {response.status_code}")
        print(f"[Turn] {result.get('turn')}")
        
        ai_message = result.get('ai_message')
        if ai_message:
            print(f"[AI 응답 길이] {len(ai_message)}자")
            print(f"[AI 응답 미리보기]\n{ai_message[:300]}...")
        else:
            print(f"[AI 응답] None")
            print(f"[전체 응답]\n{json.dumps(result, ensure_ascii=False, indent=2)}")
        
        print(f"[제출 여부] {result.get('is_submitted')}")
        print(f"[에러] {result.get('error')}")
        
        return result

async def test_submit_code(code: str):
    """코드 제출 테스트"""
    print(f"\n{'='*80}")
    print(f"[제출] 코드 제출 테스트")
    print(f"{'='*80}")
    print(f"코드:\n{code}")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/chat/submit",
            json={
                "session_id": SESSION_ID,
                "exam_id": 1,
                "participant_id": 100,
                "spec_id": 10,
                "code": code,
                "lang": "python"
            }
        )
        
        result = response.json()
        print(f"\n[응답 상태] {response.status_code}")
        print(f"[제출 완료] {result.get('is_submitted')}")
        print(f"[최종 점수]")
        
        final_scores = result.get('final_scores')
        if final_scores:
            print(f"  - 프롬프트 점수: {final_scores.get('prompt_score')}")
            print(f"  - 성능 점수: {final_scores.get('performance_score')}")
            print(f"  - 정확성 점수: {final_scores.get('correctness_score')}")
            print(f"  - 총점: {final_scores.get('total_score')}")
            print(f"  - 등급: {final_scores.get('grade')}")
        
        print(f"[에러] {result.get('error')}")
        
        return result

async def check_turn_logs():
    """Redis에 저장된 turn_logs 확인"""
    print(f"\n{'='*80}")
    print(f"[Redis] Turn Logs 확인")
    print(f"{'='*80}")
    
    # Redis 직접 확인은 Python redis 클라이언트로
    import redis.asyncio as redis
    
    r = await redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    
    # turn_logs 키 패턴 검색
    keys = []
    async for key in r.scan_iter(f"turn_logs:{SESSION_ID}:*"):
        keys.append(key)
    
    print(f"발견된 turn_logs: {len(keys)}개")
    
    for key in sorted(keys):
        turn_num = key.split(":")[-1]
        log = await r.get(key)
        if log:
            log_data = json.loads(log)
            print(f"\n[Turn {turn_num}]")
            print(f"  Intent: {log_data.get('prompt_evaluation_details', {}).get('intent')}")
            print(f"  Score: {log_data.get('prompt_evaluation_details', {}).get('score')}")
            print(f"  Rubrics: {len(log_data.get('prompt_evaluation_details', {}).get('rubrics', []))}개")
    
    await r.aclose()

async def main():
    """전체 테스트 플로우"""
    print(f"{'#'*80}")
    print(f"# 실제 채팅/제출 플로우 테스트")
    print(f"# Session ID: {SESSION_ID}")
    print(f"{'#'*80}")
    
    # Turn 1: 문제 이해 및 힌트 요청
    await test_chat_message(
        "피보나치 수열을 계산하는 함수를 작성해주세요. 어떻게 시작하면 좋을까요?",
        turn_num=1
    )
    
    # 백그라운드 4번 노드 실행 대기
    print("\n[대기] 백그라운드 4번 노드 실행 대기 (3초)...")
    await asyncio.sleep(3)
    
    # Turn 2: 최적화 요청
    await test_chat_message(
        "재귀 방식은 느릴 것 같아요. 동적 프로그래밍으로 O(n) 시간 복잡도로 최적화해주세요.",
        turn_num=2
    )
    
    await asyncio.sleep(3)
    
    # Turn 3: 에지 케이스 처리
    await test_chat_message(
        "n=0이나 n=1일 때의 에지 케이스 처리를 추가해주세요.",
        turn_num=3
    )
    
    await asyncio.sleep(3)
    
    # Redis turn_logs 확인 (중간 체크)
    await check_turn_logs()
    
    # 제출
    code = """def fibonacci(n):
    if n <= 1:
        return n
    
    # 동적 프로그래밍
    dp = [0] * (n + 1)
    dp[1] = 1
    
    for i in range(2, n + 1):
        dp[i] = dp[i-1] + dp[i-2]
    
    return dp[n]
"""
    
    await test_submit_code(code)
    
    # 최종 turn_logs 확인
    await asyncio.sleep(2)
    await check_turn_logs()
    
    print(f"\n{'#'*80}")
    print(f"# 테스트 완료!")
    print(f"{'#'*80}")

if __name__ == "__main__":
    asyncio.run(main())

