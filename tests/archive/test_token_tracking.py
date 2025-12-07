"""
토큰 사용량 추적 테스트 스크립트
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
SESSION_ID = f"test-session-{int(datetime.now().timestamp() * 1000)}"


def test_chat_with_tokens():
    """일반 채팅 메시지 전송 및 토큰 사용량 확인"""
    print(f"\n{'='*60}")
    print("테스트 1: 일반 채팅 메시지 전송 (토큰 사용량 확인)")
    print(f"{'='*60}")
    
    # 메시지 전송
    url = f"{BASE_URL}/api/chat/message"
    payload = {
        "session_id": SESSION_ID,
        "exam_id": 1,
        "participant_id": 100,
        "spec_id": 1,
        "message": "DP에 대해 설명해줘"
    }
    
    print(f"\n[요청] POST {url}")
    print(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        result = response.json()
        
        print(f"\n[응답] Status: {response.status_code}")
        print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        # 토큰 사용량 확인
        if "chat_tokens" in result:
            chat_tokens = result["chat_tokens"]
            print(f"\n✅ 채팅 검사 토큰 (chat_tokens):")
            print(f"   - Prompt tokens: {chat_tokens.get('prompt_tokens', 0)}")
            print(f"   - Completion tokens: {chat_tokens.get('completion_tokens', 0)}")
            print(f"   - Total tokens: {chat_tokens.get('total_tokens', 0)}")
        else:
            print("\n❌ chat_tokens가 응답에 없습니다!")
        
        if "eval_tokens" in result and result["eval_tokens"]:
            eval_tokens = result["eval_tokens"]
            print(f"\n✅ 평가 토큰 (eval_tokens):")
            print(f"   - Prompt tokens: {eval_tokens.get('prompt_tokens', 0)}")
            print(f"   - Completion tokens: {eval_tokens.get('completion_tokens', 0)}")
            print(f"   - Total tokens: {eval_tokens.get('total_tokens', 0)}")
        else:
            print("\n⚠️ eval_tokens가 응답에 없습니다 (백그라운드 평가는 아직 완료되지 않았을 수 있음)")
        
        return result
    except Exception as e:
        print(f"\n❌ 요청 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_websocket_streaming():
    """WebSocket 스트리밍 테스트 및 토큰 사용량 확인 (건너뛰기)"""
    print(f"\n{'='*60}")
    print("테스트 2: WebSocket 스트리밍 (건너뛰기 - websockets 라이브러리 필요)")
    print(f"{'='*60}")
    print("⚠️ WebSocket 테스트는 websockets 라이브러리가 필요합니다.")
    print("   일반 채팅 API 테스트로 대체합니다.")


def test_turn_logs():
    """턴 로그 조회 테스트"""
    print(f"\n{'='*60}")
    print("테스트 3: 턴 로그 조회 (백그라운드 평가 완료 확인)")
    print(f"{'='*60}")
    
    # 잠시 대기 (백그라운드 평가 완료 대기)
    print("\n[대기] 백그라운드 평가 완료 대기 중... (5초)")
    import time
    time.sleep(5)
    
    url = f"{BASE_URL}/api/chat/turn-logs"
    params = {"session_id": SESSION_ID}
    
    print(f"\n[요청] GET {url}")
    print(f"Params: {params}")
    
    try:
        response = requests.get(url, params=params, timeout=30)
        result = response.json()
        
        print(f"\n[응답] Status: {response.status_code}")
        print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        if result.get("turn_logs"):
            print(f"\n✅ 턴 로그 조회 성공")
            for turn_num, turn_log in result["turn_logs"].items():
                print(f"\n턴 {turn_num}:")
                print(f"  - Intent: {turn_log.get('prompt_evaluation_details', {}).get('intent', 'N/A')}")
                print(f"  - Score: {turn_log.get('prompt_evaluation_details', {}).get('score', 'N/A')}")
        else:
            print("\n⚠️ 턴 로그가 없습니다 (백그라운드 평가가 아직 완료되지 않았을 수 있음)")
    except Exception as e:
        print(f"\n❌ 요청 실패: {str(e)}")
        import traceback
        traceback.print_exc()


def main():
    """메인 테스트 함수"""
    print("\n" + "="*60)
    print("토큰 사용량 추적 기능 테스트")
    print("="*60)
    
    try:
        # 테스트 1: 일반 채팅 메시지 전송
        test_chat_with_tokens()
        
        # 테스트 2: WebSocket 스트리밍 (건너뛰기)
        test_websocket_streaming()
        
        # 테스트 3: 턴 로그 조회
        test_turn_logs()
        
        print(f"\n{'='*60}")
        print("✅ 모든 테스트 완료")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

