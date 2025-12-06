"""
간단한 /api/session/{sessionId}/messages 테스트
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_chat_message():
    """간단한 메시지 전송 테스트"""
    print("=" * 80)
    print("간단한 /api/session/{sessionId}/messages 테스트")
    print("=" * 80)
    
    # 1. 세션 시작
    print("\n[1단계] 세션 시작")
    start_response = requests.post(
        f"{BASE_URL}/api/session/start",
        json={
            "examId": 1,
            "participantId": 100,
            "specId": 10
        },
        timeout=60
    )
    
    if start_response.status_code != 200:
        print(f"❌ 세션 시작 실패: {start_response.status_code} - {start_response.text}")
        return False
    
    start_result = start_response.json()
    session_id = start_result.get("id")
    print(f"✅ 세션 시작 완료 - session_id: {session_id}")
    
    # 2. 메시지 전송
    print(f"\n[2단계] 메시지 전송")
    test_data = {
        "role": "USER",
        "content": "안녕하세요, 테스트 메시지입니다."
    }
    
    print(f"\n[요청] POST {BASE_URL}/api/session/{session_id}/messages")
    print(f"데이터: {json.dumps(test_data, ensure_ascii=False, indent=2)}")
    
    try:
        print("   메시지 전송 중... (최대 120초 대기)")
        response = requests.post(
            f"{BASE_URL}/api/session/{session_id}/messages",
            json=test_data,
            timeout=120
        )
        
        print(f"\n[응답] Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 성공!")
            user_msg = result.get('userMessage', {})
            ai_msg = result.get('aiMessage', {})
            session_info = result.get('session', {})
            print(f"   - Session ID: {session_info.get('id')}")
            print(f"   - User Turn: {user_msg.get('turn')}")
            print(f"   - AI Turn: {ai_msg.get('turn')}")
            print(f"   - AI Message: {ai_msg.get('content', '')[:100] if ai_msg.get('content') else 'None'}...")
            print(f"   - Total Tokens: {session_info.get('totalTokens', 0)}")
            return True
        else:
            print(f"❌ 실패!")
            print(f"   - 응답 내용: {response.text[:500]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ 서버 연결 실패 - 서버가 실행 중인지 확인하세요.")
        return False
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_chat_message()
    exit(0 if success else 1)


