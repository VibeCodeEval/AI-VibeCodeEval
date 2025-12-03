# 테스트 케이스 및 언어 정보 위치

## ❌ 현재 상태

### 1. 테스트 케이스 API
**없습니다.** 현재 테스트 케이스를 가져오는 API 엔드포인트가 없습니다.

### 2. 테스트 케이스 저장 위치
**없습니다.** 현재 테스트 케이스가 저장되어 있지 않습니다.

---

## 📍 현재 정보 위치

### 1. 코드 (Code)
**위치**: `app/presentation/api/routes/chat.py` - `SubmitRequest`

```python
# app/presentation/schemas/chat.py
class SubmitRequest(BaseModel):
    code: str = Field(..., description="제출 코드")
    lang: str = Field("python", description="프로그래밍 언어")
```

**API 엔드포인트**: `POST /api/chat/submit`

**요청 예시**:
```json
{
  "session_id": "session-123",
  "exam_id": 1,
  "participant_id": 100,
  "spec_id": 10,
  "code": "def fibonacci(n):\n    return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)",
  "lang": "python"
}
```

---

### 2. 언어 정보 (Language)
**위치 1**: API 요청에서 받음 (`SubmitRequest.lang`)
- 기본값: `"python"`
- 예시: `"python"`, `"java"`, `"cpp"`, `"c"`, `"javascript"`, `"go"`, `"rust"`

**위치 2**: Judge0 언어 ID 매핑 (`app/infrastructure/judge0/client.py`)

```python
# app/infrastructure/judge0/client.py
class Judge0Client:
    LANGUAGE_IDS = {
        "python": 71,
        "python3": 71,
        "java": 62,
        "cpp": 54,
        "c++": 54,
        "c": 50,
        "javascript": 63,
        "nodejs": 63,
        "go": 60,
        "rust": 73,
    }
    
    def _get_language_id(self, language: str) -> int:
        """언어 이름을 Judge0 언어 ID로 변환"""
        return self.LANGUAGE_IDS.get(language.lower(), 71)  # 기본값: Python
```

**사용 위치**:
- `app/domain/langgraph/nodes/holistic_evaluator/performance.py` (6c 노드)
- `app/domain/langgraph/nodes/holistic_evaluator/correctness.py` (6d 노드)

**현재 문제**: 하드코딩으로 `"python"` 사용 중
```python
# TODO: state에서 언어 정보 가져오기
language = "python"  # TODO: state에서 언어 정보 가져오기
```

---

### 3. 테스트 케이스 (Test Cases)
**현재 상태**: ❌ 없음

**예상 저장 위치** (구현 필요):
1. **ProblemSpec.checker_json** (PostgreSQL)
   - `app/infrastructure/persistence/models/problems.py`
   - 현재는 JSONB 필드로만 정의되어 있음
   - 구조 미정의

2. **problem_context** (하드코딩 딕셔너리)
   - `app/domain/langgraph/utils/problem_info.py`
   - `HARDCODED_PROBLEM_SPEC`에 테스트 케이스 필드 없음

**현재 사용 위치**:
```python
# app/domain/langgraph/nodes/holistic_evaluator/correctness.py
test_cases = []  # TODO: problem_context에서 테스트 케이스 가져오기
```

---

## 🔍 파일 위치 정리

### 코드 (Code)
- **API 요청**: `app/presentation/schemas/chat.py` - `SubmitRequest.code`
- **State 저장**: `app/domain/langgraph/states.py` - `MainGraphState.code_content`
- **사용 위치**: 
  - `app/domain/langgraph/nodes/holistic_evaluator/performance.py`
  - `app/domain/langgraph/nodes/holistic_evaluator/correctness.py`

### 언어 (Language)
- **API 요청**: `app/presentation/schemas/chat.py` - `SubmitRequest.lang`
- **Judge0 ID 매핑**: `app/infrastructure/judge0/client.py` - `Judge0Client.LANGUAGE_IDS`
- **사용 위치**: 
  - `app/infrastructure/judge0/client.py` - `_get_language_id()`
  - `app/domain/langgraph/nodes/holistic_evaluator/performance.py` (하드코딩)
  - `app/domain/langgraph/nodes/holistic_evaluator/correctness.py` (하드코딩)

### 테스트 케이스 (Test Cases)
- **현재**: ❌ 없음
- **예상 위치**: 
  - `app/infrastructure/persistence/models/problems.py` - `ProblemSpec.checker_json` (구조 미정의)
  - `app/domain/langgraph/utils/problem_info.py` - `HARDCODED_PROBLEM_SPEC` (필드 없음)

---

## 🚨 문제점

1. **테스트 케이스 API 없음**
   - 테스트 케이스를 가져올 API 엔드포인트가 없음
   - 테스트 케이스 저장 구조가 정의되지 않음

2. **언어 정보 하드코딩**
   - 6c, 6d 노드에서 언어를 하드코딩으로 `"python"` 사용
   - `SubmitRequest.lang`을 State에 저장하지 않음

3. **테스트 케이스 저장 위치 미정**
   - `ProblemSpec.checker_json` 구조 미정의
   - `problem_context`에 테스트 케이스 필드 없음

---

## 💡 해결 방안

### 1. 언어 정보 State에 저장
```python
# app/domain/langgraph/states.py
class MainGraphState(TypedDict):
    # ...
    code_content: Optional[str]
    code_language: Optional[str]  # 추가 필요
```

### 2. 테스트 케이스 구조 정의
```python
# problem_context에 추가
{
    "test_cases": [
        {"input": "5", "expected": "10"},
        {"input": "10", "expected": "55"},
    ]
}
```

### 3. 테스트 케이스 API 추가 (선택사항)
```python
# app/presentation/api/routes/chat.py
@router.get("/problem/{spec_id}/test-cases")
async def get_test_cases(spec_id: int):
    # ProblemSpec.checker_json 또는 problem_context에서 가져오기
    pass
```

---

## 📝 요약

| 항목 | 위치 | 상태 |
|------|------|------|
| **코드** | `SubmitRequest.code` | ✅ 있음 |
| **언어 이름** | `SubmitRequest.lang` | ✅ 있음 |
| **언어 NUMBER** | `Judge0Client.LANGUAGE_IDS` | ✅ 있음 |
| **테스트 케이스** | 없음 | ❌ 없음 |
| **테스트 케이스 API** | 없음 | ❌ 없음 |

**다음 작업 필요**:
1. 언어 정보를 State에 저장
2. 테스트 케이스 구조 정의 및 저장
3. 테스트 케이스 가져오기 로직 구현

