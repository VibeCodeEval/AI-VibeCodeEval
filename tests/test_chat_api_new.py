"""
신규 Chat API 테스트 (2024-12-07)
POST /api/chat/messages 엔드포인트 테스트
"""
import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"


def print_section(title):
    """섹션 제목 출력"""
    print(f"\n{'='*60}")
    print(title)
    print(f"{'='*60}")


def setup_test_session():
    """테스트용 세션 정보 반환"""
    print_section("테스트 세션 정보")
    
    # setup_web_test_data.py를 실행하면 다음 데이터가 생성됩니다:
    # - exam_id: 1
    # - participant_id: 1
    # - exam_participants.id: 1 (exam_id=1, participant_id=1인 경우)
    # - spec_id: 10
    # - problem_id: 1
    # - prompt_sessions.id: 1
    
    print("⚠️  테스트 전에 다음을 실행하세요:")
    print("   uv run python test_scripts/setup_web_test_data.py")
    print("\n생성되는 테스트 데이터:")
    print("  - Session ID: 1")
    print("  - ExamParticipant ID: 1")
    print("  - Problem ID: 1")
    print("  - Spec Version: 1")
    
    # 테스트 세션 정보 반환
    # 주의: setup_web_test_data.py 실행 후 exam_participants.id를 확인해야 함
    # exam_id=1, participant_id=1인 경우 exam_participants.id는 자동 생성됨
    return {
        "session_id": 1,  # prompt_sessions.id
        "exam_id": 1,
        "participant_id": 1,
        "exam_participant_id": 2,  # exam_participants.id (실제 DB에서 확인 필요, 보통 2번째 생성)
        "spec_id": 10,
        "problem_id": 1,
        "spec_version": 1
    }


def test_send_message(session_info, turn_id=1):
    """메시지 전송 테스트 (신규 API)"""
    print_section(f"테스트: 메시지 전송 (Turn {turn_id})")
    
    url = f"{BASE_URL}/api/chat/messages"
    payload = {
        "sessionId": session_info["session_id"],
        "examParticipantId": session_info["exam_participant_id"],
        "turnId": turn_id,
        "role": "USER",
        "content": "DP에 대해 설명해줘",
        "context": {
            "problemId": session_info["problem_id"],
            "specVersion": session_info["spec_version"]
        }
    }
    
    print(f"\n[요청] POST {url}")
    print(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        result = response.json()
        
        print(f"\n[응답] Status: {response.status_code}")
        
        if response.status_code == 200:
            print("\n✅ 요청 성공!")
            print("\n" + "-"*60)
            print("응답 데이터")
            print("-"*60)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            # aiMessage 확인
            if "aiMessage" in result:
                ai_msg = result["aiMessage"]
                print("\n" + "-"*60)
                print("AI 메시지 정보")
                print("-"*60)
                print(f"Session ID: {ai_msg.get('session_id')}")
                print(f"Turn: {ai_msg.get('turn')}")
                print(f"Role: {ai_msg.get('role')}")
                print(f"Content: {ai_msg.get('content', '')[:100]}...")
                print(f"Token Count (현재): {ai_msg.get('tokenCount', 0)}")
                print(f"Total Token (누적): {ai_msg.get('totalToken', 0)}")
                
                return {
                    "success": True,
                    "ai_message": ai_msg,
                    "next_turn": ai_msg.get("turn", turn_id + 1)
                }
            else:
                print("\n❌ aiMessage가 응답에 없습니다.")
                return {"success": False, "error": "aiMessage not found"}
        else:
            print(f"\n❌ 요청 실패: {response.status_code}")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return {"success": False, "error": result}
            
    except requests.exceptions.Timeout:
        print("\n❌ 요청 타임아웃 (120초 초과)")
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        print(f"\n❌ 요청 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def test_multiple_turns(session_info, num_turns=3):
    """여러 턴 대화 테스트"""
    print_section(f"테스트: 여러 턴 대화 ({num_turns}턴)")
    
    results = []
    current_turn = 1
    
    for i in range(num_turns):
        print(f"\n--- Turn {current_turn} ---")
        
        result = test_send_message(session_info, turn_id=current_turn)
        results.append(result)
        
        if not result.get("success"):
            print(f"\n❌ Turn {current_turn} 실패")
            break
        
        # 다음 턴으로 (AI 응답 턴 다음이 사용자 턴)
        current_turn = result.get("next_turn", current_turn + 1) + 1
        
        # 턴 간 대기 (선택사항)
        if i < num_turns - 1:
            print(f"\n[대기] 다음 턴 전 대기 (2초)...")
            time.sleep(2)
    
    # 요약
    print_section("여러 턴 대화 요약")
    success_count = sum(1 for r in results if r.get("success"))
    print(f"성공: {success_count}/{num_turns}")
    
    if results:
        last_result = results[-1]
        if last_result.get("success") and "ai_message" in last_result:
            last_ai = last_result["ai_message"]
            print(f"\n최종 토큰 정보:")
            print(f"  - 마지막 Turn Token: {last_ai.get('tokenCount', 0)}")
            print(f"  - 전체 누적 Token: {last_ai.get('totalToken', 0)}")
    
    return results


def test_session_not_found():
    """존재하지 않는 세션 테스트"""
    print_section("테스트: 존재하지 않는 세션 (404 에러)")
    
    url = f"{BASE_URL}/api/chat/messages"
    payload = {
        "sessionId": 99999,  # 존재하지 않는 세션 ID
        "examParticipantId": 1,
        "turnId": 1,
        "role": "USER",
        "content": "테스트 메시지",
        "context": {
            "problemId": 1,
            "specVersion": 1
        }
    }
    
    print(f"\n[요청] POST {url}")
    print(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        result = response.json()
        
        print(f"\n[응답] Status: {response.status_code}")
        
        if response.status_code == 404:
            print("\n✅ 예상된 404 에러 발생")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return True
        else:
            print(f"\n⚠️ 예상과 다른 응답: {response.status_code}")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return False
            
    except Exception as e:
        print(f"\n❌ 요청 실패: {str(e)}")
        return False


def main():
    """메인 테스트 함수"""
    print("\n" + "="*60)
    print("신규 Chat API 테스트 (POST /api/chat/messages)")
    print("="*60)
    print(f"서버 URL: {BASE_URL}")
    print(f"테스트 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
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
            print("   실행 명령: uv run scripts/run_dev.py")
            return
        
        # 테스트 세션 정보 준비
        session_info = setup_test_session()
        
        # 실제 세션 ID 확인 (DB에서 조회하거나 사용자 입력)
        print("\n[세션 정보 입력]")
        print("실제 세션 ID를 입력하거나, DB에서 조회한 세션 ID를 사용하세요.")
        print(f"기본값: session_id={session_info['session_id']}")
        
        # 사용자 입력 받기 (선택사항)
        # user_input = input("세션 ID를 입력하세요 (Enter로 기본값 사용): ").strip()
        # if user_input:
        #     session_info["session_id"] = int(user_input)
        
        # 테스트 1: 단일 메시지 전송
        print("\n" + "="*60)
        print("테스트 1: 단일 메시지 전송")
        print("="*60)
        result1 = test_send_message(session_info, turn_id=1)
        
        if result1.get("success"):
            # 테스트 2: 여러 턴 대화
            print("\n" + "="*60)
            print("테스트 2: 여러 턴 대화")
            print("="*60)
            test_multiple_turns(session_info, num_turns=3)
        
        # 테스트 3: 존재하지 않는 세션
        print("\n" + "="*60)
        print("테스트 3: 에러 처리 (존재하지 않는 세션)")
        print("="*60)
        test_session_not_found()
        
        # 최종 요약
        print_section("테스트 완료")
        print("✅ 모든 테스트가 완료되었습니다.")
        print("\n다음 단계:")
        print("1. 응답 데이터 확인")
        print("2. DB에서 메시지 저장 확인 (백엔드에서 저장)")
        print("3. 토큰 계산 확인")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

