# prompt_evaluations 저장 위치

## 📋 개요

`prompt_evaluations` 테이블에 평가 결과를 저장하는 위치와 시점을 정리합니다.

---

## 💾 저장 위치

### 1. 턴별 평가 (TURN_EVAL) 저장

**저장 함수**: `EvaluationStorageService.save_turn_evaluation()`

**저장 위치**: `app/application/services/evaluation_storage_service.py`

**호출 위치:**

#### 1.1. 4번 노드: Eval Turn Guard (제출 시)

**파일**: `app/domain/langgraph/nodes/eval_turn_guard.py`

**함수**: `_evaluate_turn_sync()` (263번 줄)

**저장 시점**: 제출 시 각 턴 평가 완료 후

**코드:**
```python
# PostgreSQL에 평가 결과 저장
async with get_db_context() as db:
    storage_service = EvaluationStorageService(db)
    
    await storage_service.save_turn_evaluation(
        session_id=postgres_session_id,
        turn=turn,
        turn_log=turn_log_for_storage
    )
    await db.commit()
```

**저장 데이터:**
- `evaluation_type`: `TURN_EVAL`
- `turn`: 턴 번호 (NOT NULL)
- `details`: JSONB (score, analysis, rubrics, intent 등)

---

#### 1.2. 백그라운드 평가 (현재 미사용)

**파일**: `app/application/services/eval_service.py`

**함수**: `_run_eval_turn_background()` (696번 줄)

**저장 시점**: 일반 채팅 시 백그라운드 평가 완료 후

**상태**: 현재 미사용 (일반 채팅에서는 평가를 하지 않음)

---

### 2. 전체 플로우 평가 (HOLISTIC_FLOW) 저장

**저장 함수**: `EvaluationStorageService.save_holistic_flow_evaluation()`

**저장 위치**: `app/application/services/evaluation_storage_service.py`

**호출 위치:**

#### 2.1. 6a번 노드: Holistic Flow Evaluation

**파일**: `app/domain/langgraph/nodes/holistic_evaluator/flow.py`

**함수**: `_eval_holistic_flow_impl()` (약 283번 줄)

**저장 시점**: 전체 플로우 평가 완료 후

**코드:**
```python
# PostgreSQL에 평가 결과 저장
async with get_db_context() as db:
    storage_service = EvaluationStorageService(db)
    
    await storage_service.save_holistic_flow_evaluation(
        session_id=postgres_session_id,
        holistic_flow_score=holistic_flow_score,
        holistic_flow_analysis=holistic_flow_analysis,
        details=details
    )
    await db.commit()
```

**저장 데이터:**
- `evaluation_type`: `HOLISTIC_FLOW`
- `turn`: `NULL` (전체 평가)
- `details`: JSONB (score, analysis, strategy_coherence 등)

---

## 📊 저장 흐름

### 제출 시 평가 저장 흐름

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
[EvaluationStorageService.save_turn_evaluation() 호출]
    ↓
[PostgreSQL prompt_evaluations 저장 (TURN_EVAL)]
    ↓
[6a번 노드: Holistic Flow Evaluation]
    ↓
[전체 플로우 평가]
    ↓
[EvaluationStorageService.save_holistic_flow_evaluation() 호출]
    ↓
[PostgreSQL prompt_evaluations 저장 (HOLISTIC_FLOW)]
```

---

## 🔍 저장 함수 상세

### `save_turn_evaluation()`

**위치**: `app/application/services/evaluation_storage_service.py` (38번 줄)

**시그니처:**
```python
async def save_turn_evaluation(
    self,
    session_id: int,
    turn: int,
    turn_log: Dict[str, Any]
) -> Optional[PromptEvaluation]
```

**기능:**
1. `turn_log`에서 평가 정보 추출
2. `details` JSONB 구성 (score, analysis, rubrics 등)
3. 기존 평가 결과 확인 (UNIQUE 제약 조건)
4. 기존 평가가 있으면 업데이트, 없으면 생성
5. DB에 저장 및 커밋

**저장 형식:**
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

---

### `save_holistic_flow_evaluation()`

**위치**: `app/application/services/evaluation_storage_service.py` (125번 줄)

**시그니처:**
```python
async def save_holistic_flow_evaluation(
    self,
    session_id: int,
    holistic_flow_score: float,
    holistic_flow_analysis: str,
    details: Optional[Dict[str, Any]] = None
) -> Optional[PromptEvaluation]
```

**기능:**
1. `details` JSONB 구성 (score, analysis, strategy_coherence 등)
2. 기존 평가 결과 확인 (UNIQUE 제약 조건)
3. 기존 평가가 있으면 업데이트, 없으면 생성
4. DB에 저장 및 커밋

**저장 형식:**
```python
PromptEvaluation(
    session_id=session_id,
    turn=None,  # 전체 평가이므로 NULL
    evaluation_type=EvaluationTypeEnum.HOLISTIC_FLOW,
    details={
        "score": float,
        "analysis": str,
        "strategy_coherence": float,
        ...
    }
)
```

---

## ⚠️ 중요 사항

### 1. UNIQUE 제약 조건

**턴 평가 (TURN_EVAL):**
- `(session_id, turn, evaluation_type)` UNIQUE
- 같은 턴에 대해 여러 번 저장하면 업데이트됨

**전체 평가 (HOLISTIC_FLOW):**
- `(session_id, evaluation_type)` UNIQUE (turn이 NULL이므로)
- 같은 세션에 대해 여러 번 저장하면 업데이트됨

### 2. 세션 ID 변환

**Redis session_id**: `"session_123"` (문자열)
**PostgreSQL session_id**: `123` (정수)

저장 전에 변환 필요:
```python
postgres_session_id = int(session_id.replace("session_", "")) if session_id.startswith("session_") else None
```

### 3. 저장 실패 처리

- PostgreSQL 저장 실패 시 경고 로그만 출력
- Redis 저장은 이미 완료되었으므로 메인 플로우는 계속 진행
- 에러가 발생해도 평가 프로세스는 중단되지 않음

---

## 📝 요약

| 평가 타입 | 저장 함수 | 호출 위치 | 저장 시점 |
|----------|----------|----------|----------|
| **TURN_EVAL** | `save_turn_evaluation()` | `eval_turn_guard.py` | 제출 시 각 턴 평가 완료 후 |
| **HOLISTIC_FLOW** | `save_holistic_flow_evaluation()` | `holistic_evaluator/flow.py` | 전체 플로우 평가 완료 후 |

**저장 서비스**: `app/application/services/evaluation_storage_service.py`

