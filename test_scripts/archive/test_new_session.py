"""새 세션으로 단일 Turn 테스트"""
import requests
import json

BASE_URL = "http://localhost:8000"

print("=" * 80)
print("새 세션 단일 Turn 테스트 - tokenCount와 totalToken 확인")
print("=" * 80)

# 기존 세션 ID 1 사용 (Redis 토큰 초기화 후 테스트)
session_id = 1

# 첫 번째 Turn
print("\n[Turn 1] 첫 번째 메시지 전송")
payload1 = {
    "sessionId": session_id,
    "examParticipantId": 2,
    "turnId": 1,
    "role": "USER",
    "content": "안녕하세요",
    "context": {
        "problemId": 1,
        "specVersion": 1
    }
}

try:
    response1 = requests.post(f"{BASE_URL}/api/chat/messages", json=payload1, timeout=120)
    result1 = response1.json()
    
    if response1.status_code == 200:
        ai_msg1 = result1.get("aiMessage", {})
        token_count_1 = ai_msg1.get("tokenCount", 0)
        total_token_1 = ai_msg1.get("totalToken", 0)
        
        print(f"✅ Turn 1 성공")
        print(f"   tokenCount (현재 Turn): {token_count_1}")
        print(f"   totalToken (전체 누적): {total_token_1}")
        print(f"   검증: tokenCount == totalToken? {token_count_1 == total_token_1} (첫 Turn이므로 같아야 함)")
        
        if token_count_1 != total_token_1:
            print(f"   ⚠️ 경고: 첫 Turn인데 tokenCount와 totalToken이 다릅니다!")
        
        # 두 번째 Turn
        print("\n[Turn 2] 두 번째 메시지 전송")
        payload2 = {
            "sessionId": session_id,
            "examParticipantId": 2,
            "turnId": 3,  # Turn 2는 사용자, Turn 3은 AI이므로 다음 사용자는 Turn 3
            "role": "USER",
            "content": "DP에 대해 설명해줘",
            "context": {
                "problemId": 1,
                "specVersion": 1
            }
        }
        
        response2 = requests.post(f"{BASE_URL}/api/chat/messages", json=payload2, timeout=120)
        result2 = response2.json()
        
        if response2.status_code == 200:
            ai_msg2 = result2.get("aiMessage", {})
            token_count_2 = ai_msg2.get("tokenCount", 0)
            total_token_2 = ai_msg2.get("totalToken", 0)
            
            print(f"✅ Turn 2 성공")
            print(f"   tokenCount (현재 Turn): {token_count_2}")
            print(f"   totalToken (전체 누적): {total_token_2}")
            print(f"\n   검증:")
            print(f"   - totalToken == 이전 totalToken + 현재 tokenCount?")
            print(f"   - {total_token_2} == {total_token_1} + {token_count_2}?")
            print(f"   - {total_token_2} == {total_token_1 + token_count_2}? {total_token_2 == total_token_1 + token_count_2}")
            
            if total_token_2 != total_token_1 + token_count_2:
                print(f"   ❌ 오류: totalToken이 이전 totalToken + 현재 tokenCount와 일치하지 않습니다!")
        else:
            print(f"❌ Turn 2 실패: {response2.status_code}")
            print(json.dumps(result2, indent=2, ensure_ascii=False))
    else:
        print(f"❌ Turn 1 실패: {response1.status_code}")
        print(json.dumps(result1, indent=2, ensure_ascii=False))
        
except Exception as e:
    print(f"❌ 오류 발생: {str(e)}")
    import traceback
    traceback.print_exc()

