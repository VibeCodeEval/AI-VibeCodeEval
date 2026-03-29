# 노드별 DB 접근 가이드

> **최종 통합일**: 2026-03-27 | **원본**: Prompt_Evaluation_Storage_Location.md, Node4_Node6_Database_Access.md

---

## 1. 저장 시점·위치 (`prompt_evaluations`)

### 1.1 개요

`prompt_evaluations` 테이블에 평가 결과를 넣는 **시점**과 **코드 위치**를 정리한다. 실제 Redis·PostgreSQL **접근 코드**는 [2절](#2-노드별-redispostgresql-접근)을 본다.

### 1.2 턴별 평가 (TURN_EVAL)

| 항목 | 내용 |
|------|------|
| **저장 함수** | `EvaluationStorageService.save_turn_evaluation()` |
| **구현 파일** | `app/application/services/evaluation_storage_service.py` |
| **주요 호출** | `app/domain/langgraph/nodes/eval_turn_guard.py` — `_evaluate_turn_sync()` (제출 시, 각 턴 평가 완료 후) |
| **보조 경로** | `app/application/services/eval_service.py` — `_run_eval_turn_background()` (백그라운드; 일반 채팅 경로에서는 현재 평가 미사용과 동일하게 취급 가능) |

**저장 데이터 요약**

- `evaluation_type`: `TURN_EVAL`
- `turn`: 턴 번호 (NOT NULL)
- `details`: JSONB (score, analysis, rubrics, intent 등)

### 1.3 전체 플로우 평가 (HOLISTIC_FLOW)

| 항목 | 내용 |
|------|------|
| **저장 함수** | `EvaluationStorageService.save_holistic_flow_evaluation()` |
| **구현 파일** | `app/application/services/evaluation_storage_service.py` |
| **호출 위치** | `app/domain/langgraph/nodes/holistic_evaluator/flow.py` — `_eval_holistic_flow_impl()` (전체 플로우 평가 완료 후) |

**저장 데이터 요약**

- `evaluation_type`: `HOLISTIC_FLOW`
- `turn`: `NULL` (전체 평가)
- `details`: JSONB (score, analysis, strategy_coherence 등)

### 1.4 저장 함수 상세

#### `save_turn_evaluation()`

- **위치**: `evaluation_storage_service.py` (약 38번 줄)
- **시그니처**:

```python
async def save_turn_evaluation(
    self,
    session_id: int,
    turn: int,
    turn_log: Dict[str, Any]
) -> Optional[PromptEvaluation]
```

- **동작**: `turn_log`에서 평가 정보 추출 → `details` JSONB 구성 → UNIQUE 기준으로 기존 행 있으면 갱신, 없으면 생성 → 커밋.

```python
PromptEvaluation(
    session_id=session_id,
    turn=turn,
    evaluation_type=EvaluationTypeEnum.TURN_EVAL,
    details={
        "score": float,
        "analysis": str,
        "rubrics": list,
        "intent": str,
        ...
    }
)
```

#### `save_holistic_flow_evaluation()`

- **위치**: `evaluation_storage_service.py` (약 125번 줄)
- **시그니처**:

```python
async def save_holistic_flow_evaluation(
    self,
    session_id: int,
    holistic_flow_score: float,
    holistic_flow_analysis: str,
    details: Optional[Dict[str, Any]] = None
) -> Optional[PromptEvaluation]
```

- **동작**: `details` 구성 → UNIQUE 기준 upsert → 커밋.

```python
PromptEvaluation(
    session_id=session_id,
    turn=None,
    evaluation_type=EvaluationTypeEnum.HOLISTIC_FLOW,
    details={
        "score": float,
        "analysis": str,
        "strategy_coherence": float,
        ...
    }
)
```

### 1.5 제약·식별자·실패 처리

**UNIQUE**

- **TURN_EVAL**: `(session_id, turn, evaluation_type)` — 동일 턴 재저장 시 업데이트.
- **HOLISTIC_FLOW**: `(session_id, evaluation_type)` (`turn`이 NULL) — 동일 세션 재저장 시 업데이트.

**세션 ID 변환**

- Redis: `"session_123"` (문자열) → PostgreSQL `session_id`: `123` (정수).

```python
postgres_session_id = int(session_id.replace("session_", "")) if session_id.startswith("session_") else None
```

**저장 실패**

- PostgreSQL 실패 시 경고 로그만 남기고, Redis는 이미 반영된 경우가 많아 **메인 플로우는 계속** 진행한다.

### 1.6 한눈에 보기

| 평가 타입 | 저장 함수 | 호출 위치 | 저장 시점 |
|-----------|-----------|-----------|-----------|
| TURN_EVAL | `save_turn_evaluation()` | `eval_turn_guard.py` (주), `eval_service.py` (백그라운드) | 턴별 평가 완료 후 |
| HOLISTIC_FLOW | `save_holistic_flow_evaluation()` | `holistic_evaluator/flow.py` | 전체 플로우 평가 완료 후 |

**공통 저장 서비스**: `app/application/services/evaluation_storage_service.py`

---

## 2. 노드별 Redis·PostgreSQL 접근

### 2.1 4번 노드 (Turn Evaluator)

`app/domain/langgraph/nodes/turn_evaluator/` 안에서는 **Redis·PostgreSQL에 직접 접근하지 않는다**. `aggregate_turn_log()`는 turn_log **생성만** 하고 저장은 하지 않는다.

#### Redis

| 경로 | 파일 | 줄 참고 | 내용 |
|------|------|---------|------|
| 제출 시 동기 | `eval_turn_guard.py` | 조회 ~164, 저장 ~294 | `get_all_turn_logs` → 평가 후 `save_turn_log` |
| 백그라운드 | `eval_service.py` | `state_repo.get_state` ~122, `save_state` ~166, `save_turn_log` ~676 | 상태 로드·저장 및 턴 로그 저장 |

**제출 시 (`eval_turn_guard.py`) 예시**

```python
updated_turn_logs = await redis_client.get_all_turn_logs(session_id)
# ...
await redis_client.save_turn_log(session_id, turn, detailed_turn_log)
```

**백그라운드 (`eval_service.py`) 예시**

```python
existing_state = await self.state_repo.get_state(session_id)
await self.state_repo.save_state(session_id, result)
await self.redis.save_turn_log(session_id, current_turn, detailed_turn_log)
```

#### PostgreSQL

실제 `prompt_evaluations` 저장은 **`eval_turn_guard.py`**(제출) 또는 **`eval_service.py`**(백그라운드)에서 `get_db_context` + `EvaluationStorageService.save_turn_evaluation()`으로 수행한다 (대략 `eval_turn_guard` 296–335줄, `eval_service` 678–717줄).

- 제출 경로: `turn_log_for_storage`에 `prompt_evaluation_details`, `comprehensive_reasoning`, `intent_types`, `evaluations`/`detailed_feedback`(백그라운드 쪽은 `detailed_turn_log`에서 채움), `turn_score`, 가드레일 필드 등을 담는다.
- 실패 시: Redis는 이미 저장된 경우가 많아 **warning만** 기록하고 흐름은 유지.

**4번 요약**

| 접근 | turn_evaluator 직접 | 실제 위치 |
|------|---------------------|-----------|
| Redis | 없음 | `eval_turn_guard.py` / `eval_service.py` |
| PostgreSQL | 없음 | `eval_turn_guard.py` / `eval_service.py` |

**시나리오**

1. **제출**: 모든 턴 동기 평가 → Redis + PostgreSQL 즉시 반영.
2. **일반 채팅(백그라운드)**: 비동기 평가 → Redis + PostgreSQL; 응답 지연 최소화 (현재 일반 채팅에서 평가 비활성 등 정책은 [1.2절](#12-턴별-평가-turn_eval)과 운영 설정을 함께 본다).

---

### 2.2 6번 노드 (Holistic Evaluator)

`holistic_evaluator/flow.py`에서 **Redis 조회**와 **PostgreSQL 저장**을 직접 수행한다.

#### Redis (읽기)

- **위치**: `flow.py` 122–124줄 부근 — `redis_client.get_all_turn_logs(session_id)`.
- **용도**: Holistic Flow 평가 입력으로 전체 턴 로그 수집 (`_eval_holistic_flow_impl()` 내부, 이후 130–139줄 부근에서 구조화).

```python
from app.infrastructure.cache.redis_client import redis_client
all_turn_logs = await redis_client.get_all_turn_logs(session_id)
```

#### PostgreSQL (쓰기)

- **위치**: `flow.py` 288–313줄 부근 — `save_holistic_flow_evaluation()`; `score is not None` 등 조건과 함께 `details`에 `strategy_coherence`, `problem_solving_approach`, `iteration_quality`, `structured_logs` 등 포함.
- **실패**: 318–323줄 부근에서 예외 시 warning 로그 (Redis는 이미 앞 단계에서 사용됨).

**6번 요약**

| 접근 | 직접 | 위치 |
|------|------|------|
| Redis | 있음 (조회) | `flow.py` |
| PostgreSQL | 있음 (저장) | `flow.py` |

**흐름**: Redis에서 turn_logs 조회 → LLM 평가 → PostgreSQL 저장.

#### 같은 패키지 내 기타 파일

| 파일 | DB |
|------|-----|
| `scores.py` | PostgreSQL 있음 (약 174–185줄; 세션 종료·제출 관련 저장) |
| `execution.py` | Judge0 연동, DB 없음 |
| `performance.py` | 성능 평가만, DB 없음 |

---

## 3. 호출 스택·저장 흐름

### 3.1 제출 시 평가 저장 흐름 (다이어그램)

```
[Submit API 호출]
    ↓
[4번 노드: Eval Turn Guard]
    ↓
[각 턴 평가]
    ↓
[_evaluate_turn_sync() 호출]
    ↓
[Eval Turn SubGraph 실행]
    ↓
[평가 결과 생성]
    ↓
[Redis turn_logs 저장]
    ↓
[EvaluationStorageService.save_turn_evaluation()]
    ↓
[PostgreSQL prompt_evaluations (TURN_EVAL)]
    ↓
[6a: Holistic Flow Evaluation]
    ↓
[전체 플로우 평가]
    ↓
[EvaluationStorageService.save_holistic_flow_evaluation()]
    ↓
[PostgreSQL prompt_evaluations (HOLISTIC_FLOW)]
```

### 3.2 스택 관점 정리

- **Submit → Eval Turn Guard**: 턴별 동기 평가; 평가 완료 직후 Redis `save_turn_log`, 이어서 동일 맥락에서 PG `save_turn_evaluation` (실패해도 가드 로그 후 계속).
- **Holistic (`flow.py`)**: `get_all_turn_logs`로 Redis 읽기 → holistic 점수·분석 산출 → `save_holistic_flow_evaluation`으로 PG 기록.
- **백그라운드 (`eval_service`)**: `_run_eval_turn_background` 체인에서 state_repo·redis·PG 순으로 턴 평가를 반영할 수 있으나, 운영상 일반 채팅 평가 비활성과 맞물려 [1.2절](#12-턴별-평가-turn_eval)을 참고한다.

### 3.3 참고 메모

- 4번 **노드 디렉터리**는 평가만 담당하고, **저장은 guard·서비스**가 담당한다.
- 6번은 **조회(redis) + 저장(pg)** 를 `flow.py`에서 한 번에 처리한다.
- 모든 PostgreSQL 평가 행은 가능한 한 **`EvaluationStorageService`** 경로로 일원화한다.
