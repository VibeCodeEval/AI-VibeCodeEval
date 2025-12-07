# Judge0 완전 가이드

## 📋 목차

1. [Judge0 개요](#judge0-개요)
2. [설정 방법](#설정-방법)
3. [API 작동 방식](#api-작동-방식)
4. [통합 구조](#통합-구조)
5. [6번 노드 통합](#6번-노드-통합)
6. [테스트 케이스 제한](#테스트-케이스-제한)
7. [API 호출 분석](#api-호출-분석)
8. [문제 해결](#문제-해결)

---

## Judge0 개요

Judge0는 **외부 API 서버(RapidAPI)**를 통해 사용하는 코드 실행 및 채점 서비스입니다.

**특징**:
- 로컬 서버 설치 불필요
- RapidAPI를 통한 외부 서버 사용
- 다양한 프로그래밍 언어 지원
- 테스트 케이스 실행 및 결과 평가

---

## 설정 방법

### 1. 환경 변수 파일 (`.env`)

**파일 위치**: 프로젝트 루트의 `.env` 파일

```env
# Judge0 RapidAPI 설정 (외부 API 서버)
JUDGE0_API_URL=https://judge0-ce.p.rapidapi.com
JUDGE0_API_KEY=your_rapidapi_key_here
JUDGE0_USE_RAPIDAPI=true
JUDGE0_RAPIDAPI_HOST=judge0-ce.p.rapidapi.com
```

### 2. 설정 파일 (정의)

**파일 위치**: `app/core/config.py`

```python
class Settings(BaseSettings):
    # Judge0 설정 (코드 실행 평가)
    JUDGE0_API_URL: str = "http://localhost:2358"  # 또는 "https://judge0-ce.p.rapidapi.com"
    JUDGE0_API_KEY: Optional[str] = None
    JUDGE0_USE_RAPIDAPI: bool = False  # RapidAPI 사용 여부
    JUDGE0_RAPIDAPI_HOST: str = "judge0-ce.p.rapidapi.com"  # RapidAPI Host
```

### 3. RapidAPI Key 발급

1. [RapidAPI](https://rapidapi.com/) 회원가입/로그인
2. [Judge0 API](https://rapidapi.com/judge0-official/api/judge0-ce) 페이지 방문
3. "Subscribe to Test" 또는 유료 플랜 선택
4. API Key 복사
5. `.env` 파일의 `JUDGE0_API_KEY`에 붙여넣기

### 4. 설정 확인

```python
from app.core.config import settings

print(f"API URL: {settings.JUDGE0_API_URL}")
print(f"RapidAPI 사용: {settings.JUDGE0_USE_RAPIDAPI}")
print(f"API Key: {'설정됨' if settings.JUDGE0_API_KEY else '미설정'}")
```

**예상 출력**:
```
API URL: https://judge0-ce.p.rapidapi.com
RapidAPI 사용: True
API Key: 설정됨
```

### 5. 연결 테스트

```bash
uv run python test_scripts/check_judge0_connection.py
```

---

## API 작동 방식

### 기본 흐름

```
1. 코드 제출 (POST /submissions)
   ↓
2. 토큰 받기
   ↓
3. 결과 조회 (GET /submissions/{token}) - 폴링
   ↓
4. 결과 분석
```

### 필요한 정보

**필수**:
- `source_code`: 실행할 코드
- `language_id`: 언어 ID (Python=71, Java=62 등)
- `stdin`: 테스트 케이스 입력

**권장** (평가를 위해):
- `expected_output`: 예상 출력 (정확성 평가용)
- `cpu_time_limit`: 시간 제한 (성능 평가용)
- `memory_limit`: 메모리 제한 (성능 평가용)

### 언어 ID 매핑

**파일 위치**: `app/infrastructure/judge0/client.py`

```python
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
```

### 헤더 형식

**RapidAPI 사용 시**:
```python
headers = {
    "Content-Type": "application/json",
    "x-rapidapi-key": "your_rapidapi_key",
    "x-rapidapi-host": "judge0-ce.p.rapidapi.com"
}
```

**일반 Judge0 사용 시** (로컬 서버):
```python
headers = {
    "Content-Type": "application/json",
    "X-Auth-Token": "your_api_key"
}
```

---

## 통합 구조

### 큐 시스템

**파일 위치**: `app/domain/queue/`

```
Judge0 API 호출
   ↓
큐에 작업 추가 (enqueue)
   ↓
Judge0 Worker가 큐에서 가져오기 (dequeue)
   ↓
Judge0 API로 코드 실행
   ↓
결과를 Redis에 저장
   ↓
LangGraph 노드가 폴링으로 결과 확인
```

### 어댑터 패턴

**인터페이스**: `app/domain/queue/adapters/base.py`
- `QueueAdapter`: 추상 인터페이스
- `JudgeTask`: 코드 실행 태스크
- `JudgeResult`: 실행 결과

**구현**:
- `MemoryQueueAdapter`: 메모리 기반 (개발/테스트)
- `RedisQueueAdapter`: Redis 기반 (프로덕션)

**팩토리**: `app/domain/queue/factory.py`
- `create_queue_adapter()`: 설정에 따라 적절한 어댑터 생성

### 설정

**파일 위치**: `app/core/config.py`

```python
USE_REDIS_QUEUE: bool = True  # True: Redis 큐, False: 메모리 큐
```

**환경 변수**: `.env`

```env
USE_REDIS_QUEUE=true  # Redis 사용 (프로덕션)
# USE_REDIS_QUEUE=false  # 메모리 사용 (개발/테스트)
```

---

## 6번 노드 통합

### 변경 사항

**변경 전**: 6c (Performance) + 6d (Correctness) = 2개 노드

**변경 후**: 6c (Execution) = 1개 노드 (통합)

### 평가 순서

```
6b → 6c (Execution)
   ↓
1. Correctness 평가 (테스트 케이스 통과율)
   ↓
   [실패?] → Performance 평가 건너뛰고 바로 종료 (점수: 0)
   ↓
   [통과?] → Performance 평가 진행
   ↓
2. Performance 평가 (실행 시간, 메모리 사용량)
```

### 파일 위치

**통합 노드**: `app/domain/langgraph/nodes/holistic_evaluator/execution.py`
- 함수: `eval_code_execution()`

**그래프 연결**: `app/domain/langgraph/graph.py`
- 노드: `eval_code_execution`
- 엣지: `6b → 6c → 7`

### 장점

1. **효율성**: Correctness 실패 시 Performance 평가 건너뛰기
2. **비용 절감**: 불필요한 API 호출 제거
3. **논리적 흐름**: 정확성 먼저, 성능은 그 다음
4. **관리 용이**: 하나의 노드에서 관리

---

## 테스트 케이스 제한

### 현재 설정

**API 제한으로 인해 제출 플로우에서 테스트 케이스 1개만 사용**

**파일 위치**: `app/domain/langgraph/nodes/holistic_evaluator/execution.py`

```python
# 테스트 케이스 준비 (API 제한으로 인해 첫 번째 TC만 사용)
test_cases_raw = problem_context.get("test_cases", [])
if test_cases_raw:
    # 첫 번째 테스트 케이스만 사용
    first_tc = test_cases_raw[0]
    test_cases = [{
        "input": first_tc.get("input", ""),
        "expected": first_tc.get("expected", "")
    }]
    test_cases_total = 1  # API 제한으로 1개만 사용
```

### 사용되는 테스트 케이스

**첫 번째 테스트 케이스** (기본 케이스: 4개 도시)
- Input: `4\n0 10 15 20\n5 0 9 10\n6 13 0 12\n8 8 9 0\n`
- Expected: `35`

### 효과

- **API 호출**: 20번 이상 → 2번 (90% 절감)
- **실행 시간**: ~10-20초 → ~1-2초 (80-90% 단축)
- **대기 시간**: 60초 → 30초

---

## API 호출 분석

### 현재 구현 방식

**각 테스트 케이스마다 별도의 API 호출 발생**

```python
# app/infrastructure/judge0/client.py
async def execute_test_cases(...):
    for i, test_case in enumerate(test_cases):  # 각 TC마다 반복
        result = await self.execute_code(...)   # 각 TC마다 API 호출
```

### 호출 횟수

**1개 테스트 케이스 실행 시**:
- 제출: 1번 (`POST /submissions`)
- 결과 조회: 1번 이상 (`GET /submissions/{token}` - 폴링)
- **총 2번 이상의 API 호출**

**10개 테스트 케이스 실행 시** (현재는 사용 안 함):
- 제출: 10번
- 결과 조회: 10번 이상
- **총 20번 이상의 API 호출**

### 개선 방안 (향후)

1. **병렬 처리**: 여러 TC를 동시에 실행
2. **배치 처리**: Judge0가 배치 API를 지원한다면 사용
3. **선택적 실행**: 중요한 TC만 선택

---

## 문제 해결

### 에러: "All connection attempts failed"

**원인**: Judge0 서버에 연결할 수 없음

**해결 방법**:

#### 1. RapidAPI 설정 확인

`.env` 파일 확인:
```env
JUDGE0_API_URL=https://judge0-ce.p.rapidapi.com
JUDGE0_API_KEY=your_rapidapi_key_here
JUDGE0_USE_RAPIDAPI=true
JUDGE0_RAPIDAPI_HOST=judge0-ce.p.rapidapi.com
```

#### 2. 연결 확인

```bash
uv run python test_scripts/check_judge0_connection.py
```

#### 3. RapidAPI Key 확인

- RapidAPI 대시보드에서 Judge0 API 구독 확인
- API Key가 활성화되어 있는지 확인

---

## 사용 방법

### 1. Judge0 Worker 실행

```bash
# Judge0 Worker 실행
python -m app.application.workers.judge_worker
```

**여러 Worker 실행** (확장):
```bash
# 터미널 1
python -m app.application.workers.judge_worker

# 터미널 2
python -m app.application.workers.judge_worker
```

### 2. API 서버 실행

```bash
uvicorn app.main:app --reload
```

### 3. 코드 제출

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

---

## 테스트

### 1. 연결 확인

```bash
uv run python test_scripts/check_judge0_connection.py
```

### 2. 단일 테스트 케이스

```bash
uv run python test_scripts/test_judge0_api.py --single
```

### 3. 전체 테스트 (현재는 1개 TC만 사용)

```bash
uv run python test_scripts/test_judge0_api.py
```

---

## 파일 구조

```
app/
├── core/
│   └── config.py                    # Judge0 설정 정의
├── domain/
│   ├── queue/                       # 큐 시스템
│   │   ├── adapters/
│   │   │   ├── base.py              # 인터페이스
│   │   │   ├── memory.py            # 메모리 어댑터
│   │   │   └── redis.py             # Redis 어댑터
│   │   └── factory.py               # 팩토리
│   └── langgraph/
│       └── nodes/
│           └── holistic_evaluator/
│               └── execution.py     # 6c 통합 노드
├── infrastructure/
│   └── judge0/
│       ├── __init__.py
│       └── client.py                 # Judge0 API 클라이언트
└── application/
    └── workers/
        └── judge_worker.py           # Judge0 Worker

test_scripts/
├── check_judge0_connection.py       # 연결 확인
└── test_judge0_api.py               # API 테스트

docs/
└── Judge0_Complete_Guide.md         # 이 문서
```

---

## 설정 요약

### 필수 설정 (`.env`)

```env
# Judge0 RapidAPI 설정
JUDGE0_API_URL=https://judge0-ce.p.rapidapi.com
JUDGE0_API_KEY=your_rapidapi_key_here
JUDGE0_USE_RAPIDAPI=true
JUDGE0_RAPIDAPI_HOST=judge0-ce.p.rapidapi.com

# 큐 시스템 설정
USE_REDIS_QUEUE=true  # Redis 사용 (프로덕션)
```

### 설정 파일 위치

| 설정 항목 | 파일 위치 | 환경 변수 |
|----------|----------|----------|
| **Judge0 URL** | `app/core/config.py` | `JUDGE0_API_URL` |
| **Judge0 API Key** | `app/core/config.py` | `JUDGE0_API_KEY` |
| **RapidAPI 사용** | `app/core/config.py` | `JUDGE0_USE_RAPIDAPI` |
| **RapidAPI Host** | `app/core/config.py` | `JUDGE0_RAPIDAPI_HOST` |
| **큐 시스템** | `app/core/config.py` | `USE_REDIS_QUEUE` |

---

## 📊 전체 플로우

```
코드 제출
   ↓
6c 노드 (Execution)
   ↓
1. Correctness 평가 (TC 1개)
   - 큐에 작업 추가
   - Worker가 Judge0 API 호출
   - 결과 폴링
   ↓
   [실패?] → Performance 건너뛰기, 점수 0
   ↓
   [통과?] → Performance 평가 진행
   ↓
2. Performance 평가
   - 큐에 작업 추가
   - Worker가 Judge0 API 호출
   - 결과 폴링
   ↓
7. 최종 점수 집계
```

---

## ⚠️ 주의사항

1. **API Key 보안**: `.env` 파일은 `.gitignore`에 포함되어 있어야 합니다
2. **Rate Limit**: RapidAPI 무료 플랜은 호출 제한이 있을 수 있습니다
3. **테스트 케이스**: 현재는 API 제한으로 1개만 사용
4. **Worker 실행**: Judge0 Worker가 실행 중이어야 큐에서 작업을 처리합니다

---

## 📝 요약

### 설정 위치
- **환경 변수**: `.env` 파일
- **설정 정의**: `app/core/config.py`

### 주요 기능
- ✅ RapidAPI Judge0 사용 (외부 API 서버)
- ✅ 큐 시스템 (Redis/Memory)
- ✅ 6c 노드 통합 (Correctness → Performance)
- ✅ 테스트 케이스 1개만 사용 (API 제한)

### 실행 순서
1. Correctness 평가 (TC 1개)
2. 통과 시 Performance 평가
3. 실패 시 Performance 건너뛰기

### 파일 위치
- Judge0 클라이언트: `app/infrastructure/judge0/client.py`
- Judge0 Worker: `app/application/workers/judge_worker.py`
- 6c 통합 노드: `app/domain/langgraph/nodes/holistic_evaluator/execution.py`
- 큐 시스템: `app/domain/queue/`

---

## 🔗 관련 문서

- `docs/Judge0_API_Guide.md`: API 작동 방식 상세
- `docs/Judge0_RapidAPI_Setup.md`: RapidAPI 설정 가이드
- `docs/Judge0_Integration_Guide.md`: 통합 가이드
- `docs/Judge0_Connection_Troubleshooting.md`: 문제 해결
- `docs/Judge0_API_Call_Analysis.md`: API 호출 분석
- `docs/Node6_Integration_Change.md`: 6번 노드 통합 변경
- `docs/Test_Case_Limit_Change.md`: 테스트 케이스 제한 변경

