# Judge0 가이드

> **최종 통합일**: 2026-03-27 | **원본**: Judge0_Complete_Guide.md, Judge0_Test_Case_Flow.md, QUICK_TEST.md

---

## 목차

1. [설정 및 구성](#1-설정-및-구성)
2. [API 및 통합](#2-api-및-통합)
3. [테스트 케이스 플로우](#3-테스트-케이스-플로우)
4. [빠른 실행](#4-빠른-실행)
5. [트러블슈팅](#5-트러블슈팅)
6. [파일 구조 및 관련 문서](#6-파일-구조-및-관련-문서)

---

## 1. 설정 및 구성

### Judge0 개요

Judge0는 **외부 API 서버(RapidAPI)**를 통해 사용하는 코드 실행 및 채점 서비스입니다.

- 로컬 서버 설치 불필요
- RapidAPI를 통한 외부 서버 사용
- 다양한 프로그래밍 언어 지원
- 테스트 케이스 실행 및 결과 평가

### 환경 변수 (`.env`)

**위치**: 프로젝트 루트 `.env`

```env
# Judge0 RapidAPI 설정 (외부 API 서버)
JUDGE0_API_URL=https://judge0-ce.p.rapidapi.com
JUDGE0_API_KEY=your_rapidapi_key_here
JUDGE0_USE_RAPIDAPI=true
JUDGE0_RAPIDAPI_HOST=judge0-ce.p.rapidapi.com

# 큐 시스템
USE_REDIS_QUEUE=true   # 프로덕션: Redis
# USE_REDIS_QUEUE=false  # 개발/테스트: 메모리
```

### 설정 정의 (`app/core/config.py`)

```python
class Settings(BaseSettings):
    JUDGE0_API_URL: str = "http://localhost:2358"  # 또는 "https://judge0-ce.p.rapidapi.com"
    JUDGE0_API_KEY: Optional[str] = None
    JUDGE0_USE_RAPIDAPI: bool = False
    JUDGE0_RAPIDAPI_HOST: str = "judge0-ce.p.rapidapi.com"
    USE_REDIS_QUEUE: bool = True
```

### RapidAPI 키 발급

1. [RapidAPI](https://rapidapi.com/) 회원가입/로그인
2. [Judge0 API](https://rapidapi.com/judge0-official/api/judge0-ce) 페이지 방문
3. "Subscribe to Test" 또는 유료 플랜 선택
4. API Key 복사 후 `.env`의 `JUDGE0_API_KEY`에 설정

### 설정 확인

```python
from app.core.config import settings

print(f"API URL: {settings.JUDGE0_API_URL}")
print(f"RapidAPI 사용: {settings.JUDGE0_USE_RAPIDAPI}")
print(f"API Key: {'설정됨' if settings.JUDGE0_API_KEY else '미설정'}")
```

### 설정 요약 표

| 항목 | 파일 | 환경 변수 |
|------|------|-----------|
| Judge0 URL | `app/core/config.py` | `JUDGE0_API_URL` |
| API Key | `app/core/config.py` | `JUDGE0_API_KEY` |
| RapidAPI 사용 | `app/core/config.py` | `JUDGE0_USE_RAPIDAPI` |
| RapidAPI Host | `app/core/config.py` | `JUDGE0_RAPIDAPI_HOST` |
| 큐 시스템 | `app/core/config.py` | `USE_REDIS_QUEUE` |

### 주의사항

- `.env`는 `.gitignore`에 포함
- RapidAPI 무료 플랜은 Rate Limit 가능
- 제출 플로우에서는 **테스트 케이스 1개**만 사용 (API·비용 제한)
- **Judge0 Worker**가 실행 중이어야 큐 작업이 처리됨

---

## 2. API 및 통합

### Judge0 API 기본 흐름

```
1. 코드 제출 (POST /submissions)
   ↓
2. 토큰 수신
   ↓
3. 결과 조회 (GET /submissions/{token}) — 폴링
   ↓
4. 결과 분석
```

### 제출 시 필요한 정보

**필수**

- `source_code`: 실행할 코드
- `language_id`: 언어 ID (Python=71, Java=62 등)
- `stdin`: 테스트 입력

**권장 (평가용)**

- `expected_output`: 예상 출력
- `cpu_time_limit`, `memory_limit`

### 언어 ID (`app/infrastructure/judge0/client.py`)

```python
LANGUAGE_IDS = {
    "python": 71, "python3": 71,
    "java": 62,
    "cpp": 54, "c++": 54,
    "c": 50,
    "javascript": 63, "nodejs": 63,
    "go": 60,
    "rust": 73,
}
```

### HTTP 헤더

**RapidAPI**

```python
headers = {
    "Content-Type": "application/json",
    "x-rapidapi-key": "your_rapidapi_key",
    "x-rapidapi-host": "judge0-ce.p.rapidapi.com"
}
```

**로컬 Judge0**

```python
headers = {
    "Content-Type": "application/json",
    "X-Auth-Token": "your_api_key"
}
```

### 큐 시스템

**위치**: `app/domain/queue/`

```
Judge0 API 호출 요청
   ↓
큐에 작업 추가 (enqueue)
   ↓
Judge0 Worker가 dequeue
   ↓
Judge0 API로 코드 실행
   ↓
결과를 Redis에 저장
   ↓
LangGraph 노드가 폴링으로 결과 확인
```

- **인터페이스**: `app/domain/queue/adapters/base.py` — `QueueAdapter`, `JudgeTask`, `JudgeResult`
- **구현**: `MemoryQueueAdapter`, `RedisQueueAdapter`
- **팩토리**: `app/domain/queue/factory.py` — `create_queue_adapter()`

### 6번 노드 통합 (6c Execution)

**변경**: 기존 6c(Performance) + 6d(Correctness) → **6c(Execution) 하나로 통합**

**평가 순서**

```
6b → 6c (Execution)
   ↓
1. Correctness (테스트 케이스 통과)
   ↓ 실패 → Performance 생략, 점수 0
   ↓ 통과
2. Performance (시간·메모리)
```

- **노드 구현**: `app/domain/langgraph/nodes/holistic_evaluator/execution.py` — `eval_code_execution()`
- **그래프**: `app/domain/langgraph/graph.py` — `6b → 6c → 7`

### API 호출 분석

`app/infrastructure/judge0/client.py`의 `execute_test_cases`는 **테스트 케이스마다** `execute_code`를 호출합니다.

**1개 TC 실행 시 (대략)**

- 제출 1회 (`POST /submissions`)
- 결과 조회 1회 이상 (폴링)

**여러 TC** (현재 제출 플로우에서는 1개만 사용): 호출 수가 TC 개수에 비례해 증가합니다.

**향후 개선 아이디어**: 병렬 실행, 배치 API(지원 시), 중요 TC만 선택 실행.

### 애플리케이션 전체 플로우 (요약)

```
코드 제출
   ↓
6c (Execution)
   ↓
Correctness (TC 1개) → 큐 → Worker → Judge0 → 폴링
   ↓ 실패 → Performance 생략
   ↓ 통과
Performance → 큐 → Worker → Judge0 → 폴링
   ↓
7. 최종 점수 집계
```

---

## 3. 테스트 케이스 플로우

### 단계별 개요

```
problem_info.py (TC 정의)
   ↓
execution.py (6c — TC 추출·스마트 게이트 분기)
   ↓
JudgeTask 생성 → 큐 enqueue
   ↓
JudgeWorker dequeue
   ↓
test_cases 유무에 따라 execute_code / execute_test_cases
   ↓
stdout vs expected 비교 (일반 TC)
   ↓
correctness_score 계산
```

### 1. 테스트 케이스 정의

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
            # 추가 TC...
        ]
    }
}
```

- `input`: stdin
- `expected`: 예상 출력
- `description`: 설명

### 2. 6c에서 `JudgeTask` 구성 (스마트 게이트 vs 일반 TC)

**파일**: `app/domain/langgraph/nodes/holistic_evaluator/execution.py`

- **스마트 게이트(예: spec_id 11/20)**  
  - `code_to_run` = 사용자 코드 전체 + `"\n"` + `test_suite_code` 전체  
  - `test_cases` = `[]`  
  - 테스트는 코드 문자열에 포함, stdin/expected는 사용하지 않음.

- **그 외(입출력 TC 방식)**  
  - `code_to_run` = 사용자 코드만  
  - `test_cases` = `[{"input": "...", "expected": "..."}]` — **첫 번째 TC 1개만** (아래 제한 참고)

```python
correctness_task = JudgeTask(
    task_id=correctness_task_id,
    code=code_to_run,
    language=language,
    test_cases=test_cases,
    timeout=...,
    memory_limit=...,
    meta={...},
)
await queue.enqueue(correctness_task)
```

### 3. 첫 번째 테스트 케이스만 사용 (제출 플로우)

**파일**: `execution.py`

```python
test_cases_raw = problem_context.get("test_cases", [])
if test_cases_raw:
    first_tc = test_cases_raw[0]
    test_cases = [{
        "input": first_tc.get("input", ""),
        "expected": first_tc.get("expected", "")
    }]
    test_cases_total = 1
```

**기본으로 쓰이는 첫 TC 예**: 4개 도시, Input 위와 동일, Expected `35`.

효과(문서상 목표): API 호출·실행 시간·대기 시간 감소.

### 4. Redis 직렬화

**파일**: `app/domain/queue/adapters/redis.py`

- `JudgeTask`를 dict로 만든 뒤 `json.dumps(..., ensure_ascii=False)`로 직렬화, Redis List에 `LPUSH`.
- Worker는 동일 큐를 `BRPOP`으로 읽음. **백엔드와 Worker는 같은 Redis·같은 큐 키**를 써야 함.

### 5. Worker → Judge0

**파일**: `app/application/workers/judge_worker.py` — `_execute_task(task)`

- `task.test_cases`가 **비어 있음** (스마트 게이트):  
  `judge0_client.execute_code(code=task.code, stdin="", ...)` **한 번**
- `task.test_cases`가 **있음** (일반 TC):  
  `judge0_client.execute_test_cases(code=task.code, test_cases=..., ...)`

정리: **코드**는 항상 `task.code` → Judge0 `source_code`. **테스트**는 코드 내부(스마트 게이트) 또는 `test_cases`의 input/expected(일반 TC).

### 6. `execute_test_cases` 검증 (`client.py`)

```python
async def execute_test_cases(self, code, language, test_cases, ...):
    for i, test_case in enumerate(test_cases):
        result = await self.execute_code(
            code=code,
            language=language,
            stdin=test_case.get("input", ""),
            expected_output=test_case.get("expected"),
            wait=True
        )
        status_id = result.get("status", {}).get("id")
        passed = (
            status_id == 3
            and (result.get("stdout") or "").strip() == test_case.get("expected", "").strip()
        )
        # results에 test_case_index, input, expected, actual, passed 등 저장
```

- Judge0 Status ID **3** = Accepted 이고, `stdout.strip() == expected.strip()`이면 통과.

### 7. Correctness 점수 (`execution.py`)

- TC를 쓰는 경로에서 성공 시 **100점**, 실패 시 **0점** (부분 점수 없음, 현재 TC 1개 기준).

### Worker 처리 개요 (`judge_worker.py`)

`task.test_cases`가 있으면 `execute_test_cases`로 결과를 모으고, `passed_count == total_count`이면 `status = "success"`, 아니면 `"error"`.

### 백엔드만 실패할 때 점검 포인트

1. **problem_context / spec_id**  
   스마트 게이트를 타야 하는데 일반 TC 분기만 타면 `code_to_run`에 test_suite가 안 붙고, `test_cases`도 비면 사용자 코드만 stdin 없이 실행될 수 있음.

2. **Redis/큐 불일치**  
   API와 Worker의 Redis URL·큐 키가 다르면 enqueue한 작업을 Worker가 읽지 못함.

3. **Judge0 `stdout: null`**  
   `(result.get("stdout") or "").strip()` 등으로 방어 (`client.py`).

### 알려진 한계·개선 아이디어

- 첫 TC만 사용 → 다른 TC에서 틀릴 위험; 여러 TC·통과율 반영은 향후 과제.
- 언어가 `"python"` 하드코딩된 경로가 있으면 다른 언어 제출 시 문제 가능 → `state`의 언어 필드 사용 권장.
- 마크다운 코드 블록이 섞인 코드 → `clean_code()` 등 정규화 고려.
- `stdout`과 `expected`를 단순 `strip()` 비교 → 공백·줄바꿈 차이에 유연한 비교 검토.

### 테스트 케이스 추가

**방법 1**: `problem_info.py`의 `HARDCODED_PROBLEM_SPEC`에 `test_cases` 항목 추가.

**방법 2 (추후)**: DB `problem_specs.meta` 등 JSON에 `test_cases` 저장.

### 플로우 요약 표

| 단계 | 파일 | 역할 |
|------|------|------|
| TC 정의 | `problem_info.py` | `input` / `expected` / `description` |
| TC 추출·분기 | `execution.py` | 첫 TC만·스마트 게이트 분기 |
| Task·큐 | `execution.py` | `JudgeTask` enqueue |
| Worker | `judge_worker.py` | dequeue 후 Judge0 호출 |
| 검증 | `judge0/client.py` | Status 3 + stdout vs expected |
| 점수 | `execution.py` | 통과 100 / 실패 0 |

### 디버깅용 로그 예시

- Worker: 작업 시작, `테스트 케이스 1/1`, `passed`
- 6c: `테스트 케이스 1개만 사용 (API 제한)`, Correctness 점수, `test_cases_passed`

---

## 4. 빠른 실행

### Judge0·스크립트 연결 확인

```bash
uv run python test_scripts/check_judge0_connection.py
```

### Judge0 API 스크립트

```bash
uv run python test_scripts/test_judge0_api.py --single   # 단일 TC
uv run python test_scripts/test_judge0_api.py            # 전체(현재도 1 TC 위주)
```

### `test_judge0_submit.py` (파일 기반)

**자주 쓰는 파일**: `solution.py`(제출할 코드), `test_cases.json`(TC 정의). 경로는 프로젝트 레이아웃에 맞게 지정.

**PowerShell (Windows)**

```powershell
# 기본: 첫 TC만
uv run python test_scripts/test_judge0_submit.py --code-file solution.py --test-cases test_cases.json

# 제약 조건 JSON 포함
uv run python test_scripts/test_judge0_submit.py --code-file solution.py --test-cases test_cases.json --constraints test_scripts/constraints.json

# 모든 TC (스크립트 옵션)
uv run python test_scripts/test_judge0_submit.py --code-file solution.py --test-cases test_cases.json --all-tc

# spec_id (하드코딩 스펙)
uv run python test_scripts/test_judge0_submit.py --code-file solution.py --spec-id 10
```

**Bash (Linux/Mac)**

```bash
uv run python test_scripts/test_judge0_submit.py \
  --code-file solution.py \
  --test-cases test_cases.json

uv run python test_scripts/test_judge0_submit.py \
  --code-file solution.py \
  --test-cases test_cases.json \
  --constraints test_scripts/constraints.json

uv run python test_scripts/test_judge0_submit.py \
  --code-file solution.py \
  --test-cases test_cases.json \
  --all-tc

uv run python test_scripts/test_judge0_submit.py \
  --code-file solution.py \
  --spec-id 10
```

### Worker·API 서버·curl 예시

```bash
# Worker (터미널 1)
python -m app.application.workers.judge_worker

# 확장 시 Worker 여러 개 동시 실행 가능 (각각 별도 터미널)

# API 서버 (터미널 2)
uvicorn app.main:app --reload
```

```bash
curl -X POST http://localhost:8000/api/chat/submit \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session",
    "exam_id": 1,
    "participant_id": 100,
    "spec_id": 10,
    "code": "print(\"hello\")",
    "lang": "python"
  }'
```

### 예상 출력 (`test_judge0_submit.py`)

```
================================================================================
Judge0 코드 제출 및 평가 시작
================================================================================

[1단계] 직접 제공된 테스트 케이스 사용
✅ 총 4개의 테스트 케이스 발견
⚠️ 첫 번째 테스트 케이스만 사용 (API 제한) - 기본 케이스: 4개 도시

[2단계] 테스트 케이스 추출
⚠️ 첫 번째 테스트 케이스만 사용 (API 제한) - 기본 케이스: 4개 도시

[3단계] 제약 조건
  - 시간 제한: 1.0초
  - 메모리 제한: 128MB
  - 언어: python

[4단계] 코드 형식 확인
  - 코드 길이: 500 문자
  - 코드 바이트 (UTF-8): 512 bytes
  - 줄바꿈: \n (LF)
  ✅ 순수 코드 (마크다운 코드 블록 없음)

[5단계] Judge0 실행
  - 테스트 케이스: 1개
  - 코드 형식: 원본 그대로 (실제 Flow와 동일)

[6단계] Judge0 실행 결과
================================================================================

✅ 테스트 케이스 1: 기본 케이스: 4개 도시
  입력: 4\n0 10 15 20\n5 0 9 10\n6 13 0 12\n8 8 9 0\n
  예상 출력: 35
  실제 출력: 35
  통과 여부: ✅ 통과
  Judge0 Status: Accepted (ID: 3)
  실행 시간: 0.123초
  메모리 사용: 1024KB

[7단계] 점수 계산
================================================================================

📊 Correctness 점수
  점수: 100.0점
  통과: 1/1
  통과율: 100.0%

⚡ Performance 점수
  점수: 100.0점
  시간 점수: 100.0점 (실행 시간: 0.123초)
  메모리 점수: 100.0점 (메모리: 1.00MB)

================================================================================
최종 결과
================================================================================
✅ Correctness: 100.0점
⚡ Performance: 100.0점
📈 종합 점수 (Correctness 50% + Performance 25%): 75.0점

✅ 평가 완료!
```

---

## 5. 트러블슈팅

### "All connection attempts failed"

- Judge0/RapidAPI에 연결 불가.

**조치**

1. `.env` 확인: `JUDGE0_API_URL`, `JUDGE0_API_KEY`, `JUDGE0_USE_RAPIDAPI=true`, `JUDGE0_RAPIDAPI_HOST`
2. `uv run python test_scripts/check_judge0_connection.py` 실행
3. RapidAPI 대시보드에서 Judge0 구독·키 활성 상태 확인

### Judge0 연결·환경 변수

```env
JUDGE0_API_URL=...
JUDGE0_API_KEY=...
JUDGE0_USE_RAPIDAPI=...
```

### 파일을 찾을 수 없음

프로젝트 **루트**에서 실행:

```powershell
cd C:\P-project\AI-VibeCodeEval
uv run python test_scripts/test_judge0_submit.py --code-file solution.py --test-cases test_cases.json
```

### Judge0 Status ID (참고)

- **3**: Accepted (성공)
- **4**: Wrong Answer
- **5**: Time Limit Exceeded
- **6**: Compilation Error  
(기타 ID는 Judge0 문서 참고)

### 실제 출력 vs 예상

로그에서 `actual` / `expected` / `passed`를 비교.

---

## 6. 파일 구조 및 관련 문서

### 코드·테스트 스크립트 위치

```
app/
├── core/config.py
├── domain/queue/
│   ├── adapters/base.py, memory.py, redis.py
│   └── factory.py
├── domain/langgraph/nodes/holistic_evaluator/execution.py
├── domain/langgraph/utils/problem_info.py
├── infrastructure/judge0/client.py
└── application/workers/judge_worker.py

test_scripts/
├── check_judge0_connection.py
├── test_judge0_api.py
└── test_judge0_submit.py

docs/
└── Judge0_가이드.md
```

### 관련 문서

- `docs/Judge0_API_Guide.md`
- `docs/Judge0_RapidAPI_Setup.md`
- `docs/Judge0_Integration_Guide.md`
- `docs/Judge0_Connection_Troubleshooting.md`
- `docs/Judge0_API_Call_Analysis.md`
- `docs/Node6_Integration_Change.md`
- `docs/Test_Case_Limit_Change.md`

### 한 페이지 요약

- **설정**: `.env` + `app/core/config.py`, RapidAPI 또는 로컬 Judge0
- **기능**: Redis/Memory 큐, 6c에서 Correctness 후 Performance
- **TC**: 제출 플로우에서는 1개; 스마트 게이트는 코드에 test suite 내장
- **실행**: Worker 필수, 연결은 `check_judge0_connection.py`로 확인
