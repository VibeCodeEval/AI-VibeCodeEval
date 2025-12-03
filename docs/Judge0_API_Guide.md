# Judge0 API 작동 방식 가이드

## 📋 개요

Judge0는 온라인 코드 실행 및 채점 서비스입니다. REST API를 통해 코드를 제출하고 실행 결과를 받을 수 있습니다.

---

## 🔄 작동 방식

### 1단계: 코드 제출 (POST)

```
POST /submissions
```

**요청 본문**:
```json
{
  "source_code": "print('hello')",
  "language_id": 71,
  "stdin": "입력 데이터",
  "expected_output": "예상 출력 (선택)",
  "cpu_time_limit": 2,
  "memory_limit": 128000
}
```

**응답**:
```json
{
  "token": "abc123-def456-ghi789"
}
```

### 2단계: 결과 조회 (GET)

```
GET /submissions/{token}
```

**응답**:
```json
{
  "status": {
    "id": 3,
    "description": "Accepted"
  },
  "stdout": "hello\n",
  "stderr": null,
  "compile_output": null,
  "message": null,
  "time": "0.001",
  "memory": 1024,
  "exit_code": 0,
  "exit_signal": null
}
```

---

## ✅ 필요한 정보

### 필수 항목

1. **source_code**: 실행할 코드
2. **language_id**: 언어 ID (Python=71, Java=62, C++=54 등)

### 선택 항목 (하지만 평가에는 필요)

3. **stdin**: 테스트 케이스 입력
4. **expected_output**: 예상 출력 (정확성 평가용)
5. **cpu_time_limit**: CPU 시간 제한 (초)
6. **memory_limit**: 메모리 제한 (KB)

---

## 💡 사용자 질문에 대한 답변

**Q: 정답 코드와 TC만 있으면 되나요?**

**A: 거의 맞습니다!** 하지만 추가 설정도 필요합니다:

✅ **필수**:
- 정답 코드 (`source_code`)
- 테스트 케이스 입력 (`stdin`)
- 언어 ID (`language_id`)

✅ **권장** (평가를 위해):
- 예상 출력 (`expected_output`) - 정확성 평가용
- 시간 제한 (`cpu_time_limit`) - 성능 평가용
- 메모리 제한 (`memory_limit`) - 성능 평가용

---

## 📝 실제 예제

### 예제 1: 간단한 Python 코드 실행

```python
import httpx
import asyncio

async def judge0_simple_example():
    """간단한 코드 실행 예제"""
    
    # Judge0 API URL
    base_url = "http://localhost:2358"
    
    # 1. 코드 제출
    submission_data = {
        "source_code": "print('Hello, World!')",
        "language_id": 71,  # Python 3
        "cpu_time_limit": 2,
        "memory_limit": 128000  # 128MB
    }
    
    async with httpx.AsyncClient() as client:
        # 제출
        response = await client.post(
            f"{base_url}/submissions",
            json=submission_data,
            params={"base64_encoded": "false", "wait": "false"}
        )
        result = response.json()
        token = result["token"]
        print(f"제출 토큰: {token}")
        
        # 2. 결과 조회 (폴링)
        import time
        for _ in range(10):  # 최대 10회 시도
            await asyncio.sleep(1)  # 1초 대기
            
            result_response = await client.get(
                f"{base_url}/submissions/{token}",
                params={"base64_encoded": "false"}
            )
            result = result_response.json()
            
            status_id = result["status"]["id"]
            
            # 상태 ID 설명:
            # 1: In Queue
            # 2: Processing
            # 3: Accepted (성공)
            # 4-11: 에러 (Wrong Answer, Time Limit, Runtime Error 등)
            
            if status_id == 3:  # Accepted
                print(f"✅ 성공!")
                print(f"출력: {result.get('stdout', '')}")
                print(f"실행 시간: {result.get('time', '0')}초")
                print(f"메모리: {result.get('memory', '0')}KB")
                break
            elif status_id >= 4:  # 에러
                print(f"❌ 실패: {result['status']['description']}")
                print(f"에러: {result.get('stderr', '')}")
                break
            else:
                print(f"⏳ 처리 중... (상태: {result['status']['description']})")

# 실행
asyncio.run(judge0_simple_example())
```

---

### 예제 2: 테스트 케이스와 함께 실행 (정확성 평가)

```python
async def judge0_with_test_cases():
    """테스트 케이스와 함께 실행"""
    
    base_url = "http://localhost:2358"
    
    # 사용자 제출 코드
    user_code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

n = int(input())
print(fibonacci(n))
"""
    
    # 테스트 케이스들
    test_cases = [
        {"input": "5", "expected": "5"},
        {"input": "10", "expected": "55"},
        {"input": "0", "expected": "0"},
    ]
    
    results = []
    
    async with httpx.AsyncClient() as client:
        for i, tc in enumerate(test_cases):
            # 각 테스트 케이스마다 제출
            submission_data = {
                "source_code": user_code,
                "language_id": 71,  # Python 3
                "stdin": tc["input"],
                "expected_output": tc["expected"],
                "cpu_time_limit": 2,
                "memory_limit": 128000
            }
            
            response = await client.post(
                f"{base_url}/submissions",
                json=submission_data,
                params={"base64_encoded": "false", "wait": "false"}
            )
            token = response.json()["token"]
            
            # 결과 대기
            await asyncio.sleep(2)
            
            result_response = await client.get(
                f"{base_url}/submissions/{token}",
                params={"base64_encoded": "false"}
            )
            result = result_response.json()
            
            # 결과 분석
            status_id = result["status"]["id"]
            passed = (
                status_id == 3 and  # Accepted
                result.get("stdout", "").strip() == tc["expected"]
            )
            
            results.append({
                "test_case": i + 1,
                "input": tc["input"],
                "expected": tc["expected"],
                "actual": result.get("stdout", "").strip(),
                "passed": passed,
                "status": result["status"]["description"],
                "time": result.get("time", "0"),
                "memory": result.get("memory", "0")
            })
    
    # 결과 출력
    print("\n=== 테스트 케이스 결과 ===")
    for r in results:
        status_icon = "✅" if r["passed"] else "❌"
        print(f"{status_icon} TC {r['test_case']}: {r['status']}")
        print(f"   입력: {r['input']}, 예상: {r['expected']}, 실제: {r['actual']}")
        print(f"   시간: {r['time']}초, 메모리: {r['memory']}KB")
    
    # 통과율 계산
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    print(f"\n통과율: {passed_count}/{total_count} ({passed_count/total_count*100:.1f}%)")

asyncio.run(judge0_with_test_cases())
```

---

### 예제 3: 성능 평가 (실행 시간, 메모리 측정)

```python
async def judge0_performance_evaluation():
    """성능 평가 예제"""
    
    base_url = "http://localhost:2358"
    
    # 두 가지 알고리즘 비교
    code1 = """
# O(n^2) 알고리즘
n = int(input())
result = 0
for i in range(n):
    for j in range(n):
        result += 1
print(result)
"""
    
    code2 = """
# O(n) 알고리즘
n = int(input())
result = n * n
print(result)
"""
    
    test_input = "1000"
    
    async with httpx.AsyncClient() as client:
        for name, code in [("O(n^2)", code1), ("O(n)", code2)]:
            submission_data = {
                "source_code": code,
                "language_id": 71,
                "stdin": test_input,
                "cpu_time_limit": 5,
                "memory_limit": 128000
            }
            
            response = await client.post(
                f"{base_url}/submissions",
                json=submission_data,
                params={"base64_encoded": "false", "wait": "false"}
            )
            token = response.json()["token"]
            
            await asyncio.sleep(3)
            
            result_response = await client.get(
                f"{base_url}/submissions/{token}",
                params={"base64_encoded": "false"}
            )
            result = result_response.json()
            
            print(f"\n{name} 알고리즘:")
            print(f"  실행 시간: {result.get('time', '0')}초")
            print(f"  메모리 사용: {result.get('memory', '0')}KB")
            print(f"  상태: {result['status']['description']}")

asyncio.run(judge0_performance_evaluation())
```

---

## 🔢 언어 ID 목록

| 언어 | ID |
|------|-----|
| Python 3 | 71 |
| Java | 62 |
| C++ | 54 |
| C | 50 |
| JavaScript (Node.js) | 63 |
| Go | 60 |
| Rust | 73 |

전체 목록: https://github.com/judge0/judge0/blob/master/CHANGELOG.md

---

## 📊 상태 ID 설명

| ID | 설명 | 의미 |
|----|------|------|
| 1 | In Queue | 대기 중 |
| 2 | Processing | 처리 중 |
| 3 | Accepted | 성공 ✅ |
| 4 | Wrong Answer | 잘못된 답 |
| 5 | Time Limit Exceeded | 시간 초과 |
| 6 | Compilation Error | 컴파일 에러 |
| 7 | Runtime Error | 런타임 에러 |
| 8 | Runtime Error (SIGSEGV) | 세그멘테이션 폴트 |
| 9 | Runtime Error (SIGXFSZ) | 파일 크기 초과 |
| 10 | Runtime Error (SIGFPE) | 산술 오류 |
| 11 | Runtime Error (SIGABRT) | 중단 |
| 12 | Runtime Error (NZEC) | Non-zero exit code |
| 13 | Runtime Error (Other) | 기타 런타임 에러 |
| 14 | Internal Error | Judge0 내부 에러 |
| 15 | Exec Format Error | 실행 파일 형식 에러 |

---

## 🎯 우리 프로젝트에서의 사용

### 현재 계획

```python
# app/infrastructure/judge0/client.py (예정)

class Judge0Client:
    """Judge0 API 클라이언트"""
    
    def __init__(self, api_url: str, api_key: Optional[str] = None):
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.client = httpx.AsyncClient()
    
    async def submit_code(
        self,
        code: str,
        language: str,
        stdin: str = "",
        expected_output: Optional[str] = None,
        timeout: int = 5,
        memory_limit: int = 128
    ) -> str:
        """코드 제출"""
        language_id = self._get_language_id(language)
        
        response = await self.client.post(
            f"{self.api_url}/submissions",
            json={
                "source_code": code,
                "language_id": language_id,
                "stdin": stdin,
                "expected_output": expected_output,
                "cpu_time_limit": timeout,
                "memory_limit": memory_limit * 1024  # MB -> KB
            },
            params={"base64_encoded": "false", "wait": "false"},
            headers={"X-Auth-Token": self.api_key} if self.api_key else {}
        )
        
        return response.json()["token"]
    
    async def get_result(self, token: str) -> Dict[str, Any]:
        """결과 조회"""
        response = await self.client.get(
            f"{self.api_url}/submissions/{token}",
            params={"base64_encoded": "false"}
        )
        return response.json()
    
    def _get_language_id(self, language: str) -> int:
        """언어 이름을 ID로 변환"""
        language_map = {
            "python": 71,
            "java": 62,
            "cpp": 54,
            "c": 50,
            "javascript": 63,
            "go": 60,
            "rust": 73
        }
        return language_map.get(language.lower(), 71)  # 기본값: Python
```

---

## 📝 요약

### 필요한 정보

✅ **필수**:
- `source_code`: 정답 코드
- `language_id`: 언어 ID
- `stdin`: 테스트 케이스 입력

✅ **평가를 위해 권장**:
- `expected_output`: 예상 출력 (정확성 평가)
- `cpu_time_limit`: 시간 제한 (성능 평가)
- `memory_limit`: 메모리 제한 (성능 평가)

### 작동 흐름

1. **제출**: POST `/submissions` → 토큰 받기
2. **조회**: GET `/submissions/{token}` → 결과 받기
3. **분석**: 상태 ID로 성공/실패 판단

### 답변

**Q: 정답 코드와 TC만 있으면 되나요?**

**A: 네, 맞습니다!** 하지만 평가를 위해서는:
- 정답 코드 ✅
- 테스트 케이스 입력 ✅
- 예상 출력 (정확성 평가용) ✅
- 시간/메모리 제한 (성능 평가용) ✅

이 정도면 충분합니다!

