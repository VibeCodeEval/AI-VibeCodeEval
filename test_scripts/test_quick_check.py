"""
빠른 API 상태 확인 테스트
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_quick():
    """빠른 상태 확인"""
    print("=" * 80)
    print("빠른 API 상태 확인")
    print("=" * 80)
    
    # 1. 헬스체크
    print("\n[1] 헬스체크")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ 서버 실행 중")
        else:
            print(f"   ⚠️ 서버 응답 이상: {response.text[:100]}")
    except Exception as e:
        print(f"   ❌ 서버 연결 실패: {str(e)}")
        return False
    
    # 2. 세션 시작 (빠른 확인)
    print("\n[2] 세션 시작 테스트")
    try:
        response = requests.post(
            f"{BASE_URL}/api/session/start",
            json={"examId": 1, "participantId": 100, "specId": 10},
            timeout=10
        )
        if response.status_code == 200:
            result = response.json()
            session_id = result.get("id")
            print(f"   ✅ 세션 생성 성공 - session_id: {session_id}")
            return session_id
        else:
            print(f"   ❌ 세션 생성 실패: {response.status_code}")
            print(f"   응답: {response.text[:200]}")
            return None
    except requests.exceptions.Timeout:
        print("   ⚠️ 타임아웃 (10초 초과)")
        return None
    except Exception as e:
        print(f"   ❌ 오류: {str(e)}")
        return None

if __name__ == "__main__":
    session_id = test_quick()
    if session_id:
        print(f"\n✅ 기본 테스트 통과 - session_id: {session_id}")
    else:
        print("\n❌ 테스트 실패")

