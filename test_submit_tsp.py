"""
외판원 문제 Submit 테스트
자동으로 생성된 SessionId와 SubmissionId 사용
"""
import requests
import json
import time
import os
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
    print("외판원 문제 Submit 테스트")
    print(f"SessionId: {session_id}, SubmissionId: {submission_id}")
    print(f"ExamParticipantId: {exam_participant_id}")
    print("=" * 80)
else:
    print("⚠️  test_ids.json 파일을 찾을 수 없습니다.")
    print("   먼저 test_scripts/setup_submit_test_data.py를 실행하세요.")
    exit(1)

# 외판원 문제 (TSP) 제출 코드 (백준 2098번)
# 비트마스킹 DP로 해결
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

# Submit API 요청
print("\n[1] Submit API 호출")
payload = {
    "problemId": 1,  # 문제 ID (DB에서 확인 필요)
    "specVersion": 1,  # 스펙 버전
    "examParticipantId": exam_participant_id,  # exam_participants.id
    "finalCode": tsp_code,
    "language": "python3.11",
    "submissionId": submission_id
}

print(f"Request URL: {BASE_URL}/api/session/submit")
print(f"Request Body:")
print(json.dumps(payload, indent=2, ensure_ascii=False))

try:
    print("\n⏳ 평가가 완료될 때까지 대기합니다 (최대 5분)...")
    response = requests.post(
        f"{BASE_URL}/api/session/submit",
        json=payload,
        timeout=300  # 5분 타임아웃 (평가 완료까지 대기)
    )
    
    print(f"\n[2] Response Status: {response.status_code}")
    result = response.json()
    print(f"Response Body:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if response.status_code == 200:
        print("\n✅ Submit API 호출 성공")
        print(f"   submissionId: {result.get('submissionId')}")
        print(f"   status: {result.get('status')}")
        print("\n⚠️  평가는 동기적으로 진행되며 완료 후 Response를 반환합니다.")
        print("   결과 확인:")
        print(f"   - submissions (submission_id: {submission_id})")
        print(f"   - scores (submission_id: {submission_id})")
        print(f"   - prompt_evaluations (session_id: {session_id})")
        print(f"\n   결과 확인 명령: uv run python test_scripts/check_submit_result.py")
    else:
        print(f"\n❌ Submit API 호출 실패")
        if result.get("detail"):
            print(f"   Error: {result.get('detail')}")
        
except requests.exceptions.ConnectionError:
    print("\n❌ 서버에 연결할 수 없습니다.")
    print("   서버가 실행 중인지 확인하세요: uv run scripts/run_dev.py")
except Exception as e:
    print(f"\n❌ 오류 발생: {str(e)}")
    import traceback
    traceback.print_exc()

