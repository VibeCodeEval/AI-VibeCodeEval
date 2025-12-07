"""
토큰 사용량 추적 상세 테스트 스크립트
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
        print("토큰 사용량 분석")
        print("-"*60)
        
        if "chat_tokens" in result:
            chat_tokens = result["chat_tokens"]
            if chat_tokens and isinstance(chat_tokens, dict):
                print(f"\n✅ 채팅 검사 토큰 (chat_tokens):")
                print(f"   - Prompt tokens: {chat_tokens.get('prompt_tokens', 0)}")
                print(f"   - Completion tokens: {chat_tokens.get('completion_tokens', 0)}")
                print(f"   - Total tokens: {chat_tokens.get('total_tokens', 0)}")
            else:
                print(f"\n⚠️ chat_tokens가 비어있거나 dict가 아님: {chat_tokens}")
        else:
            print("\n❌ chat_tokens가 응답에 없습니다!")
            print(f"   응답 키: {list(result.keys())}")
        
        if "eval_tokens" in result:
            eval_tokens = result["eval_tokens"]
            if eval_tokens and isinstance(eval_tokens, dict):
                print(f"\n✅ 평가 토큰 (eval_tokens):")
                print(f"   - Prompt tokens: {eval_tokens.get('prompt_tokens', 0)}")
                print(f"   - Completion tokens: {eval_tokens.get('completion_tokens', 0)}")
                print(f"   - Total tokens: {eval_tokens.get('total_tokens', 0)}")
            else:
                print(f"\n⚠️ eval_tokens가 비어있거나 dict가 아님: {eval_tokens}")
                print("   (백그라운드 평가는 아직 완료되지 않았을 수 있음)")
        else:
            print("\n⚠️ eval_tokens가 응답에 없습니다 (백그라운드 평가는 아직 완료되지 않았을 수 있음)")
        
        # 전체 응답 구조 확인
        print("\n" + "-"*60)
        print("응답 구조 확인")
        print("-"*60)
        print(f"응답 키: {list(result.keys())}")
        if "ai_message" in result:
            print(f"AI 메시지 길이: {len(result.get('ai_message', ''))} 문자")
        
        return result
    except Exception as e:
        print(f"\n❌ 요청 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_turn_logs_with_tokens():
    """턴 로그 조회 및 토큰 사용량 확인"""
    print_section("테스트 2: 턴 로그 조회 (백그라운드 평가 완료 확인)")
    
    # 잠시 대기 (백그라운드 평가 완료 대기)
    print("\n[대기] 백그라운드 평가 완료 대기 중... (10초)")
    time.sleep(10)
    
    url = f"{BASE_URL}/api/chat/turn-logs"
    params = {"session_id": SESSION_ID}
    
    print(f"\n[요청] GET {url}")
    print(f"Params: {params}")
    
    try:
        response = requests.get(url, params=params, timeout=30)
        result = response.json()
        
        print(f"\n[응답] Status: {response.status_code}")
        
        if result.get("turn_logs"):
            print(f"\n✅ 턴 로그 조회 성공")
            for turn_num, turn_log in result["turn_logs"].items():
                print(f"\n턴 {turn_num}:")
                print(f"  - Intent: {turn_log.get('prompt_evaluation_details', {}).get('intent', 'N/A')}")
                print(f"  - Score: {turn_log.get('prompt_evaluation_details', {}).get('score', 'N/A')}")
        else:
            print("\n⚠️ 턴 로그가 없습니다 (백그라운드 평가가 아직 완료되지 않았을 수 있음)")
            print(f"   응답: {json.dumps(result, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"\n❌ 요청 실패: {str(e)}")
        import traceback
        traceback.print_exc()


def main():
    """메인 테스트 함수"""
    print("\n" + "="*60)
    print("토큰 사용량 추적 상세 테스트")
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
        
        # 테스트 2: 턴 로그 조회
        test_turn_logs_with_tokens()
        
        # 최종 요약
        print_section("테스트 요약")
        if chat_result:
            has_chat_tokens = bool(chat_result.get("chat_tokens"))
            has_eval_tokens = bool(chat_result.get("eval_tokens"))
            
            print(f"\n✅ 채팅 토큰 추적: {'성공' if has_chat_tokens else '실패'}")
            print(f"⚠️ 평가 토큰 추적: {'성공' if has_eval_tokens else '대기 중 (백그라운드)'}")
            
            if not has_chat_tokens:
                print("\n❌ 문제: chat_tokens가 추적되지 않았습니다.")
                print("   - Intent Analyzer 또는 Writer LLM에서 토큰 추적 확인 필요")
                print("   - 서버 로그 확인 필요")
        
        print(f"\n{'='*60}")
        print("✅ 모든 테스트 완료")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()







