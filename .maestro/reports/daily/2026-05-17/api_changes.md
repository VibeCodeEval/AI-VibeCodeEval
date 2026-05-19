# API·인터페이스 변경 기록 — 2026-05-17

> Judge0 호출 방식, LangGraph State(N5), LLM 백엔드

---

## 1. Judge0 (외부 RapidAPI)

### 변경 요약

| 항목 | 이전 | 이후 |
|------|------|------|
| TC 1 | `POST /submissions` × 1 | 동일 |
| TC N (N≥2) | `POST /submissions` × N | `POST /submissions/batch` × ⌈N/20⌉ |
| 결과 조회 | `GET /submissions/{token}` × N | `GET /submissions/batch?tokens=...` 폴링 |
| Worker → N5 매핑 | `passed`, `time`, `memory` per TC | **동일** (`JudgeResult.passed_test_cases` 등) |

### 호환성

- `code_correctness_score`, `code_performance_score`, `test_cases_passed/total` State 필드 **스키마 변경 없음**
- `skip_performance`, `skip_reason` — 부분 TC 실패 시에도 설정 (Performance 0일 때)

### 할당량 (RapidAPI)

- **Submissions**: TC 1건 제출마다 1
- **Batched Submissions**: batch 생성 1회당 1 (TC 10 → 보통 1)
- 실행(컴파일) 횟수는 submission 수와 동일 — batch가 실행 횟수를 줄이지는 않음

---

## 2. LangGraph State (N5 출력)

### Performance (TC별)

| 필드 | 변경 |
|------|------|
| `code_performance_score` | **passed TC마다** time·memory raw → `(Σ raw / 전체 TC) × (CODE_PERFORMANCE_MAX_POINTS/100)` |
| `JudgeResult.test_case_results` | per-TC `passed`, `time`, `memory` (Worker) |
| `skip_performance` | passed TC에 메트릭 없을 때 등 |
| `skip_reason` | 예: `부분 TC만 Performance 반영 (2/3)` |
| `code_correctness_score` | `(passed/total)×CODE_CORRECTNESS_MAX_POINTS`, max **100** |

### N9 총점 영향

- Performance 20%: 부분 통과 시 **맞은 TC 품질**까지 반영
- Correctness 40%: 통과율 반영 (변경 없음)

---

## 3. LLM (내부)

| 항목 | 이전 | 이후 |
|------|------|------|
| Vertex 경로 | `langchain_google_vertexai.ChatVertexAI` | `langchain_google_genai.ChatGoogleGenerativeAI(vertexai=True, ...)` |
| 인증 | SA JSON / ADC | **동일** |
| AI Studio 경로 | `ChatGoogleGenerativeAI(google_api_key=...)` | 동일 |
| REST 엔드포인트 | Vertex AI Platform | Vertex AI Platform (패밀리 동일, 클라이언트 라이브러리만 변경) |

**과금**: Vertex+SA → GCP 프로젝트. `GEMINI_API_KEY`만 쓰는 경로 → AI Studio (별도).

---

## 4. 설정 (`app/core/config.py`)

| 변수 | 기본값 | 비고 |
|------|--------|------|
| `CODE_CORRECTNESS_MAX_POINTS` | **100.0** | 이전 30 |
| `CODE_PERFORMANCE_MAX_POINTS` | **100.0** | 신규 |
| `JUDGE0_MAX_BATCH_SIZE` | **20** | 신규 |
| `EVAL_SUBMISSION_TIMEOUT_SEC` | **600.0** | 제출 평가 E2E (AI Worker 내부) |

---

## 5. 제출 평가 E2E 타임아웃 (AI Worker)

| 항목 | 내용 |
|------|------|
| 적용 범위 | `POST /submit` → 백그라운드 `submit_code` → `graph.ainvoke` (N4~N9) |
| 미포함 | BE Outbox 대기, HTTP 즉시 응답, 채팅 120초 |
| 초과 시 | `ai-evaluation-timeout[{node}]`, Redis `failed`, DB `FAILED`, Spring `FAILED` 콜백 |
| 노드 추적 | `eval_timeout_tracking` + `graph.py` 래퍼, N4 `eval_turn_subgraph:turn_{N}` |

REST API 스키마: **변경 없음** (비동기 `processing` 유지).

---

## 6. 하위 호환

- Spring/프론트 REST API: **변경 없음**
- 제출 플로우 graph 노드명: **변경 없음**
- DB `scores` 컬럼: `correctness_score` 스케일 0~100으로 저장값 증가 (의미는 동일 비율)
