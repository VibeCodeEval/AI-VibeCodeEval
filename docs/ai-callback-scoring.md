# AI 채점 콜백 연동 명세 (BE ↔ AI Worker)

> **상태:** BE **PR #67** 반영 (검증·runs replace·SSE `scoring_complete`) — **AI Worker 연동·사전 검증** (2026-05)  
> **관련 이슈:** AI-VibeCodeEval #37 (`runs[]` 빈 배열) · BE repo `docs/integration/ai-callback-scoring.md` (SoT)  
> **목적:** 채점 **데이터(TC + 점수)** 는 `POST /api/callbacks/ai/submissions/{submissionId}/result` 한 번으로 BE에 넘기고, `analysis`는 **진행/실패 알림만**. **`DONE`은 result URL에만** 보낸다.

---

## 1. 요약

| 구분 | 변경 전 | 변경 후 |
|------|---------|---------|
| 채점 완료 (TC + 점수 + `DONE`) | `POST /api/internal/submissions/{id}/result` (deprecated) | **`POST /api/callbacks/ai/submissions/{submissionId}/result`** |
| 진행/실패 알림 | `POST /api/callbacks/ai/analysis` (`DONE` 위주) | **유지** — `RUNNING` / `FAILED`만 ( **`DONE`은 `result`만** ) |
| BE 저장 로직 | `ReceiveScoringResultUseCase` | **동일 UseCase 재사용** |
| `internal/.../result` | 존재 | **deprecated → 제거 예정** |

**호출 순서 (권장):**

```
(선택) POST /api/callbacks/ai/analysis   { status: "RUNNING" }
         … LangGraph N4 → N5 → … → N9 …
(필수) POST /api/callbacks/ai/submissions/{submissionId}/result
         Body: { status: "DONE", testCases[], score }
```

---

## 2. BE 변경 사항

### 2.1 채점 결과 API (PR #67 기준)

**`POST /api/callbacks/ai/submissions/{submissionId}/result`**

| 항목 | 내용 |
|------|------|
| Controller | `AICallbackController` |
| UseCase | `ReceiveScoringResultUseCase` |
| Body | `ScoringResultRequest` — `status`, `testCases`, `score` (`submissionId`는 **path**) |
| Validation | `@Valid` — `DONE` + `testCases` **비어 있음** → **400** |
| 인증 | `POST /api/callbacks/ai/**` permitAll |
| Response | `BaseResponse<Void>` (200) |

**처리 순서 (트랜잭션 1회, PR #67):**

1. `submissions.status` ← `request.status()`
2. 기존 `submission_runs` **DELETE** 후 `testCases[]` **INSERT** (재콜백 replace)
3. `score` 있으면 → `scores` **upsert** + `calculateTotalScore()`
4. 커밋 후 SSE: `case_result`(×N, **`group` 포함**) → **`scoring_complete`** → `final_score`(optional) → `complete`

### 2.2 유지 API

**`POST /api/callbacks/ai/analysis`**

| 항목 | 내용 |
|------|------|
| UseCase | `UpdateSubmissionStatusUseCase` |
| Body | `{ submissionId, status }` |
| DB 변경 | `submissions.status` **만** |
| 미처리 | `submission_runs`, `scores`, SSE |

**AI 호출 규칙 (계약):**

| `status` | `analysis` | `result` |
|----------|:------------:|:--------:|
| `RUNNING` | ✅ | — |
| `FAILED` | ✅ | ✅ (`testCases: []`, `score: null` 가능) |
| `DONE` | ❌ | ✅ (`testCases` + `score` 필수) |
| `QUEUED` | 가능 | — |

> BE 코드는 `analysis`에서 `DONE`도 **기술적으로** 받을 수 있으나, AI는 **`DONE`을 `result`에만** 보낸다.

> BE는 `analysis`로 `DONE`을 받아도 **status만 `DONE`으로 갱신**하며 `submission_runs` / `scores` / SSE는 채우지 않는다. **무시 API가 아니라** 계약상 AI가 `DONE`을 `analysis`에 보내지 않는 것(Issue #37 “완료인데 `runs[]` 빈 상태”와 동일).

### 2.3 폐기 API

**`POST /api/internal/submissions/{id}/result`**

- 동작은 신규 `result`와 동일했으나 JWT 필요, AI 미사용
- deprecated 후 제거

### 2.4 BE 작업 체크리스트 (PR #67)

- [x] `POST /api/callbacks/ai/submissions/{submissionId}/result`
- [x] `ScoringResultRequest` + validation (`DONE` 시 TC ≥ 1)
- [x] `ReceiveScoringResultUseCase` — runs delete+replace, scores upsert
- [x] SSE `scoring_complete`, `case_result.group`
- [x] `InternalSubmissionController` deprecated
- [ ] BE PR #67 **배포 후** AI↔BE E2E (`runs[]` non-empty)

### 2.5 BE 검증 규칙 (AI가 맞출 payload)

| 규칙 | BE 응답 | AI 대응 |
|------|---------|---------|
| `status=DONE` + `testCases` 빈 배열 | **400** | `validate_be_scoring_body` — 전송 전 차단 |
| `group` 오타 (`sample` 등) | **400** | 기본 `SAMPLE`; checker에 group 넣을 때만 주의 |
| `verdict` enum 외 | **400** | `judge_status_to_verdict` + 사전 검증 |
| 재콜백 (동일 submission result 2회) | **200** (덮어쓰기) | 권장: 제출당 **result 1회**만 |

---

## 3. AI Worker 연동

### 3.1 엔드포인트

| 환경 변수 예 | 값 |
|--------------|-----|
| `BE_BASE_URL` | `http://localhost:8080` |
| 채점 완료 | `{BE_BASE_URL}/api/callbacks/ai/submissions/{submissionId}/result` |
| 진행 알림 | `{BE_BASE_URL}/api/callbacks/ai/analysis` |

**Content-Type:** `application/json`

### 3.2 `POST /api/callbacks/ai/submissions/{submissionId}/result` — Request 예시

**URL:** `POST {BE_BASE}/api/callbacks/ai/submissions/88001/result`

**성공 (N9 직후 1회) — body (`ScoringResultRequest`만, submissionId는 path):**

```json
{
  "status": "DONE",
  "testCases": [
    {
      "caseIndex": 0,
      "group": "SAMPLE",
      "verdict": "AC",
      "timeMs": 100,
      "memKb": 1024,
      "stdoutBytes": 128,
      "stderrBytes": 0
    },
    {
      "caseIndex": 1,
      "group": "SAMPLE",
      "verdict": "WA",
      "timeMs": 150,
      "memKb": 1100,
      "stdoutBytes": 64,
      "stderrBytes": 0
    }
  ],
  "score": {
    "promptScore": 30.0,
    "perfScore": 30.0,
    "correctnessScore": 40.0,
    "rubricJson": "{\"correctness_details\":{\"test_cases\":[]}}"
  }
}
```

**실패 (그래프 중단, TC 없음):**

```json
{
  "status": "FAILED",
  "testCases": [],
  "score": null
}
```

### 3.3 `POST /api/callbacks/ai/analysis` — Request 예시

```json
{
  "submissionId": 88001,
  "status": "RUNNING"
}
```

```json
{
  "submissionId": 88001,
  "status": "FAILED"
}
```

### 3.4 AI State → BE 필드 매핑

| BE 필드 | AI 소스 (N5 `test_case_results` 등) | 변환 |
|---------|-------------------------------------|------|
| `caseIndex` | `test_case_index` | 정수, 0부터 |
| `group` | (없음) | 정책값 예: `"SAMPLE"` (대문자) |
| `verdict` | `passed`, `status_id` (Judge0) | 아래 표 참고 |
| `timeMs` | `time` (초, 문자열/숫자) | × 1000, 정수 |
| `memKb` | `memory` | KB 정수 파싱 |
| `stdoutBytes` | `actual` | `len(utf-8 bytes)` 또는 `0` |
| `stderrBytes` | `stderr` | `len(utf-8 bytes)` 또는 `0` |
| `score.promptScore` | N9 `prompt_score` | number |
| `score.perfScore` | N9 `perf_score` | number |
| `score.correctnessScore` | N9 `correctness_score` | number |
| `score.rubricJson` | N9 rubric `dict` | **`json.dumps(...)` 문자열** |

**Judge0 `status_id` → `verdict` (권장):**

| 조건 | `verdict` |
|------|-----------|
| Accepted (예: 3) + 통과 | `AC` |
| Wrong answer (예: 4) 또는 출력 불일치 | `WA` |
| TLE (예: 5) | `TLE` |
| Compilation Error (**6**, Judge0) | **`RE`** |
| Runtime Error NS (**7**, Judge0) | `MLE` |
| 그 외 / 런타임 오류 | `RE` |
| `passed == false` & AC id | `WA` |

> Judge0 표: [`docs/Judge0_가이드.md`](Judge0_가이드.md). AI 매퍼: `scoring_callback_mapper.judge_status_to_verdict`.

### 3.5 AI Worker 작업 체크리스트

- [x] N9 직후 `result` 1회 호출 (`session.py` ← `be_scoring_callback`)
- [x] `scoring_callback_mapper.py` — verdict, group, bytes, `rubricJson` 문자열
- [x] `analysis`에서 `DONE` 제거 (`RUNNING`/`FAILED`만)
- [x] N9 DB 직접 `scores` / `submissions.status` write 중단 — BE SoT (`end_session`만 유지)
- [x] `BE_BASE_URL` + `CallbackService.send_scoring_result`
- [x] `validate_be_scoring_body` — `DONE`+빈 TC 전송 차단 (`session.py`)
- [x] BE 400 응답 body `error` 로그 (`callback_service.py`)

### 3.6 AI SoT 권장

| 데이터 | 권장 SoT |
|--------|----------|
| `submission_runs` | **BE** (`result` 콜백) |
| `scores` (행 + `total_score`) | **BE** (`result` 콜백) |
| `rubric_json` 상세 (TC 입출력 등) | payload `score.rubricJson`에 포함 |
| `submissions.status` 완료 | **`result`의 `status: DONE`** |

AI가 N9에서 DB에 직접 `scores`를 쓰고 BE도 `result`로 쓰면 **PK 충돌·덮어쓰기** 위험이 있다. 단계적으로 AI direct write 제거 권장.

---

## 4. DB 저장 상세 (AI 전송 시 준수 사항)

### 4.1 `submissions` (result / analysis 공통)

| 컬럼 | API 필드 | 타입 | Nullable | 비고 |
|------|----------|------|----------|------|
| `id` | `submissionId` | BIGINT | — | **존재하는 ID** 필수, 없으면 404 |
| `status` | `status` | ENUM string | NOT NULL | `SubmissionStatus` |

**`SubmissionStatus` 허용 값 (대소문자 무관, BE에서 upper case):**

```
QUEUED | RUNNING | DONE | FAILED
```

잘못된 문자열 → **400**

---

### 4.2 `submission_runs` (`result`의 `testCases[]`만)

| 컬럼 | API 필드 | 타입 | Nullable (JPA) | 비고 |
|------|----------|------|----------------|------|
| `id` | — | BIGINT | auto | BE 생성 |
| `submission_id` | `submissionId` | BIGINT | **NOT NULL** | path/body ID와 동일 |
| `case_index` | `caseIndex` | INT | **NOT NULL** | 0부터 |
| `grp` | `group` | ENUM string | **NOT NULL** | `RunGroup.valueOf(group)` |
| `verdict` | `verdict` | ENUM string | nullable* | JSON enum, 잘못된 값 → 400 |
| `time_ms` | `timeMs` | INT | nullable | SSE null 시 0 |
| `mem_kb` | `memKb` | INT | nullable | SSE null 시 0 |
| `stdout_bytes` | `stdoutBytes` | INT | nullable | |
| `stderr_bytes` | `stderrBytes` | INT | nullable | |

\* 엔티티상 `verdict` 컬럼은 nullable이나, AI는 **항상 채우는 것을 권장**.

**UNIQUE 제약:**

```
UNIQUE (submission_id, case_index)
```

| 주의 | 내용 |
|------|------|
| `group`은 unique에 **포함되지 않음** | 같은 `caseIndex`에 다른 `group` 불가 — caseIndex만 유일 |
| 재콜백 (PR #67) | 기존 runs **DELETE 후 INSERT**, score **upsert** → **200** |
| `DONE` + 빈 `testCases` | BE **400** (저장 안 함) — AI는 전송 전 검증으로 방지 |

**`RunGroup` (`group`) — 정확히 대문자:**

```
SAMPLE | PUBLIC | PRIVATE
```

오타 예: `sample`, `Sample` → `IllegalArgumentException` → **400**

**`Verdict` (`verdict`):**

```
AC | WA | TLE | MLE | RE
```

---

### 4.3 `scores` (`result`의 `score` 객체)

| 컬럼 | API 필드 | 타입 | Nullable | 비고 |
|------|----------|------|----------|------|
| `submission_id` | `submissionId` | BIGINT | **PK** | 1 submission : 1 score |
| `prompt_score` | `promptScore` | DECIMAL(5,2) | null → 0 | |
| `perf_score` | `perfScore` | DECIMAL(5,2) | null → 0 | |
| `correctness_score` | `correctnessScore` | DECIMAL(5,2) | null → 0 | |
| `total_score` | — | DECIMAL(5,2) | BE 계산 | `prompt + perf + correctness` |
| `rubric_json` | `rubricJson` | JSONB | nullable | **JSON 문자열** (객체 X) |

**PK 제약:**

```
PRIMARY KEY (submission_id)
```

| 주의 | 내용 |
|------|------|
| 재콜백 (PR #67) | `scores` **upsert** — 동일 submission 재전송 시 **200** |
| `score: null` | UseCase에서 score 저장·SSE `final_score` **스킵** |
| `rubricJson` | Python `dict`를 그대로 보내지 말 것 — **반드시 string** |

---

### 4.4 저장 흐름 다이어그램

```
POST .../submissions/{id}/result
        │
        ├─► submissions.status
        ├─► submission_runs  (DELETE 기존 → INSERT testCases[])
        ├─► scores           (upsert)
        └─► SSE: case_result* → scoring_complete → final_score? → complete
```

---

## 5. HTTP·검증 (AI 참고)

| HTTP | 원인 |
|------|------|
| 200 | 성공 (재콜백 replace 포함) |
| 400 | 잘못된 `status` / `group` / `verdict`; **`DONE` + `testCases: []`**; `@Valid` 실패 |
| 404 | `submissionId` 없음 |
| 500 | DB 기타 (드묾) |

**AI 클라이언트:** `status=DONE`이면 `testCases` **1건 이상** 필수. N5 TC 0건·Judge0 미실행 시 `be_body` 없거나 빈 TC → **result 미전송** + warning 로그.

### 5.1 SSE (BE 발행, AI 코드 변경 없음)

| 이벤트 | 비고 |
|--------|------|
| `case_result` | TC별; **`group`** 필드 추가 (PR #67) |
| `scoring_complete` | `score` 없어도 **항상** 발송 |
| `final_score` | `score` 객체 있을 때 (optional) |
| `complete` | 세션/제출 완료 알림 |

순서: `case_result` → `scoring_complete` → `final_score`(optional) → `complete`. FE는 BE PR #67 배포 후 구독 로직 확인.

---

## 6. 완료 검증

| 검증 | 방법 |
|------|------|
| `submission_runs` | `SELECT * FROM submission_runs WHERE submission_id = ?` |
| 관리자 API | `GET /api/admin/...` 상세의 `runs[]` non-empty |
| `scores` | `scores` 행 존재, `total_score` = 세 항목 합 |
| SSE | `case_result`, `scoring_complete`, `final_score`(optional), `complete` |
| Issue #37 | rubric에만 TC 있고 `runs[]` 빈 현상 해소 |

---

## 7. 관련 코드 (BE)

| 파일 | 역할 |
|------|------|
| `ReceiveScoringResultUseCase` | 저장 + SSE 이벤트 |
| `UpdateSubmissionStatusUseCase` | analysis 전용 |
| `ScoringResultRequest` | result body 스키마 |
| `AICallbackController` | analysis (기존) |
| `InternalSubmissionController` | internal (deprecated 예정) |
| `SubmissionRun` / `Score` / `Submission` | 엔티티·제약 |
| `application.yml` | `/api/callbacks/ai/**` permitAll |

---

## 8. AI repo diff 체크리스트

Issue #37 · `docs/ai-callback-scoring.md` 구현 시 AI-VibeCodeEval 저장소에서 손대는 파일·동작 기준.

### 8.1 `app/application/services/callback_service.py`

| 항목 | 현재 | 목표 |
|------|------|------|
| `send_submission_status` | `POST .../api/callbacks/ai/analysis`, `{ submissionId, status }` | 유지 — **`DONE` 호출 제거** |
| 신규 메서드 | 없음 | `send_scoring_result(...)` → `POST .../submissions/{id}/result` |
| URL 설정 | `SPRING_CALLBACK_URL` + path replace | `BE_BASE_URL` + path (§3.1) |
| payload | status만 | body: `status`, `testCases[]`, `score` (§3.2) |
| `rubricJson` | — | N9 dict → **`json.dumps(..., ensure_ascii=False)`** 문자열 |

### 8.2 `app/domain/langgraph/nodes/eval/n9_final_scores.py`

| 항목 | 현재 | 목표 |
|------|------|------|
| DB `submission_runs` | 미호출 | **(권장) 제거** — BE `result` SoT |
| DB `scores` / `submissions.status` | N9에서 직접 upsert + `DONE` | **(권장) 제거 또는 최소화** — BE `result` SoT (PK·`total_score` 충돌 방지) |
| 콜백 | 없음 (상위 `session.py`가 `analysis` `DONE`) | N9 직후 또는 submit 백그라운드에서 **`result` 1회** (`testCases` + `score`) |
| State 입력 | `test_case_results`, `final_scores` | 매핑 함수에 전달 (§3.4) |

### 8.3 `app/presentation/api/routes/session.py`

| 항목 | 현재 | 목표 |
|------|------|------|
| `_run_submit_evaluation_background` 성공 | Redis `completed` → DB `DONE` → **`analysis` `DONE`** | **`result` `DONE`** (+ 선택 `analysis` 없음) |
| `_fail_submission_evaluation_background` | DB `FAILED` → **`analysis` `FAILED`** | **`analysis` `FAILED`** + **`result` `FAILED`** (`testCases: []`, `score: null`) |
| 평가 시작 | `RUNNING` 없음 | (선택) **`analysis` `RUNNING`** |
| 순서 | — | `FAILED` 시 `analysis` / `result` 순서 자유(BE); 권장: 상태 알림 → `result` |

### 8.4 신규·이동 권장 모듈

| 파일 (예) | 역할 |
|-----------|------|
| `app/domain/langgraph/nodes/eval/scoring_callback_mapper.py` (또는 `app/application/services/scoring_callback_mapper.py`) | `test_case_results` → BE `testCases[]`; Judge0 `status_id` + `passed` → `verdict`; `group` 기본 `"SAMPLE"`; `time`/`memory` → `timeMs`/`memKb`; `stdoutBytes`/`stderrBytes` |

**Judge0 → `verdict` (§3.4):** 3+통과 → `AC`; 4/불일치 → `WA`; 5 → `TLE`; **6 → `RE`**; **7 → `MLE`**; 그 외 → `RE`.

### 8.5 설정·문서·검증

- [ ] `env.example` / `.env`: `BE_BASE_URL` 또는 `SPRING_CALLBACK_URL` 정리
- [ ] `docs/API_변경_이력.md` — `result` 콜백·`analysis` `DONE` 제거 기록
- [ ] `.maestro/docs/DB_Save_Path_Audit.md` — submission_runs SoT BE로 한 줄
- [x] E2E (로컬): `result DONE` 200, `testCases=N`
- [ ] E2E: **BE PR #67 배포 후** 관리자 `GET .../submissions/{id}` → `runs[]` non-empty
- [x] 재콜백: BE replace/upsert — AI는 제출당 result 1회 권장

### 8.6 완료 조건 (BE·AI 공통)

1. BE **PR #67** 배포 (`validation`, runs replace, `scoring_complete` SSE)  
2. [x] AI submit 백그라운드 직후 `result` 1회 + 사전 검증  
3. [x] AI N9 direct write(`scores`, `submission_runs`) 정리  

### 8.7 PR #38 Copilot 리뷰 대응 (Resolve용)

| 코멘트 | 대응 |
|--------|------|
| `status_id` 6/7 → `MLE` | 6 → `RE`, 7 → `MLE` (`scoring_callback_mapper.py`) |
| `BE_BASE_URL` | `env.example` + `CallbackService`; 레거시 URL은 레거시 메서드만 |
| grade D/F 상한 (`correctness < 100`) | 의도 변경 — `total_score` 구간만 (`n9_final_scores`, `State_노드별_흐름.md`) |
| 문서 URL `.../ai/result` | §2.1 `.../submissions/{id}/result`로 정정 |

**PR 본문 한 줄:** BE PR #67 배포 필요 — 본 커밋으로 AI 계약·검증 동기화.

---

## 9. 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-05-20 | 초안 — 콜백 통합 계획 문서화 |
| 2026-05-20 | §2.2 `analysis`+`DONE` BE 동작 명시; §8 AI repo diff 체크리스트 추가 |
| 2026-05-20 | AI Worker — `scoring_callback_mapper`, `CallbackService.send_scoring_result`, N9/session 연동 |
| 2026-05-20 | BE PR #67 — validation, replace, SSE; AI `validate_be_scoring_body`, verdict 6→RE |
