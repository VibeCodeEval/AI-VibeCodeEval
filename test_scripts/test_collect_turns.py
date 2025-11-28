"""
Phase 1: Turn 수집 테스트
- 2턴 채팅만 진행 (제출 안 함)
- 백그라운드 평가 완료 대기
- session_id 저장
"""
import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
SESSION_FILE = "data/turn_sessions.json"

# 테스트 데이터
EXAM_ID = 1
PARTICIPANT_ID = 100
SPEC_ID = 10

# 1턴 대화 시나리오 (단일 Turn 테스트)
TURNS = [
    "피보나치 수열을 O(n) 시간 복잡도로 계산하는 함수를 작성해주세요. 동적 프로그래밍을 사용하고, 입출력 예시도 제공해주세요."
]


def save_session_id(session_id: str):
    """세션 ID를 파일에 저장"""
    data = {
        "session_id": session_id,
        "created_at": datetime.now().isoformat(),
        "turns": len(TURNS),
        "status": "turns_collected"
    }
    
    try:
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            sessions = json.load(f)
    except FileNotFoundError:
        sessions = []
    
    sessions.append(data)
    
    with open(SESSION_FILE, 'w', encoding='utf-8') as f:
        json.dump(sessions, indent=2, ensure_ascii=False, fp=f)
    
    print(f"\n[OK] Session 저장 완료: {SESSION_FILE}")
    print(f"   Session ID: {session_id}")


async def send_message(client: httpx.AsyncClient, session_id: str, message: str, turn: int) -> dict:
    """채팅 메시지 전송"""
    url = f"{BASE_URL}/api/chat/message"
    payload = {
        "session_id": session_id,
        "exam_id": EXAM_ID,
        "participant_id": PARTICIPANT_ID,
        "spec_id": SPEC_ID,
        "message": message
    }
    
    print(f"\n[Turn {turn}] 메시지 전송: {message[:50]}...")
    
    try:
        response = await client.post(url, json=payload, timeout=60.0)
        response.raise_for_status()
        result = response.json()
        
        ai_message = result.get("ai_message", "")
        print(f"  [OK] 응답 수신: {len(ai_message)}자")
        
        return result
    
    except httpx.TimeoutException:
        print(f"  [ERROR] 타임아웃 (60초)")
        return None
    except httpx.HTTPStatusError as e:
        print(f"  [ERROR] HTTP 에러: {e.response.status_code}")
        print(f"     {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"  [ERROR] 에러: {str(e)}")
        return None


async def check_redis_turn_logs(session_id: str):
    """Redis에 turn_logs가 모두 저장되었는지 확인"""
    print(f"\n[Redis] turn_logs 확인 중...")
    
    # redis-cli로 키 확인
    import subprocess
    
    try:
        # KEYS 명령으로 turn_logs 키 확인
        result = subprocess.run(
            ["docker", "exec", "ai_vibe_redis_dev", "redis-cli", "KEYS", f"turn_logs:{session_id}:*"],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        keys = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        
        print(f"  발견된 turn_logs: {len(keys)}개")
        for key in keys:
            turn_num = key.split(":")[-1]
            print(f"    - Turn {turn_num}")
        
        if len(keys) == len(TURNS):
            print(f"  [OK] 모든 턴 로그 확인 완료!")
            return True
        else:
            print(f"  [WARNING] 일부 턴 로그 누락 (예상: {len(TURNS)}, 실제: {len(keys)})")
            return False
    
    except Exception as e:
        print(f"  [ERROR] Redis 확인 실패: {str(e)}")
        return False


async def check_turn_mapping(session_id: str):
    """Redis에 turn_mapping이 저장되었는지 확인"""
    print(f"\n[Redis] turn_mapping 확인 중...")
    
    import subprocess
    
    try:
        result = subprocess.run(
            ["docker", "exec", "ai_vibe_redis_dev", "redis-cli", "GET", f"turn_mapping:{session_id}"],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        if result.stdout.strip() and result.stdout.strip() != "(nil)":
            mapping = json.loads(result.stdout.strip())
            print(f"  [OK] turn_mapping 확인:")
            for turn, indices in sorted(mapping.items()):
                print(f"    Turn {turn}: messages[{indices['start_msg_idx']}:{indices['end_msg_idx']}]")
            return True
        else:
            print(f"  [ERROR] turn_mapping 없음")
            return False
    
    except Exception as e:
        print(f"  [ERROR] turn_mapping 확인 실패: {str(e)}")
        return False


async def main():
    print("="*80)
    print("Phase 1: Turn 수집 테스트")
    print("="*80)
    
    # 고유 session_id 생성
    session_id = f"turns-collect-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    print(f"\n[Session ID] {session_id}")
    
    async with httpx.AsyncClient() as client:
        # 3턴 채팅
        for i, message in enumerate(TURNS, 1):
            result = await send_message(client, session_id, message, i)
            
            if not result:
                print(f"\n[ERROR] Turn {i} 실패, 테스트 중단")
                return
            
            # 턴 사이 짧은 대기 (Rate Limiting 회피)
            if i < len(TURNS):
                print(f"  [WAIT] 다음 턴까지 5초 대기...")
                await asyncio.sleep(5)
    
    print(f"\n{'='*80}")
    print("모든 턴 전송 완료!")
    print(f"{'='*80}")
    
    # 백그라운드 평가 완료 대기
    print(f"\n⏰ 백그라운드 평가 완료 대기 (20초)...")
    print("   - Turn 1 평가: 예상 5-10초")
    print("   - Turn 2 평가: 예상 5-10초")
    print("   - Turn 3 평가: 예상 5-10초")
    
    for i in range(20, 0, -5):
        print(f"   남은 시간: {i}초...", end='\r')
        await asyncio.sleep(5)
    
    print(f"\n{'='*80}")
    print("백그라운드 평가 완료 예상 시점 도달")
    print(f"{'='*80}")
    
    # Redis 데이터 검증
    turn_logs_ok = await check_redis_turn_logs(session_id)
    turn_mapping_ok = await check_turn_mapping(session_id)
    
    # 세션 저장
    if turn_logs_ok and turn_mapping_ok:
        save_session_id(session_id)
        
        print(f"\n{'='*80}")
        print("[OK] Phase 1 완료!")
        print(f"{'='*80}")
        print(f"\n다음 단계:")
        print(f"  1. Gemini API Quota 회복 대기 (필요 시)")
        print(f"  2. Phase 2 실행:")
        print(f"     uv run python test_submit_from_saved.py --session {session_id}")
    else:
        print(f"\n{'='*80}")
        print("[WARNING] Phase 1 부분 완료 (일부 검증 실패)")
        print(f"{'='*80}")
        print(f"\n문제:")
        if not turn_logs_ok:
            print(f"  - turn_logs 누락 (백그라운드 평가 미완료 또는 실패)")
        if not turn_mapping_ok:
            print(f"  - turn_mapping 누락 (Writer LLM 저장 실패)")
        
        print(f"\n조치:")
        print(f"  1. 서버 로그 확인:")
        print(f"     Get-Content <terminals>\\<터미널>.txt | Select-String \"{session_id}\"")
        print(f"  2. 백그라운드 평가 로그 확인:")
        print(f"     Get-Content <terminals>\\<터미널>.txt | Select-String \"{session_id}.*4\\.\"")
        print(f"  3. API 에러 확인:")
        print(f"     Get-Content <terminals>\\<터미널>.txt | Select-String \"{session_id}.*429\"")


if __name__ == "__main__":
    asyncio.run(main())

