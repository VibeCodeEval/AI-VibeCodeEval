# Judge0 Batch API · Genai Vertex LLM 통합

> **작성일**: 2026-05-17  
> **목적**: N5 Judge0 호출 최적화(Batched Submissions) 및 `ChatVertexAI` → `ChatGoogleGenerativeAI`(Vertex) 마이그레이션 기록

---

## 1. Judge0 — Batched Submissions

### 1.1 배경

- **이전**: `execute_test_cases()`가 TC마다 `POST /submissions` + 단건 폴링 → TC 10개 ≈ Submissions 할당 **10회** + GET 다수
- **RapidAPI 한도**(예): Submissions 50/일, **Batched Submissions 50/일** (별도 카운터)
- **목표**: TC ≥ 2일 때 생성·조회 HTTP를 batch로 묶어 **Batched Submissions** 할당 절약

### 1.2 동작 규칙 (`app/infrastructure/judge0/client.py`)

| TC 개수 | API | RapidAPI 카운터 |
|--------|-----|-----------------|
| 0 | 실행 안 함 | — |
| **1** | `POST /submissions` + 단건 폴링 | **Submissions** |
| **≥ 2** | `POST /submissions/batch` + `GET /submissions/batch` 폴링 | **Batched Submissions** (청크당 1회) |

- 청크 상한: `settings.JUDGE0_MAX_BATCH_SIZE` (기본 **20**, Judge0 CE 기본값과 동일)
- TC 21개 → batch POST 2회 + 조회 폴링 소수 회
- **채점 실행 횟수**(submission 수)는 TC 개수와 동일 — batch는 HTTP만 묶음

### 1.3 N5·Worker 연동

- `n5_integrated_evaluator.py`: `problem_context.test_cases` **전체**를 `JudgeTask`에 전달 (변경 없음)
- `judge_worker.py` → `execute_test_cases()` → 위 분기
- N5 로그: TC ≥ 2 → `Judge0 Batched Submissions`, TC 1 → `단일 submission`

### 1.4 검증

- Mock: `tests/test_judge0_client_batch.py`
- 실 API: `tests/test_judge0_integration.py`, `tmp/live_judge0_batch_check.py` (`.env` + RapidAPI 키)

### 1.5 설정 (`app/core/config.py`)

```env
JUDGE0_MAX_BATCH_SIZE=20   # 선택, 기본 20
```

---

## 2. LLM — ChatGoogleGenerativeAI + Vertex

### 2.1 배경

- `langchain-google-vertexai.ChatVertexAI` → LangChain 3.2+ **deprecated**
- `langchain-google-genai` 4.x: **동일 클래스**로 Vertex / AI Studio 백엔드 선택

### 2.2 동작 규칙 (`app/domain/langgraph/utils/llm_factory.py`)

| `USE_VERTEX_AI` | 클라이언트 | 인증 | 과금 |
|-----------------|------------|------|------|
| **true** (기본) | `ChatGoogleGenerativeAI(vertexai=True, project=..., location=..., credentials=...)` | `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` 또는 ADC | **GCP 프로젝트 (Vertex)** |
| **false** | `ChatGoogleGenerativeAI(google_api_key=GEMINI_API_KEY)` | API 키 | **Gemini Developer API (AI Studio)** |

- `app/core/vertex_auth.py`: SA JSON → `load_vertex_credentials()` (기존과 동일)
- **`GEMINI_API_KEY` 불필요** (Vertex 운영 시)
- `langchain-google-vertexai` **pyproject 의존성 제거** (`uv lock` 후 gRPC/aiplatform 대량 전이 패키지 정리됨)

### 2.3 pytest

- `tests/conftest.py`: `USE_VERTEX_AI=false`, `GEMINI_API_KEY=test-api-key` (수집 시점 모듈 import용)
- 운영 `.env`는 Vertex + SA JSON 유지

---

## 3. N5 부가 변경 (동일 작업 세션)

### 3.1 Correctness 만점 스케일

- `CODE_CORRECTNESS_MAX_POINTS`: **30 → 100**
- N5: `(통과 TC / 전체 TC) × 100`
- N9: `(raw / max) × 100` 환산 후 가중 40% (통과율 동일 시 총점 동일)

### 3.2 Performance — TC별 `passed`일 때만 채점

- **TC별**: `test_case_results[].passed=true`일 때만 해당 TC의 time·memory → raw 0~100
- **합산**: `(Σ raw / 전체 TC 수) × (CODE_PERFORMANCE_MAX_POINTS / 100)` (`config.py`)
- 실패 TC는 raw 0 기여 (Correctness와 동일하게 전체 TC 수가 분모)
- 스마트 게이트: 1/1 통과 시 합성 실행 메트릭 1건으로 Performance

---

## 4. 관련 파일

| 영역 | 파일 |
|------|------|
| Judge0 | `app/infrastructure/judge0/client.py`, `app/application/workers/judge_worker.py` |
| N5 | `app/domain/langgraph/nodes/eval/n5_integrated_evaluator.py` |
| LLM | `app/domain/langgraph/utils/llm_factory.py`, `app/core/vertex_auth.py` |
| 설정 | `app/core/config.py`, `pyproject.toml`, `uv.lock`, `requirements.txt` |
| 테스트 | `tests/test_judge0_client_batch.py`, `tests/test_n5_performance_gate.py`, `tests/conftest.py` |

---

## 5. 에이전트 담당 (참고)

| 주제 | 에이전트 |
|------|----------|
| Judge0·Submit·ENV | `submit_test_agent.md` |
| N5~N9 그래프 | `graph_orchestrator.md`, `holistic_score_agent.md` |
| LLM 팩토리 | `graph_orchestrator.md` / `project_maestro.md` |

일일 상세 diff: `.maestro/reports/daily/2026-05-17/`
