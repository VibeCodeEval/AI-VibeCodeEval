# Judge0 테스트 케이스 검증 Flow

## 전체 흐름

```
1. problem_info.py (테스트 케이스 정의)
   ↓
2. execution.py (6c 노드 - TC 추출)
   ↓
3. JudgeTask 생성 (큐에 추가)
   ↓
4. JudgeWorker (큐에서 작업 가져오기)
   ↓
5. Judge0Client.execute_test_cases (각 TC 실행)
   ↓
6. stdout vs expected 비교 (검증)
   ↓
7. correctness_score 계산
```

## 1. 테스트 케이스 정의 위치

**파일**: `app/domain/langgraph/utils/problem_info.py`

```python
HARDCODED_PROBLEM_SPEC = {
    10: {
        "test_cases": [
            {
                "input": "4\n0 10 15 20\n5 0 9 10\n6 13 0 12\n8 8 9 0\n",
                "expected": "35",
                "description": "기본 케이스: 4개 도시"
            },
            {
                "input": "3\n0 1 2\n1 0 3\n2 3 0\n",
                "expected": "6",
                "description": "최소 케이스: 3개 도시"
            },
            # ... 더 많은 TC
        ]
    }
}
```

**구조**:
- `input`: 표준 입력 (stdin)
- `expected`: 예상 출력 (정답)
- `description`: 테스트 케이스 설명

## 2. TC 추출 (execution.py)

**파일**: `app/domain/langgraph/nodes/holistic_evaluator/execution.py`

```python
# 문제 정보에서 테스트 케이스 가져오기
problem_context = state.get("problem_context", {})
test_cases_raw = problem_context.get("test_cases", [])

if test_cases_raw:
    # ⚠️ 첫 번째 테스트 케이스만 사용 (API 제한)
    first_tc = test_cases_raw[0]
    test_cases = [{
        "input": first_tc.get("input", ""),
        "expected": first_tc.get("expected", "")
    }]
    logger.info(f"[6c] 테스트 케이스 1개만 사용 (API 제한)")
else:
    test_cases = []
    logger.warning(f"[6c] 테스트 케이스 없음")
```

**중요**: 현재는 **첫 번째 TC만 사용**합니다 (API 제한 때문)

## 3. JudgeTask 생성 및 큐 추가

```python
correctness_task = JudgeTask(
    task_id=correctness_task_id,
    code=code_content,  # 제출 코드
    language=language,   # "python" (하드코딩)
    test_cases=test_cases,  # [{"input": "...", "expected": "..."}]
    timeout=timeout,
    memory_limit=memory_limit,
)

# 큐에 추가
await queue.enqueue(correctness_task)
```

## 4. JudgeWorker 처리

**파일**: `app/application/workers/judge_worker.py`

```python
async def _execute_task(self, task: JudgeTask) -> JudgeResult:
    if task.test_cases:
        # 여러 테스트 케이스 실행
        test_case_results = await self.judge0_client.execute_test_cases(
            code=task.code,
            language=task.language,
            test_cases=[
                {
                    "input": tc.get("input", ""),
                    "expected": tc.get("expected")
                }
                for tc in task.test_cases
            ],
            cpu_time_limit=task.timeout,
            memory_limit=task.memory_limit
        )
        
        # 결과 집계
        passed_count = sum(1 for r in test_case_results if r["passed"])
        total_count = len(test_case_results)
        
        # 상태 결정
        if passed_count == total_count:
            status = "success"
        else:
            status = "error"
```

## 5. Judge0Client 검증 로직

**파일**: `app/infrastructure/judge0/client.py`

```python
async def execute_test_cases(self, code, language, test_cases, ...):
    results = []
    
    for i, test_case in enumerate(test_cases):
        # Judge0 API 호출
        result = await self.execute_code(
            code=code,
            language=language,
            stdin=test_case.get("input", ""),  # 입력
            expected_output=test_case.get("expected"),  # 예상 출력
            wait=True
        )
        
        # ✅ 검증: stdout과 expected 비교
        status_id = result.get("status", {}).get("id")
        passed = (
            status_id == 3 and  # Accepted (Judge0 상태)
            result.get("stdout", "").strip() == test_case.get("expected", "").strip()
        )
        
        results.append({
            "test_case_index": i,
            "input": test_case.get("input", ""),
            "expected": test_case.get("expected", ""),
            "actual": result.get("stdout", "").strip(),  # 실제 출력
            "passed": passed,  # ✅ 통과 여부
            "status_id": status_id,
            "status_description": result.get("status", {}).get("description", ""),
            "time": result.get("time", "0"),
            "memory": result.get("memory", "0"),
        })
    
    return results
```

**검증 조건**:
1. Judge0 Status ID가 `3` (Accepted)인가?
2. `stdout.strip()` == `expected.strip()` 인가?

둘 다 만족하면 `passed = True`

## 6. Correctness Score 계산

**파일**: `app/domain/langgraph/nodes/holistic_evaluator/execution.py`

```python
if correctness_result.status == "success" and test_cases:
    # ✅ 성공 시 100점
    correctness_score = 100.0
    test_cases_passed = len(test_cases)
else:
    # ❌ 실패 시 0점
    correctness_score = 0.0
    test_cases_passed = 0
```

**현재 로직**:
- TC 1개만 사용
- 통과하면 100점, 실패하면 0점
- 부분 점수 없음

## 문제점 및 개선 사항

### 1. 첫 번째 TC만 사용
- **현재**: API 제한으로 첫 번째 TC만 사용
- **문제**: 다른 TC에서 실패할 수 있음
- **개선**: 여러 TC 실행 후 통과율 계산

### 2. 언어 정보 하드코딩
- **현재**: `language = "python"` (하드코딩)
- **문제**: 다른 언어 제출 시 오류
- **개선**: `state.get("lang")` 사용

### 3. 코드 형식 문제
- **현재**: 코드 그대로 전달
- **문제**: 마크다운 코드 블록 포함 시 실패
- **개선**: `clean_code()` 함수 사용

### 4. 검증 로직 단순화
- **현재**: `stdout.strip() == expected.strip()`
- **문제**: 공백/줄바꿈 차이로 실패 가능
- **개선**: 더 유연한 비교 로직

## 테스트 케이스 추가 방법

### 방법 1: problem_info.py에 직접 추가

```python
HARDCODED_PROBLEM_SPEC = {
    10: {
        "test_cases": [
            {
                "input": "4\n0 10 15 20\n5 0 9 10\n6 13 0 12\n8 8 9 0\n",
                "expected": "35",
                "description": "기본 케이스"
            },
            # 새 TC 추가
            {
                "input": "5\n0 1 2 3 4\n1 0 5 6 7\n2 5 0 8 9\n3 6 8 0 10\n4 7 9 10 0\n",
                "expected": "21",
                "description": "5개 도시 케이스"
            }
        ]
    }
}
```

### 방법 2: DB에서 가져오기 (추후 구현)

```python
# problem_specs.meta (JSON) 컬럼에 저장
{
    "test_cases": [
        {"input": "...", "expected": "...", "description": "..."}
    ]
}
```

## 디버깅 팁

### 1. 로그 확인
```bash
# JudgeWorker 로그
[JudgeWorker] 작업 처리 시작 - task_id: ...
[Judge0] 테스트 케이스 1/1 실행 중...
[Judge0] 테스트 케이스 실행 완료 - passed: True/False

# execution.py 로그
[6c] 테스트 케이스 1개만 사용 (API 제한)
[6c. Eval Code Execution] Correctness Score: 100.0
[6c. Eval Code Execution] test_cases_passed: 1/1
```

### 2. Judge0 결과 확인
```python
# Judge0 Status ID
3 = Accepted (성공)
4 = Wrong Answer (출력 불일치)
5 = Time Limit Exceeded
6 = Compilation Error
# ... 기타
```

### 3. 실제 출력 vs 예상 출력 비교
```python
# 로그에서 확인
actual: "35"
expected: "35"
passed: True/False
```

## 요약

| 단계 | 파일 | 역할 |
|------|------|------|
| 1. TC 정의 | `problem_info.py` | `test_cases` 배열에 `input`, `expected` 정의 |
| 2. TC 추출 | `execution.py` | 첫 번째 TC만 추출 (API 제한) |
| 3. Task 생성 | `execution.py` | JudgeTask 생성 후 큐에 추가 |
| 4. Worker 처리 | `judge_worker.py` | 큐에서 작업 가져와 Judge0 호출 |
| 5. 검증 | `judge0/client.py` | `stdout`과 `expected` 비교 |
| 6. 점수 계산 | `execution.py` | 통과 시 100점, 실패 시 0점 |

