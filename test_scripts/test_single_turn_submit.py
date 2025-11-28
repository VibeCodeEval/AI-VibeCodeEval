"""
단일 Turn 테스트 (수집 + 제출 통합)
백그라운드 평가 시간 측정 및 Eval Turn Guard 동작 확인
"""
import asyncio
import httpx
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"

async def main():
    session_id = f"single-turn-test-{datetime.now().strftime('%H%M%S')}"
    
    print("="*80)
    print("단일 Turn 테스트 (백그라운드 평가 시간 측정)")
    print("="*80)
    print(f"\n[Session ID] {session_id}\n")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Turn 1: 채팅
        print("[Turn 1] 메시지 전송...")
        turn1_start = time.time()
        
        response = await client.post(
            f"{BASE_URL}/api/chat/message",
            json={
                "session_id": session_id,
                "exam_id": 1,
                "participant_id": 100,
                "spec_id": 10,
                "message": "피보나치 수열을 O(n) 시간 복잡도로 계산하는 함수를 작성해주세요. 동적 프로그래밍을 사용하고, 입출력 예시도 제공해주세요."
            }
        )
        turn1_end = time.time()
        result = response.json()
        
        turn1_response_time = turn1_end - turn1_start
        print(f"  [OK] AI 응답 수신: {len(result.get('ai_message', ''))}자")
        print(f"  [시간] Turn 1 응답 시간: {turn1_response_time:.2f}초\n")
        
        # 백그라운드 평가는 응답 후 시작되므로, 바로 제출하여 Guard가 대기하도록 함
        print("[전략] 즉시 제출하여 Eval Turn Guard의 대기 메커니즘 확인")
        print("  → Guard는 최대 10초 대기하며 0.5초마다 Redis 확인\n")
        
        # 제출 (Eval Turn Guard가 백그라운드 평가 완료를 대기)
        print("[제출] 코드 제출 시작...")
        submit_start = time.time()
        
        code = """def fibonacci(n):
    if n <= 1:
        return n
    
    # 동적 프로그래밍 (O(n))
    dp = [0] * (n + 1)
    dp[1] = 1
    
    for i in range(2, n + 1):
        dp[i] = dp[i-1] + dp[i-2]
    
    return dp[n]

# 예시
print(fibonacci(10))  # 55
"""
        
        response = await client.post(
            f"{BASE_URL}/api/chat/submit",
            json={
                "session_id": session_id,
                "exam_id": 1,
                "participant_id": 100,
                "spec_id": 10,
                "code": code,
                "lang": "python"
            }
        )
        submit_end = time.time()
        result = response.json()
        
        submit_time = submit_end - submit_start
        total_time = submit_end - turn1_start
        
        print(f"  [OK] 제출 완료\n")
        
        print("="*80)
        print("⏱️  시간 측정 결과")
        print("="*80)
        print(f"\n[Turn 1 응답 시간] {turn1_response_time:.2f}초")
        print(f"[제출 처리 시간] {submit_time:.2f}초")
        print(f"  → 이 시간 동안 Eval Turn Guard가 대기 또는 재평가 수행")
        print(f"[전체 소요 시간] {total_time:.2f}초\n")
        
        print("="*80)
        print("제출 결과")
        print("="*80)
        
        # 에러 먼저 확인
        error = result.get("error_message") or result.get("error")
        if error:
            print(f"\n[ERROR] {error}")
            print(f"\n전체 응답:\n{json.dumps(result, ensure_ascii=False, indent=2)}")
            return
        
        is_submitted = result.get("is_submitted", False)
        print(f"\n[제출 상태] {is_submitted}")
        
        turn_scores = result.get("turn_scores")
        if turn_scores is not None:
            print(f"\n[Turn Scores] {len(turn_scores)}개 턴")
            if turn_scores:
                for turn, score_data in sorted(turn_scores.items(), key=lambda x: int(x[0])):
                    if isinstance(score_data, dict):
                        score = score_data.get("turn_score", 0)
                        intent = score_data.get("intent_type", "UNKNOWN")
                        print(f"  Turn {turn}: {score:.2f} (의도: {intent})")
                    else:
                        print(f"  Turn {turn}: {score_data:.2f}")
            else:
                print("  [WARNING] turn_scores 비어있음!")
        else:
            print("\n[Turn Scores] None (is_submitted=False일 때 정상)")
        
        final_scores = result.get("final_scores")
        if final_scores:
            print(f"\n[Final Scores]")
            print(f"  총점: {final_scores.get('total_score', 0):.2f}")
            print(f"  등급: {final_scores.get('grade', 'N/A')}")
            
            details = final_scores.get('details', {})
            if details:
                print(f"\n  세부 점수:")
                print(f"    프롬프트: {details.get('prompt_score', 0):.2f}")
                print(f"    성능: {details.get('performance_score', 0):.2f}")
                print(f"    정확성: {details.get('correctness_score', 0):.2f}")
        
        print("\n" + "="*80)
        print("테스트 완료!")
        print("="*80)

if __name__ == "__main__":
    asyncio.run(main())

