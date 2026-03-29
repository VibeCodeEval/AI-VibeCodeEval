"""
API 테스트 스크립트 - /api/chat/messages

사용법:
    uv run python test_api_chat_messages.py

또는 직접 실행:
    python test_api_chat_messages.py
"""
import requests
import json

# API 기본 URL
API_BASE = "http://localhost:8000/api"

# 테스트 데이터 (setup_web_test_data.py에서 생성된 값 사용)
test_data = {
    "sessionId": 1,
    "participantId": 1,
    "turnId": 1,
    "role": "USER",
    "content": "안녕하세요",
    "context": {
        "problemId": 1,
        "specVersion": 10  # setup_web_test_data.py에서 생성된 spec_id=10
    }
}

def test_chat_messages():
    """POST /api/chat/messages 테스트"""
    url = f"{API_BASE}/chat/messages"
    
    print("=" * 80)
    print("API 테스트: POST /api/chat/messages")
    print("=" * 80)
    print(f"\n요청 URL: {url}")
    print(f"요청 데이터:")
    print(json.dumps(test_data, indent=2, ensure_ascii=False))
    print("\n" + "-" * 80)
    
    try:
        response = requests.post(
            url,
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=120  # 2분 타임아웃
        )
        
        print(f"\n응답 상태 코드: {response.status_code}")
        print(f"응답 헤더: {dict(response.headers)}")
        print("\n응답 본문:")
        
        if response.status_code == 200:
            result = response.json()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            if "aiMessage" in result:
                ai_msg = result["aiMessage"]
                print("\n" + "=" * 80)
                print("✅ 성공!")
                print("=" * 80)
                print(f"AI 응답 턴: {ai_msg.get('turn')}")
                print(f"AI 응답 내용: {ai_msg.get('content', '')[:200]}...")
                print(f"토큰 사용량 (현재 턴): {ai_msg.get('tokenCount', 0)}")
                print(f"토큰 사용량 (전체 누적): {ai_msg.get('totalToken', 0)}")
            else:
                print("⚠️ aiMessage가 응답에 없습니다.")
        else:
            print(response.text)
            print("\n" + "=" * 80)
            print("❌ 실패!")
            print("=" * 80)
            
    except requests.exceptions.Timeout:
        print("\n❌ 타임아웃 발생 (120초 초과)")
    except requests.exceptions.ConnectionError:
        print("\n❌ 연결 오류: 서버가 실행 중인지 확인하세요 (http://localhost:8000)")
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_chat_messages()




