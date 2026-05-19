# 제출 평가 E2E 타임아웃 (10분)

> **작성일**: 2026-05-17  
> **목적**: AI Worker 내부에서 제출 1건당 LangGraph 평가 상한, 타임아웃 시 노드 로그

---

## 1. 배경

- 제출 API는 **즉시 `processing` 반환** 후 백그라운드에서 `graph.ainvoke` 실행
- 평균 채점 5~6분(대화 5~6턴) → **E2E 상한 10분** (config 조정 가능)
- **노드마다 개별 TIMEOUT 없음** — 제출 1건당 전역 상한 + 타임아웃 시점 **현재 노드** 로그

---

## 2. 시계 시작 시점 (QUEUE와 구분)

| 시점 | 포함 여부 |
|------|-----------|
| Spring Outbox / DB `QUEUED` | **아니오** (BE) |
| HTTP `POST /submit` 응답 | **아니오** |
| **`_run_submit_evaluation_background` 진입** | **예 (시작)** |
| `eval_service.submit_code` → `graph.ainvoke` | **예 (동일 구간)** |
| Judge0 Redis 큐 dequeue (N5) | 평가 **중간** (N4 이후) |

```text
begin_eval_tracking()
  → wait_for(submit_code → ainvoke, EVAL_SUBMISSION_TIMEOUT_SEC)
  → finally: end_eval_tracking()
```

---

## 3. 설정 (`app/core/config.py`)

```env
EVAL_SUBMISSION_TIMEOUT_SEC=600   # 기본 10분 (초)
```

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `EVAL_SUBMISSION_TIMEOUT_SEC` | `600.0` | 백그라운드 제출 평가 전체 상한 |

**별도 유지** (이번 E2E와 무관):

| 설정 | 값 | 범위 |
|------|-----|------|
| 채팅 `chat.py` | 120초 | `process_message` 전체 |
| `LLM_REQUEST_TIMEOUT` | 60초 | LLM HTTP 1회 |
| N5 Judge0 큐 폴링 | 30초 | Judge0 결과 대기 |
| `CallbackService` | 30초 | Spring 콜백 HTTP 1건 |

---

## 4. 노드 추적

### 4.1 모듈

`app/domain/langgraph/eval_timeout_tracking.py`

- `begin_eval_tracking(submission_id, session_id)` — 백그라운드 시작
- `set_eval_current_node(name)` / `get_eval_current_node()`
- `wrap_eval_node_tracking(node_name, impl)` — 그래프 노드 래퍼
- `log_evaluation_timeout()` → **`ai-evaluation-timeout[노드명]`**

### 4.2 메인 그래프 (`graph.py`)

래핑된 노드: `handle_request`, `intent_analyzer`, `writer`, `handle_failure`, `summarize_memory`, `eval_turn_guard`, `eval_code_execution`, `eval_static_analysis`, `eval_code_agent`, `holistic_debate`, `aggregate_final_scores`

### 4.3 N4 턴 서브그래프

`n4_eval_turn_guard.py`에서 턴마다:

```text
eval_turn_subgraph:turn_{N}
```

---

## 5. 타임아웃 시 동작

1. `asyncio.TimeoutError` ( `wait_for` 초과 )
2. 로그: `ai-evaluation-timeout[{현재노드}] submission_id=... timeout_sec=...`
3. Redis `submission_status:{id}` → `failed`
4. DB `submissions` → `FAILED`
5. Spring 콜백 `send_submission_status(FAILED)`

공통 처리: `session.py` → `_fail_submission_evaluation_background`

---

## 6. 로그 예시

```text
ERROR ... ai-evaluation-timeout[eval_turn_guard] submission_id=123 timeout_sec=600.0
ERROR ... ai-evaluation-timeout[eval_turn_subgraph:turn_3] submission_id=123 timeout_sec=600.0
ERROR ... ai-evaluation-timeout[holistic_debate] submission_id=123 timeout_sec=600.0
```

---

## 7. 관련 파일

| 파일 | 역할 |
|------|------|
| `app/core/config.py` | `EVAL_SUBMISSION_TIMEOUT_SEC` |
| `app/presentation/api/routes/session.py` | `wait_for`, `begin/end_eval_tracking`, 실패 처리 |
| `app/domain/langgraph/eval_timeout_tracking.py` | contextvars·래퍼·로그 |
| `app/domain/langgraph/graph.py` | 노드 래핑 |
| `app/domain/langgraph/nodes/eval/n4_eval_turn_guard.py` | 턴 서브그래프 노드명 |
| `tests/test_eval_timeout_tracking.py` | 단위 테스트 |

---

## 8. N5 Performance (같은 작업 세션, 참고)

- **TC별**: `passed=true`일 때만 time·memory raw(0~100)
- **합산**: `(Σ raw / 전체 TC) × (CODE_PERFORMANCE_MAX_POINTS / 100)`
- `JudgeResult.test_case_results` — Worker → N5 per-TC 채점
- config: `CODE_PERFORMANCE_MAX_POINTS` (기본 100)

상세: `.maestro/reports/daily/2026-05-17/code_changes.md` §3·§6
