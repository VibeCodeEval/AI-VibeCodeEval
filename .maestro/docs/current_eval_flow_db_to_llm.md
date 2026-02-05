# 현재 기준: DB → 대화 조회 → LLM 평가 구조 정리

> 6-B 이어서 통합할 때 참고용. **지금 기준** 실제 데이터 소스와 평가 흐름.

---

## 1. 대화(메시지)가 어디서 오는가

### 1.1 제출 시 LLM 평가에 쓰는 대화 = **Redis (DB 아님)**

| 단계 | 데이터 소스 | 설명 |
|------|-------------|------|
| 1. 상태 로드 | **Redis** `graph_state:{session_id}` | `EvalService.process_message()` / `submit_code()` 에서 `state_repo.get_state(session_id)` 호출 |
| 2. State 내용 | `state["messages"]`, `state["current_turn"]` | Redis에 직렬화된 LangChain 메시지 배열. Writer 노드가 턴마다 human/ai 메시지 추가 |
| 3. 제출 시 턴 추출 | **State의 messages** | `eval_turn_guard.py`: `messages = state.get("messages", [])`, `turns_to_evaluate = range(1, current_turn)` |
| 4. 턴별 입력 | State에서 추출한 human_msg, ai_msg | 각 턴마다 `_evaluate_turn_sync(session_id, turn, human_message, ai_message, problem_context)` 로 전달 |

**정리**: 턴별 LLM 평가(8의도 Eval Turn SubGraph)의 입력은 **전부 Redis에 있는 graph state의 messages**에서 나옵니다. PostgreSQL의 `prompt_messages`는 이 경로에서 사용하지 않습니다.

---

## 2. PostgreSQL(DB) 역할

### 2.1 세션/메시지 저장

| 테이블/역할 | 사용처 | 비고 |
|-------------|--------|------|
| `prompt_sessions` | SessionRepository | 세션 생성/조회/종료 |
| `prompt_messages` | SessionRepository | 턴별 USER/ASSISTANT 메시지 영구 저장 |
| `prompt_messages.meta` (JSONB) | Phase 6B | **turn_analysis** 저장 (Spec Extractor 결과) |

- `get_session_messages(session_id)`: 턴 순서대로 메시지 목록 조회.
- `get_conversation_history(session_id)`: LangChain 형식으로 대화 반환 (역할: API/복구용).
- **평가 플로우**: 제출 시 Eval Turn Guard는 위 메서드를 쓰지 않고, Redis state만 사용.

### 2.2 TurnAnalysis 저장/조회 (6B)

| 시점 | 동작 | 파일 |
|------|------|------|
| 일반 채팅 턴 종료 후 | Writer/Spec Extractor에서 만든 `turn_analysis`를 **PostgreSQL**에 저장 | `eval_service.py` → `_save_turn_analysis_to_db()` → `SessionRepository.update_message_meta(..., meta_update={"turn_analysis": ...})` |
| 제출 시 | **Integrated Evaluator**만 DB 조회 | `integrated_evaluator.py` → `load_turn_analyses_from_db(session_id)` → `SessionRepository.get_all_turn_analyses(session_id)` |

- `get_all_turn_analyses(session_id)`: `prompt_messages`에서 role=USER인 행만, turn 오름차순으로 조회하고 각 행의 `meta['turn_analysis']`를 리스트로 반환.
- Integrated Evaluator는 이 리스트로 **규칙 기반** 점수만 계산 (LLM 호출 없음).

---

## 3. 제출 시 평가 흐름 (현재)

```
submit_code()
  → state_repo.get_state(session_id)     [Redis에서 state 로드]
  → graph.ainvoke(state)

  [그래프 내부]
  handle_request → intent_analyzer → eval_turn_guard (제출이므로 여기로 진입)
       │
       ▼
  eval_turn_guard:
    - state["messages"] (Redis에서 온 것) 에서 턴별 human/ai 추출
    - 턴 1..current_turn-1 에 대해 _evaluate_turn_sync() 반복
      → Eval Turn SubGraph (8의도 LLM 평가) 실행
      → 결과를 Redis turn_log + PostgreSQL (EvaluationStorageService) 에 저장
    - 반환: turn_scores
       │
       ▼
  main_router → "eval_holistic_flow" 쪽으로
       │
       ▼
  integrated_evaluator:
    - load_turn_analyses_from_db(session_id)  [PostgreSQL에서 turn_analysis만 조회]
    - 규칙 기반으로 first_prompt / follow_up / efficiency 점수 계산
    - state에 integrated_score, integrated_evaluation 반영
       │
       ▼
  eval_holistic_flow (LLM) → aggregate_turn_scores → eval_code_execution → aggregate_final_scores → END
```

---

## 4. 요약 표

| 목적 | 대화/데이터 소스 | 저장소 | 비고 |
|------|------------------|--------|------|
| 턴별 8의도 LLM 평가 입력 | state["messages"] (턴별 human/ai) | **Redis** (graph_state) | DB 메시지 테이블 미사용 |
| TurnAnalysis 저장 | 매 턴 Spec Extractor 결과 | **PostgreSQL** prompt_messages.meta | 6B |
| Integrated Evaluator 입력 | turn_analysis 배열 | **PostgreSQL** get_all_turn_analyses() | 규칙 기반만, LLM 없음 |
| Holistic Flow 등 | turn_logs, state | **Redis** + 그래프 state | 기존과 동일 |

---

## 5. 통합 시 참고 (6-B 이후)

- **“대화를 DB에서 가져와서 LLM 평가”로 통합**하려면:
  - 현재는 “DB에서 가져온 대화”로 LLM 평가를 하지 않음.  
    LLM 평가 입력은 **Redis state의 messages**.
  - 통합 옵션 예:
    1. **제출 시** Redis 대신 `SessionRepository.get_session_messages(session_id)` 로 대화를 가져와서, 그걸로 턴별 LLM 평가 + 통합 평가 한 번에 수행.
    2. 또는 Redis state를 계속 쓰되, “통합 평가 노드 하나”에서만 DB의 `get_all_turn_analyses` + (필요 시) `get_session_messages`를 섞어서 한 번의 LLM as Judge 호출로 8요소·Chaining 평가.
- PHASE6_PLAN.md 4.8절: “Node4 + Node6 통합해서 한번에” 는 아직 미구현.  
  현재는 Node4(Eval Turn Guard → 턴별 LLM) → Node6(Holistic Flow LLM) 순차 실행.

---

*작성: 2026-01-29, .maestro 폴더 및 app 코드 기준*
