"""
토큰 조회 API 테스트 스크립트
"""
import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"
SESSION_ID = f"test-session-{int(datetime.now().timestamp() * 1000)}"


def print_section(title):
    """섹션 제목 출력"""
    print(f"\n{'='*60}")
    print(title)
    print(f"{'='*60}")


def test_chat_with_tokens():
    """일반 채팅 메시지 전송 및 토큰 사용량 확인"""
    print_section("테스트 1: 일반 채팅 메시지 전송 (토큰 사용량 확인)")
    
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
        
        # 토큰 사용량 상세 확인
        print("\n" + "-"*60)
        print("토큰 사용량 분석 (Core 전달 형식)")
        print("-"*60)
        
        if "chat_tokens" in result and result["chat_tokens"]:
            chat = result["chat_tokens"]
            print(f"\n✅ 채팅 검사 토큰 (chat_tokens):")
            print(f"   - Prompt tokens: {chat.get('prompt_tokens', 0)}")
            print(f"   - Completion tokens: {chat.get('completion_tokens', 0)}")
            print(f"   - Total tokens: {chat.get('total_tokens', 0)}")
        
        if "eval_tokens" in result and result["eval_tokens"]:
            eval = result["eval_tokens"]
            print(f"\n✅ 평가 토큰 (eval_tokens):")
            print(f"   - Prompt tokens: {eval.get('prompt_tokens', 0)}")
            print(f"   - Completion tokens: {eval.get('completion_tokens', 0)}")
            print(f"   - Total tokens: {eval.get('total_tokens', 0)}")
        else:
            print("\n⚠️ eval_tokens 없음 (백그라운드 평가는 아직 완료되지 않았을 수 있음)")
        
        if "total_tokens" in result and result["total_tokens"]:
            total = result["total_tokens"]
            print(f"\n✅ 전체 토큰 (total_tokens) - Core 전달용:")
            print(f"   - Prompt tokens: {total.get('prompt_tokens', 0)}")
            print(f"   - Completion tokens: {total.get('completion_tokens', 0)}")
            print(f"   - Total tokens: {total.get('total_tokens', 0)}")
        
        return result
    except Exception as e:
        print(f"\n❌ 요청 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_token_api():
    """토큰 조회 API 테스트"""
    print_section("테스트 2: 토큰 조회 API (GET /api/chat/tokens)")
    
    # 잠시 대기 (백그라운드 평가 완료 대기)
    print("\n[대기] 백그라운드 평가 완료 대기 중... (10초)")
    time.sleep(10)
    
    url = f"{BASE_URL}/api/chat/tokens"
    params = {"session_id": SESSION_ID}
    
    print(f"\n[요청] GET {url}")
    print(f"Params: {params}")
    
    try:
        response = requests.get(url, params=params, timeout=30)
        result = response.json()
        
        print(f"\n[응답] Status: {response.status_code}")
        
        # 토큰 사용량 상세 확인
        print("\n" + "-"*60)
        print("토큰 사용량 조회 결과 (Core 전달 형식)")
        print("-"*60)
        
        if result.get("error"):
            print(f"\n❌ 에러: {result.get('error_message')}")
        else:
            if "chat_tokens" in result and result["chat_tokens"]:
                chat = result["chat_tokens"]
                print(f"\n✅ 채팅 검사 토큰 (chat_tokens):")
                print(f"   - Prompt tokens: {chat.get('prompt_tokens', 0)}")
                print(f"   - Completion tokens: {chat.get('completion_tokens', 0)}")
                print(f"   - Total tokens: {chat.get('total_tokens', 0)}")
            
            if "eval_tokens" in result and result["eval_tokens"]:
                eval = result["eval_tokens"]
                print(f"\n✅ 평가 토큰 (eval_tokens):")
                print(f"   - Prompt tokens: {eval.get('prompt_tokens', 0)}")
                print(f"   - Completion tokens: {eval.get('completion_tokens', 0)}")
                print(f"   - Total tokens: {eval.get('total_tokens', 0)}")
            else:
                print("\n⚠️ eval_tokens 없음 (백그라운드 평가가 아직 완료되지 않았을 수 있음)")
            
            if "total_tokens" in result and result["total_tokens"]:
                total = result["total_tokens"]
                print(f"\n✅ 전체 토큰 (total_tokens) - Core 전달용:")
                print(f"   - Prompt tokens: {total.get('prompt_tokens', 0)}")
                print(f"   - Completion tokens: {total.get('completion_tokens', 0)}")
                print(f"   - Total tokens: {total.get('total_tokens', 0)}")
            
            # Core 백엔드 전달 형식 확인
            print("\n" + "-"*60)
            print("Core 백엔드 전달 형식")
            print("-"*60)
            print(json.dumps({
                "chat_tokens": result.get("chat_tokens"),
                "eval_tokens": result.get("eval_tokens"),
                "total_tokens": result.get("total_tokens"),
            }, indent=2, ensure_ascii=False))
        
        return result
    except Exception as e:
        print(f"\n❌ 요청 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """메인 테스트 함수"""
    print("\n" + "="*60)
    print("토큰 조회 API 테스트")
    print("="*60)
    print(f"세션 ID: {SESSION_ID}")
    print(f"서버 URL: {BASE_URL}")
    
    try:
        # 서버 연결 확인
        print("\n[서버 연결 확인]")
        try:
            health_response = requests.get(f"{BASE_URL}/health", timeout=5)
            if health_response.status_code == 200:
                print("✅ 서버 연결 성공")
            else:
                print(f"⚠️ 서버 응답: {health_response.status_code}")
        except Exception as e:
            print(f"❌ 서버 연결 실패: {str(e)}")
            print("   서버가 실행 중인지 확인하세요.")
            return
        
        # 테스트 1: 일반 채팅 메시지 전송
        chat_result = test_chat_with_tokens()
        
        # 테스트 2: 토큰 조회 API
        token_result = test_token_api()
        
        # 최종 요약
        print_section("테스트 요약")
        
        if chat_result:
            has_chat = bool(chat_result.get("chat_tokens"))
            has_total = bool(chat_result.get("total_tokens"))
            
            print(f"\n✅ 채팅 API 토큰 추적: {'성공' if has_chat else '실패'}")
            print(f"✅ 전체 토큰 합계: {'성공' if has_total else '실패'}")
        
        if token_result and not token_result.get("error"):
            has_chat = bool(token_result.get("chat_tokens"))
            has_eval = bool(token_result.get("eval_tokens"))
            has_total = bool(token_result.get("total_tokens"))
            
            print(f"\n✅ 토큰 조회 API: 성공")
            print(f"   - chat_tokens: {'있음' if has_chat else '없음'}")
            print(f"   - eval_tokens: {'있음' if has_eval else '없음 (백그라운드 대기)'}")
            print(f"   - total_tokens: {'있음' if has_total else '없음'}")
        
        print(f"\n{'='*60}")
        print("✅ 모든 테스트 완료")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()







