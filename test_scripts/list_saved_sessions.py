"""
저장된 세션 목록 확인 및 관리
"""
import json
import subprocess
from datetime import datetime

SESSION_FILE = "data/turn_sessions.json"


def load_sessions():
    """저장된 세션 목록 불러오기"""
    try:
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] 세션 파일을 찾을 수 없습니다: {SESSION_FILE}")
        return []


def check_redis_status(session_id: str):
    """Redis에 데이터가 남아있는지 확인"""
    try:
        # turn_logs 확인
        result = subprocess.run(
            ["docker", "exec", "ai_vibe_redis_dev", "redis-cli", "KEYS", f"turn_logs:{session_id}:*"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=5
        )
        
        turn_logs_count = len([line for line in result.stdout.strip().split('\n') if line.strip()])
        
        # graph_state 확인
        result = subprocess.run(
            ["docker", "exec", "ai_vibe_redis_dev", "redis-cli", "EXISTS", f"graph_state:{session_id}"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=5
        )
        
        state_exists = result.stdout.strip() == "1"
        
        return {
            "turn_logs": turn_logs_count,
            "graph_state": state_exists
        }
    
    except Exception as e:
        return {
            "error": str(e)
        }


def main():
    print("="*80)
    print("저장된 세션 목록")
    print("="*80)
    
    sessions = load_sessions()
    
    if not sessions:
        print("\n저장된 세션이 없습니다.")
        print("\n먼저 test_collect_turns.py를 실행하세요:")
        print("  uv run python test_collect_turns.py")
        return
    
    print(f"\n총 {len(sessions)}개 세션")
    print()
    
    for i, session in enumerate(sessions, 1):
        session_id = session["session_id"]
        created_at = session["created_at"]
        turns = session.get("turns", "?")
        status = session.get("status", "unknown")
        
        print(f"[{i}] {session_id}")
        print(f"    생성: {created_at}")
        print(f"    턴 수: {turns}")
        print(f"    상태: {status}")
        
        # Redis 확인
        redis_status = check_redis_status(session_id)
        
        if "error" in redis_status:
            print(f"    Redis: [ERROR] 확인 불가 ({redis_status['error']})")
        else:
            turn_logs = redis_status["turn_logs"]
            graph_state = redis_status["graph_state"]
            
            if turn_logs > 0 and graph_state:
                print(f"    Redis: [OK] 데이터 존재 (turn_logs: {turn_logs}, graph_state: O)")
            elif turn_logs > 0:
                print(f"    Redis: [WARNING] 부분 데이터 (turn_logs: {turn_logs}, graph_state: X)")
            else:
                print(f"    Redis: [ERROR] 데이터 없음 (만료 또는 삭제됨)")
        
        print()
    
    print("="*80)
    print("사용법")
    print("="*80)
    print("\n최근 세션으로 제출 테스트:")
    print("  uv run python test_submit_from_saved.py")
    
    print("\n특정 세션으로 제출 테스트:")
    print(f"  uv run python test_submit_from_saved.py {sessions[-1]['session_id']}")
    
    print("\n새 턴 수집:")
    print("  uv run python test_collect_turns.py")


if __name__ == "__main__":
    main()

