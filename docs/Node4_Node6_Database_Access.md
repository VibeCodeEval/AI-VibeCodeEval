# 4번 및 6번 노드의 Redis/PostgreSQL 접근 위치

## 📋 개요

4번 노드(Turn Evaluator)와 6번 노드(Holistic Evaluator)에서 Redis와 PostgreSQL에 접근하는 위치를 정리합니다.

---

## 🔴 4번 노드 (Turn Evaluator)

### Redis 접근

**직접 접근 없음** ❌

- `app/domain/langgraph/nodes/turn_evaluator/` 디렉토리 내에서는 Redis에 직접 접근하지 않음
- `aggregate_turn_log()` 함수는 turn_log를 생성만 하고 저장하지 않음

**실제 Redis 저장 위치**:

#### 1. `eval_turn_guard.py` (제출 시 동기 평가)

**위치**: `app/domain/langgraph/nodes/eval_turn_guard.py`

**Redis 조회** (164줄):
```python
# Redis에서 최신 turn_logs 조회 (평가 결과 반영)
updated_turn_logs = await redis_client.get_all_turn_logs(session_id)
```

**Redis 저장** (294줄):
```python
# Redis에 상세 turn_log 저장
await redis_client.save_turn_log(session_id, turn, detailed_turn_log)
```

**용도**:
- 제출 시 모든 턴을 동기적으로 평가
- 평가 완료 후 turn_log를 Redis에 저장
- 저장된 turn_logs를 조회하여 turn_scores 생성

---

#### 2. `eval_service.py` (백그라운드 평가)

**위치**: `app/application/services/eval_service.py`

**Redis 조회** (122줄):
```python
# 기존 상태 로드 또는 초기 상태 생성
existing_state = await self.state_repo.get_state(session_id)
```

**Redis 저장** (166줄, 676줄):
```python
# 상태 저장
await self.state_repo.save_state(session_id, result)

# Redis에 상세 turn_log 저장 (백그라운드 평가 시)
await self.redis.save_turn_log(session_id, current_turn, detailed_turn_log)
```

**용도**:
- 일반 채팅 시 백그라운드에서 비동기 평가 수행
- 평가 결과를 Redis에 저장하여 실시간 점수 업데이트

---

### PostgreSQL 접근

**직접 접근 없음** ❌

- `app/domain/langgraph/nodes/turn_evaluator/` 디렉토리 내에서는 PostgreSQL에 직접 접근하지 않음

**실제 PostgreSQL 저장 위치**:

#### 1. `eval_turn_guard.py` (제출 시 동기 평가)

**위치**: `app/domain/langgraph/nodes/eval_turn_guard.py`

**접근 코드** (296-335줄):
```python
# PostgreSQL에 평가 결과 저장
try:
    from app.infrastructure.persistence.session import get_db_context
    from app.application.services.evaluation_storage_service import EvaluationStorageService
    
    # session_id를 PostgreSQL id로 변환 (Redis session_id: "session_123" -> PostgreSQL id: 123)
    postgres_session_id = int(session_id.replace("session_", "")) if session_id.startswith("session_") else None
    
    if postgres_session_id:
        async with get_db_context() as db:
            storage_service = EvaluationStorageService(db)
            
            # turn_log를 aggregate_turn_log 형식으로 변환
            turn_log_for_storage = {
                "prompt_evaluation_details": detailed_turn_log.get("prompt_evaluation_details", {}),
                "comprehensive_reasoning": detailed_turn_log.get("llm_answer_reasoning", ""),
                "intent_types": [intent_type],
                "evaluations": {},
                "detailed_feedback": [],
                "turn_score": turn_score,
                "is_guardrail_failed": False,
                "guardrail_message": None,
            }
            
            await storage_service.save_turn_evaluation(
                session_id=postgres_session_id,
                turn=turn,
                turn_log=turn_log_for_storage
            )
            await db.commit()
            logger.info(
                f"[Eval Turn Sync] PostgreSQL 턴 평가 저장 완료 - "
                f"session_id: {postgres_session_id}, turn: {turn}"
            )
except Exception as pg_error:
    # PostgreSQL 저장 실패해도 Redis는 저장되었으므로 경고만
    logger.warning(
        f"[Eval Turn Sync] PostgreSQL 턴 평가 저장 실패 (Redis는 저장됨) - "
        f"session_id: {session_id}, turn: {turn}, error: {str(pg_error)}"
    )
```

**용도**:
- 제출 시 모든 턴 평가 결과를 PostgreSQL에 저장
- `prompt_evaluations` 테이블에 `evaluation_type='TURN_EVAL'`로 저장

**에러 처리**:
- PostgreSQL 저장 실패 시에도 Redis는 저장되었으므로 경고만 로깅
- 메인 플로우는 계속 진행

---

#### 2. `eval_service.py` (백그라운드 평가)

**위치**: `app/application/services/eval_service.py`

**접근 코드** (678-717줄):
```python
# PostgreSQL에 평가 결과 저장 (백그라운드)
try:
    from app.infrastructure.persistence.session import get_db_context
    from app.application.services.evaluation_storage_service import EvaluationStorageService
    
    # session_id를 PostgreSQL id로 변환 (Redis session_id: "session_123" -> PostgreSQL id: 123)
    postgres_session_id = int(session_id.replace("session_", "")) if session_id.startswith("session_") else None
    
    if postgres_session_id:
        async with get_db_context() as db:
            storage_service = EvaluationStorageService(db)
            
            # turn_log를 aggregate_turn_log 형식으로 변환
            turn_log_for_storage = {
                "prompt_evaluation_details": detailed_turn_log.get("prompt_evaluation_details", {}),
                "comprehensive_reasoning": detailed_turn_log.get("llm_answer_reasoning", ""),
                "intent_types": [intent_type],
                "evaluations": detailed_turn_log.get("prompt_evaluation_details", {}).get("detailed_evaluations", {}),
                "detailed_feedback": detailed_turn_log.get("prompt_evaluation_details", {}).get("detailed_feedback", []),
                "turn_score": turn_score,
                "is_guardrail_failed": main_state.get("is_guardrail_failed", False),
                "guardrail_message": main_state.get("guardrail_message"),
            }
            
            await storage_service.save_turn_evaluation(
                session_id=postgres_session_id,
                turn=current_turn,
                turn_log=turn_log_for_storage
            )
            await db.commit()
            logger.info(
                f"[EvalService] PostgreSQL 턴 평가 저장 완료 - "
                f"session_id: {postgres_session_id}, turn: {current_turn}"
            )
except Exception as pg_error:
    # PostgreSQL 저장 실패해도 Redis는 저장되었으므로 경고만
    logger.warning(
        f"[EvalService] PostgreSQL 턴 평가 저장 실패 (Redis는 저장됨) - "
        f"session_id: {session_id}, turn: {current_turn}, error: {str(pg_error)}"
    )
```

**용도**:
- 일반 채팅 시 백그라운드에서 비동기 평가 수행 후 PostgreSQL에 저장
- `_run_eval_turn_background()` 함수 내부에서 호출

**에러 처리**:
- PostgreSQL 저장 실패 시에도 Redis는 저장되었으므로 경고만 로깅
- 백그라운드 작업이므로 메인 플로우에 영향 없음

---

## 🟢 6번 노드 (Holistic Evaluator)

### Redis 접근

**위치**: `app/domain/langgraph/nodes/holistic_evaluator/flow.py`

**접근 코드** (122-124줄):
```python
# Redis에서 모든 turn_logs 조회
from app.infrastructure.cache.redis_client import redis_client
all_turn_logs = await redis_client.get_all_turn_logs(session_id)
```

**용도**:
- 모든 턴의 평가 결과(turn_logs)를 Redis에서 조회
- Holistic Flow 평가를 위한 입력 데이터 수집

**사용 위치**:
- `_eval_holistic_flow_impl()` 함수 내부
- 130-139줄: 조회한 turn_logs를 구조화된 로그로 변환

---

### PostgreSQL 접근

**위치**: `app/domain/langgraph/nodes/holistic_evaluator/flow.py`

**접근 코드** (288-313줄):
```python
# PostgreSQL에 평가 결과 저장
try:
    from app.infrastructure.persistence.session import get_db_context
    from app.application.services.evaluation_storage_service import EvaluationStorageService
    
    # session_id를 PostgreSQL id로 변환 (Redis session_id: "session_123" -> PostgreSQL id: 123)
    postgres_session_id = int(session_id.replace("session_", "")) if session_id.startswith("session_") else None
    
    if postgres_session_id and score is not None:
        async with get_db_context() as db:
            storage_service = EvaluationStorageService(db)
            
            # 상세 정보 구성
            details = {
                "strategy_coherence": result.get("strategy_coherence"),
                "problem_solving_approach": result.get("problem_solving_approach"),
                "iteration_quality": result.get("iteration_quality"),
                "structured_logs": structured_logs,  # 턴별 로그 정보
            }
            
            await storage_service.save_holistic_flow_evaluation(
                session_id=postgres_session_id,
                holistic_flow_score=score,
                holistic_flow_analysis=analysis or "",
                details=details
            )
            await db.commit()
```

**용도**:
- Holistic Flow 평가 결과를 PostgreSQL에 저장
- `prompt_evaluations` 테이블에 `evaluation_type='HOLISTIC_FLOW'`로 저장

**에러 처리** (318-323줄):
```python
except Exception as pg_error:
    # PostgreSQL 저장 실패해도 Redis는 저장되었으므로 경고만
    logger.warning(
        f"[6a. Eval Holistic Flow] PostgreSQL 저장 실패 (Redis는 저장됨) - "
        f"session_id: {session_id}, error: {str(pg_error)}"
    )
```

---

## 📊 요약

### 4번 노드 (Turn Evaluator)

| 접근 타입 | 직접 접근 | 실제 저장 위치 |
|---------|---------|--------------|
| **Redis** | ❌ 없음 | `eval_turn_guard.py` (제출 시) 또는 `eval_service.py` (백그라운드) |
| **PostgreSQL** | ❌ 없음 | `eval_turn_guard.py` (제출 시) 또는 `eval_service.py` (백그라운드) |

**특징**:
- 4번 노드는 평가 로직만 수행하고, 저장은 다른 노드/서비스에서 처리
- `aggregate_turn_log()`는 turn_log 생성만 담당

**저장 시나리오**:
1. **제출 시 (`eval_turn_guard.py`)**: 
   - 모든 턴을 동기적으로 평가
   - 평가 완료 후 즉시 Redis + PostgreSQL 저장
   
2. **일반 채팅 시 (`eval_service.py`)**: 
   - 백그라운드에서 비동기 평가 수행
   - 평가 완료 후 Redis + PostgreSQL 저장
   - 사용자 응답 지연 없음

---

### 6번 노드 (Holistic Evaluator)

| 접근 타입 | 직접 접근 | 위치 |
|---------|---------|------|
| **Redis** | ✅ 있음 | `flow.py` 122-124줄 |
| **PostgreSQL** | ✅ 있음 | `flow.py` 288-313줄 |

**특징**:
- 6번 노드는 평가와 저장을 모두 직접 처리
- Redis에서 turn_logs 조회 → LLM 평가 → PostgreSQL 저장

---

## 🔍 추가 정보

### 6번 노드의 다른 파일들

**`scores.py`**:
- PostgreSQL 접근 있음 (174-185줄)
- 세션 종료 처리 및 제출 관련 저장

**`execution.py`**:
- Judge0 연동 (코드 실행 평가)
- DB 접근 없음

**`performance.py`**:
- 성능 평가 로직
- DB 접근 없음

---

## 📝 참고

- 4번 노드의 저장은 **비동기 백그라운드**로 처리될 수 있음 (`eval_service.py`)
- 6번 노드는 평가 완료 후 **즉시 저장**
- 모든 저장은 `EvaluationStorageService`를 통해 처리
- Redis session_id 형식: `"session_123"` → PostgreSQL id: `123`

