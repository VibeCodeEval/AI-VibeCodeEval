"""
제출 플로우만 테스트
"""
import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
SESSION_ID = f"submit-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

async def chat(msg, turn):
    print(f"\n[Turn {turn}] {msg[:50]}...")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/chat/message",
            json={
                "session_id": SESSION_ID,
                "exam_id": 1,
                "participant_id": 100,
                "spec_id": 10,
                "message": msg
            }
        )
        result = response.json()
        if result.get('ai_message'):
            print(f"  [OK] AI 응답: {len(result['ai_message'])}자")
        else:
            print(f"  [ERROR] {result.get('error_message')}")
        return result

async def submit(code):
    print(f"\n[제출] 코드 제출...")
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
        print(f"  제출 완료: {result.get('is_submitted')}")
        if result.get('final_scores'):
            scores = result['final_scores']
            print(f"  최종 점수: {scores.get('total_score')} ({scores.get('grade')})")
        return result

async def main():
    print(f"Session: {SESSION_ID}\n")
    
    # 3턴의 대화
    await chat("피보나치 함수를 작성해주세요", 1)
    await asyncio.sleep(2)
    
    await chat("O(n)으로 최적화해주세요", 2)
    await asyncio.sleep(2)
    
    await chat("에지 케이스를 추가해주세요", 3)
    await asyncio.sleep(2)
    
    # 제출
    code = "def fib(n):\\n    return n if n <= 1 else fib(n-1) + fib(n-2)"
    result = await submit(code)
    
    print("\n" + "="*80)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())

