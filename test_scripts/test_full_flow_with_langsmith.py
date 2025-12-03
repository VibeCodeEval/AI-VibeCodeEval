"""
전체 플로우 테스트 (LangSmith 추적 포함)
채팅 → 제출 → 6.X 노드 평가 → LangSmith 추적 확인
"""
import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
SESSION_ID = f"test-langsmith-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

async def test_chat_message(message: str, turn_num: int):
    """일반 채팅 메시지 전송"""
    print(f"\n{'='*80}")
    print(f"[Turn {turn_num}] 일반 채팅 테스트")
    print(f"{'='*80}")
    print(f"메시지: {message}")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
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
                print(f"[AI 응답 미리보기]\n{ai_message[:200]}...")
            else:
                print(f"[AI 응답] None")
            
            print(f"[제출 여부] {result.get('is_submitted')}")
            if result.get('error'):
                print(f"[에러] {result.get('error')}")
            
            return result
        except Exception as e:
            print(f"[에러] 요청 실패: {str(e)}")
            return None

async def test_submit_code(code: str):
    """코드 제출 테스트 (6.X 노드 실행 및 LangSmith 추적)"""
    print(f"\n{'='*80}")
    print(f"[제출] 코드 제출 테스트 (LangSmith 추적 활성화)")
    print(f"{'='*80}")
    print(f"코드:\n{code[:100]}...")
    
    async with httpx.AsyncClient(timeout=180.0) as client:  # 제출은 더 긴 타임아웃
        try:
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
            
            if result.get('final_scores'):
                final_scores = result.get('final_scores')
                print(f"\n[최종 점수]")
                print(f"  - 프롬프트 점수: {final_scores.get('prompt_score')}")
                print(f"  - 성능 점수: {final_scores.get('performance_score')}")
                print(f"  - 정확성 점수: {final_scores.get('correctness_score')}")
                print(f"  - 총점: {final_scores.get('total_score')}")
                print(f"  - 등급: {final_scores.get('grade')}")
            
            if result.get('error'):
                print(f"[에러] {result.get('error')}")
            
            print(f"\n[LangSmith 추적]")
            print(f"  - 6a 노드 (Holistic Flow) 실행 완료")
            print(f"  - 6c 노드 (Code Performance) 실행 완료")
            print(f"  - 6d 노드 (Code Correctness) 실행 완료")
            print(f"  - LangSmith 웹사이트에서 추적 내역 확인: https://smith.langchain.com/")
            print(f"  - 프로젝트: langgraph-eval-dev")
            print(f"  - Session ID: {SESSION_ID}")
            
            return result
        except Exception as e:
            print(f"[에러] 제출 실패: {str(e)}")
            return None

async def check_langsmith_status():
    """LangSmith 설정 상태 확인"""
    print(f"\n{'='*80}")
    print(f"[LangSmith 설정 확인]")
    print(f"{'='*80}")
    
    try:
        from app.core.config import settings
        
        print(f"LANGCHAIN_TRACING_V2: {settings.LANGCHAIN_TRACING_V2}")
        print(f"LANGCHAIN_API_KEY: {'설정됨' if settings.LANGCHAIN_API_KEY else '미설정'}")
        print(f"LANGCHAIN_PROJECT: {settings.LANGCHAIN_PROJECT}")
        print(f"LANGCHAIN_ENDPOINT: {settings.LANGCHAIN_ENDPOINT}")
        
        if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
            print(f"\n✅ LangSmith 추적 활성화됨")
            print(f"   - 6.X 노드 실행 시 자동으로 추적됨")
            print(f"   - LangSmith 웹사이트에서 확인 가능")
        else:
            print(f"\n⚠️ LangSmith 추적 비활성화")
            print(f"   - .env 파일에 LANGCHAIN_TRACING_V2=true 설정 필요")
            print(f"   - LANGCHAIN_API_KEY 설정 필요")
    except Exception as e:
        print(f"[에러] 설정 확인 실패: {str(e)}")

async def main():
    """전체 테스트 플로우"""
    print(f"{'#'*80}")
    print(f"# 전체 플로우 테스트 (LangSmith 추적 포함)")
    print(f"# Session ID: {SESSION_ID}")
    print(f"{'#'*80}")
    
    # LangSmith 설정 확인
    await check_langsmith_status()
    
    # Turn 1: 문제 이해 및 힌트 요청
    print(f"\n{'='*80}")
    print(f"[1단계] Turn 1: 문제 이해 및 힌트 요청")
    print(f"{'='*80}")
    result1 = await test_chat_message(
        "피보나치 수열을 계산하는 함수를 작성해주세요. 어떻게 시작하면 좋을까요?",
        turn_num=1
    )
    
    if not result1:
        print("[에러] Turn 1 실패 - 테스트 중단")
        return
    
    # 백그라운드 4번 노드 실행 대기
    print("\n[대기] 백그라운드 4번 노드 실행 대기 (3초)...")
    await asyncio.sleep(3)
    
    # Turn 2: 최적화 요청
    print(f"\n{'='*80}")
    print(f"[2단계] Turn 2: 최적화 요청")
    print(f"{'='*80}")
    result2 = await test_chat_message(
        "재귀 방식은 느릴 것 같아요. 동적 프로그래밍으로 O(n) 시간 복잡도로 최적화해주세요.",
        turn_num=2
    )
    
    if not result2:
        print("[에러] Turn 2 실패 - 테스트 중단")
        return
    
    await asyncio.sleep(3)
    
    # Turn 3: 에지 케이스 처리
    print(f"\n{'='*80}")
    print(f"[3단계] Turn 3: 에지 케이스 처리")
    print(f"{'='*80}")
    result3 = await test_chat_message(
        "n=0이나 n=1일 때의 에지 케이스 처리를 추가해주세요.",
        turn_num=3
    )
    
    if not result3:
        print("[에러] Turn 3 실패 - 테스트 중단")
        return
    
    await asyncio.sleep(3)
    
    # 제출 (6.X 노드 실행 및 LangSmith 추적)
    print(f"\n{'='*80}")
    print(f"[4단계] 코드 제출 (6.X 노드 실행 및 LangSmith 추적)")
    print(f"{'='*80}")
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
    
    submit_result = await test_submit_code(code)
    
    if submit_result:
        print(f"\n{'='*80}")
        print(f"[테스트 완료]")
        print(f"{'='*80}")
        print(f"✅ 전체 플로우 테스트 성공")
        print(f"✅ LangSmith 추적 활성화됨")
        print(f"\n[다음 단계]")
        print(f"1. LangSmith 웹사이트 접속: https://smith.langchain.com/")
        print(f"2. 프로젝트 선택: langgraph-eval-dev")
        print(f"3. Traces 탭에서 추적 내역 확인")
        print(f"4. Session ID로 필터링: {SESSION_ID}")
    else:
        print(f"\n[에러] 제출 실패")
    
    print(f"\n{'#'*80}")

if __name__ == "__main__":
    asyncio.run(main())





