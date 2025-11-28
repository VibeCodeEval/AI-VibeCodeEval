"""
Phase 2: 저장된 세션에서 제출만 테스트
- Redis에서 turn_logs, turn_mapping 불러오기
- graph_state 확인
- 제출 API 호출
- turn_scores 검증
"""
import asyncio
import httpx
import json
import sys
import subprocess
from datetime import datetime

BASE_URL = "http://localhost:8000"
SESSION_FILE = "data/turn_sessions.json"

# 제출할 코드 (피보나치 예제)
SUBMIT_CODE = """def fibonacci(n):
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        return fibonacci(n - 1) + fibonacci(n - 2)
"""


def load_sessions():
    """저장된 세션 목록 불러오기"""
    try:
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] 세션 파일을 찾을 수 없습니다: {SESSION_FILE}")
        print(f"   먼저 test_collect_turns.py를 실행하세요.")
        return []


def get_session_id(session_arg=None):
    """세션 ID 가져오기 (인자 또는 최근 세션)"""
    sessions = load_sessions()
    
    if not sessions:
        return None
    
    if session_arg:
        # 명령줄 인자로 지정된 세션
        for s in sessions:
            if s["session_id"] == session_arg:
                return s["session_id"]
        print(f"[WARNING] 세션을 찾을 수 없습니다: {session_arg}")
        return None
    else:
        # 최근 세션 사용
        latest = sessions[-1]
        return latest["session_id"]


async def verify_redis_data(session_id: str):
    """Redis 데이터 검증"""
    print(f"\n[Redis] 데이터 검증...")
    
    issues = []
    
    # 1. turn_logs 확인
    result = subprocess.run(
        ["docker", "exec", "ai_vibe_redis_dev", "redis-cli", "KEYS", f"turn_logs:{session_id}:*"],
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    
    turn_logs_keys = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
    print(f"  turn_logs: {len(turn_logs_keys)}개")
    
    if len(turn_logs_keys) == 0:
        issues.append("turn_logs 없음 - 백그라운드 평가 미완료")
    else:
        for key in turn_logs_keys:
            turn_num = key.split(":")[-1]
            print(f"    [OK] Turn {turn_num}")
    
    # 2. turn_mapping 확인
    result = subprocess.run(
        ["docker", "exec", "ai_vibe_redis_dev", "redis-cli", "GET", f"turn_mapping:{session_id}"],
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    
    if result.stdout.strip() and result.stdout.strip() != "(nil)":
        mapping = json.loads(result.stdout.strip())
        print(f"  turn_mapping: {len(mapping)}개 턴")
        for turn, indices in sorted(mapping.items()):
            print(f"    [OK] Turn {turn}: [{indices['start_msg_idx']}:{indices['end_msg_idx']}]")
    else:
        issues.append("turn_mapping 없음")
        print(f"  [ERROR] turn_mapping 없음")
    
    # 3. graph_state 확인
    result = subprocess.run(
        ["docker", "exec", "ai_vibe_redis_dev", "redis-cli", "GET", f"graph_state:{session_id}"],
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    
    if result.stdout.strip() and result.stdout.strip() != "(nil)":
        state = json.loads(result.stdout.strip())
        print(f"  graph_state:")
        print(f"    current_turn: {state.get('current_turn')}")
        print(f"    messages: {len(state.get('messages', []))}개")
        print(f"    is_submitted: {state.get('is_submitted', False)}")
        
        # 이미 제출된 세션인지 확인
        if state.get('is_submitted'):
            issues.append("이미 제출된 세션")
            print(f"    [WARNING] 이미 제출됨!")
    else:
        issues.append("graph_state 없음")
        print(f"  [ERROR] graph_state 없음")
    
    return issues


async def submit_code(client: httpx.AsyncClient, session_id: str, code: str) -> dict:
    """코드 제출"""
    url = f"{BASE_URL}/api/chat/submit"
    payload = {
        "session_id": session_id,
        "exam_id": 1,
        "participant_id": 100,
        "spec_id": 10,
        "code": code,
        "lang": "python"
    }
    
    print(f"\n[SUBMIT] 코드 제출 중...")
    print(f"  코드 길이: {len(code)}자")
    
    try:
        response = await client.post(url, json=payload, timeout=120.0)
        response.raise_for_status()
        result = response.json()
        
        print(f"  [OK] 제출 완료!")
        
        return result
    
    except httpx.TimeoutException:
        print(f"  [ERROR] 타임아웃 (120초)")
        return None
    except httpx.HTTPStatusError as e:
        print(f"  [ERROR] HTTP 에러: {e.response.status_code}")
        print(f"     {e.response.text[:500]}")
        return None
    except Exception as e:
        print(f"  [ERROR] 에러: {str(e)}")
        return None


def analyze_result(result: dict, session_id: str):
    """결과 분석 및 출력"""
    print(f"\n{'='*80}")
    print("제출 결과 분석")
    print(f"{'='*80}")
    
    # 1. 기본 정보
    is_submitted = result.get("is_submitted", False)
    print(f"\n[OK] 제출 상태: {is_submitted}")
    
    # 2. turn_scores 분석
    turn_scores = result.get("turn_scores", {})
    print(f"\n[Turn Scores] {len(turn_scores)}개 턴")
    
    if turn_scores:
        for turn, score in sorted(turn_scores.items(), key=lambda x: int(x[0])):
            print(f"  Turn {turn}: {score:.2f}")
    else:
        print(f"  [WARNING] turn_scores 비어있음!")
    
    # 3. final_scores 분석
    final_scores = result.get("final_scores", {})
    
    if final_scores:
        print(f"\n[Final Scores]")
        print(f"  총점: {final_scores.get('total_score', 0):.2f}")
        print(f"  등급: {final_scores.get('grade', 'N/A')}")
        
        # 세부 점수
        details = final_scores.get('details', {})
        if details:
            print(f"\n  세부 점수:")
            print(f"    프롬프트: {details.get('prompt_score', 0):.2f}")
            print(f"    성능: {details.get('performance_score', 0):.2f}")
            print(f"    정확성: {details.get('correctness_score', 0):.2f}")
            print(f"    전체 흐름: {details.get('holistic_score', 0):.2f}")
    else:
        print(f"\n[WARNING] final_scores 없음!")
    
    # 4. Redis 데이터와 비교
    print(f"\n{'='*80}")
    print("Redis 데이터 비교")
    print(f"{'='*80}")
    
    result_redis = subprocess.run(
        ["docker", "exec", "ai_vibe_redis_dev", "redis-cli", "KEYS", f"turn_logs:{session_id}:*"],
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    
    redis_turns = len([line for line in result_redis.stdout.strip().split('\n') if line.strip()])
    api_turns = len(turn_scores)
    
    print(f"  Redis turn_logs: {redis_turns}개")
    print(f"  API turn_scores: {api_turns}개")
    
    if redis_turns == api_turns:
        print(f"  [OK] 일치!")
    else:
        print(f"  [WARNING] 불일치! (Redis: {redis_turns}, API: {api_turns})")
        
        # 누락된 턴 찾기
        redis_turn_nums = set()
        for line in result_redis.stdout.strip().split('\n'):
            if line.strip():
                turn_num = line.strip().split(":")[-1]
                redis_turn_nums.add(turn_num)
        
        api_turn_nums = set(turn_scores.keys())
        
        missing_in_api = redis_turn_nums - api_turn_nums
        if missing_in_api:
            print(f"  API에서 누락: {sorted(missing_in_api)}")
        
        missing_in_redis = api_turn_nums - redis_turn_nums
        if missing_in_redis:
            print(f"  Redis에서 누락: {sorted(missing_in_redis)}")
    
    # 5. 종합 판단
    print(f"\n{'='*80}")
    print("종합 판단")
    print(f"{'='*80}")
    
    all_ok = True
    
    if not is_submitted:
        print(f"[ERROR] 제출 실패")
        all_ok = False
    
    if not turn_scores:
        print(f"[ERROR] turn_scores 비어있음")
        all_ok = False
    elif redis_turns != api_turns:
        print(f"[WARNING] turn_scores 불완전 ({api_turns}/{redis_turns})")
        all_ok = False
    
    if not final_scores:
        print(f"[ERROR] final_scores 없음")
        all_ok = False
    
    if all_ok:
        print(f"[OK] 모든 검증 통과!")
    else:
        print(f"[WARNING] 일부 문제 발견")
        print(f"\n서버 로그 확인 권장:")
        print(f"  Get-Content <terminals>\\<터미널>.txt | Select-String \"{session_id}\"")


async def main():
    print("="*80)
    print("Phase 2: 저장된 세션에서 제출 테스트")
    print("="*80)
    
    # 세션 ID 가져오기
    session_arg = None
    if len(sys.argv) > 1:
        if sys.argv[1] == "--session" and len(sys.argv) > 2:
            session_arg = sys.argv[2]
        else:
            session_arg = sys.argv[1]
    
    session_id = get_session_id(session_arg)
    
    if not session_id:
        print(f"\n사용법:")
        print(f"  uv run python test_submit_from_saved.py")
        print(f"  uv run python test_submit_from_saved.py --session <session-id>")
        print(f"  uv run python test_submit_from_saved.py <session-id>")
        
        sessions = load_sessions()
        if sessions:
            print(f"\n사용 가능한 세션:")
            for s in sessions[-5:]:  # 최근 5개만
                print(f"  - {s['session_id']} ({s['created_at']})")
        
        return
    
    print(f"\n[Session ID] {session_id}")
    
    # Redis 데이터 검증
    issues = await verify_redis_data(session_id)
    
    if issues:
        print(f"\n{'='*80}")
        print("[WARNING] Redis 데이터 문제 발견")
        print(f"{'='*80}")
        
        for issue in issues:
            print(f"  - {issue}")
        
        print(f"\n계속 진행하시겠습니까? (y/n): ", end='')
        # 자동으로 진행 (테스트용)
        print("y (자동 진행)")
        # choice = input().strip().lower()
        # if choice != 'y':
        #     print(f"중단됨")
        #     return
    
    # 제출 실행
    async with httpx.AsyncClient() as client:
        result = await submit_code(client, session_id, SUBMIT_CODE)
        
        if not result:
            print(f"\n[ERROR] 제출 실패")
            return
    
    # 결과 분석
    analyze_result(result, session_id)
    
    print(f"\n{'='*80}")
    print("[OK] Phase 2 완료!")
    print(f"{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())

