"""
외판원 문제 전체 Flow 테스트
1. Chat API로 대화 생성 (여러 턴)
2. Submit API로 코드 제출
3. 평가 결과 확인

자동으로 생성된 SessionId와 SubmissionId 사용
"""
import requests
import json
import time
from pathlib import Path

BASE_URL = "http://localhost:8000"

# test_ids.json에서 ID 읽기
test_ids_file = Path("test_ids.json")
if test_ids_file.exists():
    with open(test_ids_file, "r", encoding="utf-8") as f:
        test_ids = json.load(f)
    session_id = test_ids.get("session_id", 1000)
    submission_id = test_ids.get("submission_id", 1000)
    exam_participant_id = test_ids.get("exam_participant_id", 1000)
    print("=" * 80)
    print("외판원 문제 전체 Flow 테스트")
    print(f"SessionId: {session_id}, SubmissionId: {submission_id}")
    print(f"ExamParticipantId: {exam_participant_id}")
    print("=" * 80)
else:
    print("⚠️  test_ids.json 파일을 찾을 수 없습니다.")
    print("   먼저 test_scripts/setup_submit_test_data.py를 실행하세요.")
    exit(1)

# 외판원 문제 (TSP) 제출 코드
tsp_code = """import sys
input = sys.stdin.readline

def tsp(current, visited):
    if visited == (1 << N) - 1:
        if W[current][0] != 0:
            return W[current][0]
        else:
            return float('inf')
    
    if dp[current][visited] != -1:
        return dp[current][visited]
    
    dp[current][visited] = float('inf')
    for i in range(N):
        if visited & (1 << i) == 0 and W[current][i] != 0:
            dp[current][visited] = min(dp[current][visited], tsp(i, visited | (1 << i)) + W[current][i])
    
    return dp[current][visited]

N = int(input())
W = [list(map(int, input().split())) for _ in range(N)]

dp = [[-1] * (1 << N) for _ in range(N)]
result = tsp(0, 1)
print(result if result != float('inf') else -1)
"""

# Step 1: Chat API로 대화 생성 (여러 턴)
print("\n[Step 1] Chat API로 대화 생성")
print("-" * 80)

turn_id = 1

# Turn 1: 첫 번째 질문
print(f"\n[Turn {turn_id}] 첫 번째 질문")
payload1 = {
    "sessionId": session_id,
    "examParticipantId": exam_participant_id,
    "turnId": turn_id,
    "role": "USER",
    "content": "외판원 문제를 풀고 싶어요. 비트마스킹이 뭔가요?",
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
        print(f"✅ Turn {turn_id} 성공")
        print(f"   AI Turn: {ai_msg1.get('turn')}")
        print(f"   AI 응답 (처음 100자): {ai_msg1.get('content', '')[:100]}...")
        turn_id = ai_msg1.get('turn', turn_id + 1)
    else:
        print(f"❌ Turn {turn_id} 실패: {response1.status_code}")
        print(json.dumps(result1, indent=2, ensure_ascii=False))
        exit(1)
except Exception as e:
    print(f"❌ Turn {turn_id} 오류: {str(e)}")
    exit(1)

# 잠시 대기 (LLM 응답 시간)
time.sleep(2)

# Turn 2: 두 번째 질문
print(f"\n[Turn {turn_id + 1}] 두 번째 질문")
payload2 = {
    "sessionId": session_id,
    "examParticipantId": exam_participant_id,
    "turnId": turn_id + 1,
    "role": "USER",
    "content": "DP로 푸는 방법을 알려주세요",
    "context": {
        "problemId": 1,
        "specVersion": 1
    }
}

try:
    response2 = requests.post(f"{BASE_URL}/api/chat/messages", json=payload2, timeout=120)
    result2 = response2.json()
    
    if response2.status_code == 200:
        ai_msg2 = result2.get("aiMessage", {})
        print(f"✅ Turn {turn_id + 1} 성공")
        print(f"   AI Turn: {ai_msg2.get('turn')}")
        print(f"   AI 응답 (처음 100자): {ai_msg2.get('content', '')[:100]}...")
        turn_id = ai_msg2.get('turn', turn_id + 2)
    else:
        print(f"❌ Turn {turn_id + 1} 실패: {response2.status_code}")
        print(json.dumps(result2, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"❌ Turn {turn_id + 1} 오류: {str(e)}")

# 잠시 대기
time.sleep(2)

# Step 2: Submit API 호출
print("\n" + "=" * 80)
print("[Step 2] Submit API 호출")
print("-" * 80)

payload_submit = {
    "problemId": 1,
    "specVersion": 1,
    "examParticipantId": exam_participant_id,
    "finalCode": tsp_code,
    "language": "python3.11",
    "submissionId": submission_id
}

print(f"Request URL: {BASE_URL}/api/session/submit")
print(f"Request Body:")
print(json.dumps(payload_submit, indent=2, ensure_ascii=False)[:500] + "...")

try:
    response_submit = requests.post(
        f"{BASE_URL}/api/session/submit",
        json=payload_submit,
        timeout=10
    )
    
    print(f"\nResponse Status: {response_submit.status_code}")
    result_submit = response_submit.json()
    print(f"Response Body:")
    print(json.dumps(result_submit, indent=2, ensure_ascii=False))
    
    if response_submit.status_code == 200:
        print("\n✅ Submit API 호출 성공")
        print(f"   submissionId: {result_submit.get('submissionId')}")
        print(f"   status: {result_submit.get('status')}")
        print("\n⚠️  평가는 동기적으로 진행되며 완료 후 Response를 반환합니다.")
        print("   결과 확인:")
        print(f"   - submissions (submission_id: {submission_id})")
        print(f"   - scores (submission_id: {submission_id})")
        print(f"   - prompt_evaluations (session_id: {session_id})")
        print(f"\n   결과 확인 명령: uv run python test_scripts/check_submit_result.py")
    else:
        print(f"\n❌ Submit API 호출 실패")
        if result_submit.get("detail"):
            print(f"   Error: {result_submit.get('detail')}")
        
except requests.exceptions.ConnectionError:
    print("\n❌ 서버에 연결할 수 없습니다.")
    print("   서버가 실행 중인지 확인하세요: uv run scripts/run_dev.py")
except Exception as e:
    print(f"\n❌ 오류 발생: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("전체 Flow 테스트 완료")
print("=" * 80)

