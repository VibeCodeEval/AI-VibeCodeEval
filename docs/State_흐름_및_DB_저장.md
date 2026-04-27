# State 흐름 및 DB 저장

> **최종 통합일**: 2026-03-27 | **최종 갱신**: 2026-04-05 (N5~N9 평가 파이프라인 재설계, N8 다중 에이전트 토론, V3.0 루브릭 반영)  
> **원본**: Current_Data_Flow.md, LangGraph_State_Flow.md, State_Flow_and_DB_Storage.md

---

## 목차

1. [데이터 흐름](#1-데이터-흐름)
2. [State 구조](#2-state-구조)
3. [Redis vs Memory (LangGraph)](#3-redis-vs-memory-langgraph)
4. [DB 저장 전략](#4-db-저장-전략)

---

## 1. 데이터 흐름

### 1.1 개요

API 요청부터 LangGraph 실행, Redis·PostgreSQL 반영까지의 흐름을 정리한다. 평가는 **제출(Submit)** 경로에서 수행된다.

**노드 순서·입출력 표·N8 서브그래프·N9 공식을 한 문서로 보려면** → [`평가_파이프라인_플로우.md`](./평가_파이프라인_플로우.md).

### 1.2 일반 채팅 (Chat)

#### API

```
POST /api/chat/messages
```

#### 처리 순서

1. **세션 확인**  
   PostgreSQL `prompt_sessions`에서 `exam_id`, `participant_id` 기준 진행 중 세션 조회.

2. **LangGraph 실행** (`eval_service.process_message()`)
   - Redis에서 State 로드: `state_repo.get_state(session_id)` → dict를 역직렬화해 LangChain `BaseMessage` 등으로 구성.
   - `self.graph.ainvoke(state, config)` 실행. **실행 중 State는 메모리**에 있으며, 노드의 `state.get("messages")`는 메모리의 LangGraph State에서 읽는다.
   - 노드: **1** Intent Analyzer → **3** Writer LLM.
   - 실행 종료 후 `state_repo.save_state()`로 Redis에 반영.

3. **메시지 (Writer)**  
   `messages`에 user/assistant 턴 단위 dict(또는 동등 구조) 추가 후 `StateRepository.save_state()`.
   - Redis 키: `graph_state:{session_id}`  
   - 값: JSON (`messages`, `current_turn`, `problem_context` 등)  
   - TTL: 기본 **3600초(1시간)** (설정에 따라 변경 가능).

4. **턴 매핑**  
   Writer에서 `turn_mapping:{session_id}` 저장.  
   예: `{"1": {"start_msg_idx": 0, "end_msg_idx": 1}, ...}`

5. **토큰**  
   `session_token:{session_id}` — 턴별 누적 및 전체 누적.

#### 채팅 시 저장 요약

| 데이터 | 저장 위치 | 비고 |
|--------|-----------|------|
| 대화 메시지 | Redis (`graph_state`) | PostgreSQL에는 저장하지 않음 |
| 턴 매핑 | Redis (`turn_mapping`) | |
| 토큰 | Redis (`session_token`) | |
| 평가 결과 | 없음 | 일반 채팅에서는 평가 없음 |

### 1.3 제출 (Submit)

#### API

```
POST /api/session/submit
```

#### 처리 순서

1. **세션 확인** — `prompt_sessions` 동일.

2. **LangGraph 진입** (`eval_service.submit_code()`)
   - Redis에서 State 로드 후 `is_submitted`, `code_content`, `lang` 등 설정.
   - `ainvoke` 후 `save_state`로 Redis 동기화 (실행 중은 메모리 State).

3. **노드 N4 — Eval Turn Guard (턴별 프롬프트 평가)**  
   - **데이터 소스**: 메모리 State의 `messages` (Redis `turn_mapping`은 사용하지 않음; 턴은 messages에서 추출).  
   - 턴 1 ~ `current_turn-1`에 대해 Eval Turn SubGraph 실행.  
     - `eval_intent_disambiguation` → 의도 분류 (CREATION / SETTING / REFINEMENT / DEBUGGING / EXPLORATION / FOLLOW_UP)  
     - `_evaluate_turn()` → **V3.0 Intent-Rubric Gate** 기반 채점  
       - R1 논리·효율(Logic & Efficiency) / R2 명확성·완전성(Clarity & Completeness) / R3 구조·예시(Structure & Examples) / R4 맥락 유지 로컬(Context Maintenance)  
       - 의도별로 적용 루브릭 결정 (FOLLOW_UP → R4만, EXPLORATION → R1+R2만 등)  
       - 출력: `turn_score` (1~5) + `rubric_breakdown` (dict) + `applied_rubrics` (list)  
   - **저장**: Redis `turn_logs:{session_id}:{turn}` — `prompt_evaluation_details.rubric_breakdown` 포함, PostgreSQL `prompt_evaluations` (`evaluation_type: 'TURN_EVAL'`).

4. **노드 N5 — Eval Code Execution (Judge0)**  
   - **데이터 소스**: State의 `code_content`, `problem_context` (테스트 케이스, 제한 시간·메모리 등).  
   - Judge0로 Correctness(통과율) → 통과 시 Performance(시간·메모리) 평가.  
   - State 갱신: `code_correctness_score`, `code_performance_score`, `execution_time`, `memory_used_mb`, `test_cases_passed`, `test_cases_total`, `correctness_reasoning`.

5. **노드 N6 — Eval Static Analysis (Radon CC)**  
   - **데이터 소스**: State의 `code_content`.  
   - Radon 순환 복잡도(CC) 정적 분석.  
   - State 갱신: `code_quality_metrics` (`radon_cc.avg_cc`, `radon_cc.max_cc`, `junior_grade` 등).

6. **노드 N7 — Eval Code Agent (LLM 코드 리뷰)**  
   - **데이터 소스**: State의 `code_content`, `code_correctness_score`, `code_performance_score`, `execution_time`, `memory_used_mb`, `code_quality_metrics`, `problem_context`.  
   - 단일 LLM 호출로 효율성·가독성·예외처리·종합 정성 리뷰 생성.  
   - State 갱신: `code_eval_report` (`efficiency_review`, `readability_review`, `error_handling_review`, `overall_summary`, `score_adjustment_note`).

7. **노드 N8 — Holistic Debate (다중 에이전트 토론)**  
   - **데이터 소스**:  
     - N4 Redis `turn_logs` (대화 원문 요약, rubric_breakdown, final_reasoning) — 직접 Redis 조회  
     - N5 Judge0 상세 (execution_time, memory_used_mb, test_cases_passed/total)  
     - N6 Radon CC 지표  
     - N7 코드 리뷰 전문  
   - **SubGraph 구조 (subgraph_debate.py)**:  
     ```
     START → [Round 1 병렬: r1_strict | r1_advocate | r1_neutral]
          → sync_opinions (팬인)
          → r2_strict → r2_advocate → r2_neutral (순차)
          → final_verdict → END
     ```
   - 에이전트 모델: strict=Gemini 2.5 Pro(temp 0.1) / advocate=Gemini 2.0 Flash(temp 0.3) / neutral=Gemini 1.5 Pro(temp 0.2) / verdict=Gemini 2.5 Pro(temp 0.0)  
   - State 갱신: `holistic_flow_score`, `holistic_flow_analysis`, `r4_context_maintenance_score` (세션 전체 맥락 궤적 분석), `debate_log`.
   - **저장**: Redis `debate_log:{session_id}`.

8. **노드 N9 — Aggregate Final Scores**  
   - 가중치: Prompt 40% (holistic_flow × 0.60 + aggregate_turn × 0.40), Correctness 40%, Performance 20%.  
   - **PostgreSQL** `scores`: `submission_id`, `prompt_score`, `perf_score`, `correctness_score`, `total_score`, `rubric_json` (holistic 분석, code_eval_report, debate_log 등 포함).  
   - `submissions.status = 'DONE'`, `prompt_sessions.ended_at` 설정.

#### Judge0·점수 메모

- Correctness 평가 결과에서 `execution_time`, `memory_used` 추출 (별도 Performance 실행 없이 재사용).  
- Correctness 실패(0점) 시 Performance도 0점 처리.  
- `scores.rubric_json`에 `holistic_flow_analysis`, `r4_context_maintenance_score`, `code_eval_report`, `debate_log` 등 전체 평가 근거 저장.

### 1.4 Redis / PostgreSQL 한눈에 보기

**Redis**

| 키 패턴 | 내용 |
|---------|------|
| `graph_state:{session_id}` | State 전체(messages, current_turn, problem_context 등) |
| `turn_mapping:{session_id}` | 턴–메시지 인덱스 매핑 |
| `turn_logs:{session_id}:{turn}` | 턴별 평가 로그 (V3.0: `rubric_breakdown`, `applied_rubrics` 포함) |
| `session_token:{session_id}` | 토큰 누적 |
| `debate_log:{session_id}` | N8 다중 에이전트 토론 전체 기록 (TTL 3600초) |

**PostgreSQL**

| 테이블 | 용도 | 시점 |
|--------|------|------|
| `prompt_sessions` | 세션 | 생성·종료 시 |
| `prompt_messages` | 대화 행 저장 | **현재 문서 기준**: 대화 본문은 Redis 위주; 별도 백엔드 정책이 없으면 여기에 채팅 메시지를 쌓지 않음 |
| `prompt_evaluations` | 턴 평가 | 제출 시 (N4, `evaluation_type='TURN_EVAL'`) |
| `submissions` | 제출 | 제출 플로우 |
| `scores` | 최종 점수 (`rubric_json`에 holistic 분석·debate_log 포함) | N9 |

### 1.5 운영 시 확인 방법

**Redis (예시)**

```python
state = await redis_client.get_graph_state("session_1000")
messages = state.get("messages", [])
turn_mapping = await redis_client.get_turn_mapping("session_1000")
turn_logs = await redis_client.get_all_turn_logs("session_1000")
```

**PostgreSQL**

```sql
SELECT * FROM prompt_evaluations
WHERE session_id = 1000
ORDER BY turn, evaluation_type;

SELECT submission_id, total_score, rubric_json
FROM scores
WHERE submission_id = 1000;
```

---

## 2. State 구조

### 2.1 LangGraph State (메모리)

`MainGraphState`(TypedDict) 예시 개념:

- `messages`: `Annotated[list, add_messages]` — **LangChain `BaseMessage`** 리스트(`HumanMessage`, `AIMessage` 등).  
- `add_messages` 리듀서로 메시지 병합.  
- 커스텀 필드: `turn`, `timestamp` 등 객체 속성으로 유지 가능.

### 2.2 PostgreSQL 쪽 모델 (참고)

`PromptMessage` 형태의 관계형 레코드:

- `session_id`, `turn`, `role`(`PromptRoleEnum`: user/assistant), `content`, `token_count`, `meta`(JSONB), `created_at` 등.  
- LangChain 객체와 **스키마가 다름** → 변환 레이어가 필요.

### 2.3 Redis에 넣는 형식

`StateRepository._serialize_messages` 등으로 **JSON 직렬화 가능한 dict**로 바꿔 저장한다.

예:

```json
{
  "messages": [
    {"type": "human", "content": "...", "turn": 1, "timestamp": "..."},
    {"type": "ai", "content": "...", "turn": 1, "timestamp": "..."}
  ],
  "current_turn": 1,
  "session_id": "session_123"
}
```

실제 키는 구현에 따라 `graph_state:{session_id}`를 사용한다(코드베이스 기준).

### 2.4 형식 불일치로 생기는 이슈

1. **직렬화/역직렬화**: LangGraph 메시지 ↔ Redis dict ↔ `PromptMessage`는 각각 변환 함수가 필요.  
2. **타입**: LangChain 타입 vs `PromptRoleEnum` vs Redis `type: "human"|"ai"`.  
3. **메타데이터**: `turn`, `timestamp`를 Redis/DB 어디에 넣을지 정하지 않으면 손실 위험.

### 2.5 요청 라이프사이클 State 변화 (요약)

- 첫 요청: Redis에 없으면 초기 State(빈 `messages`, `current_turn` 0 등)에서 시작.  
- Node 1(Handle Request): `current_turn` 증가 등.  
- Node 2(Intent Analyzer): `intent_status`, guardrail 관련 필드.  
- Node 3(Writer): `messages`에 턴 단위 user/assistant 반영, `writer_status` 등.  
- 이후 `save_state`로 dict 직렬화 후 Redis에 저장.  
- 다음 요청: Redis에서 dict 로드 → `_deserialize_messages`로 `BaseMessage` 복원 → `ainvoke` 재개.

(상세 플로우는 아래 Redis vs Memory 절과 제출 절과 합쳐서 이해하면 된다.)

---

## 3. Redis vs Memory (LangGraph)

### 3.1 역할 정리

| 구분 | 설명 |
|------|------|
| **LangGraph State (메모리)** | `ainvoke` 구간 동안만 유효. 노드는 `state.get("messages")`로 **메모리** State만 참조. |
| **Redis** | 실행 **전** 로드, 실행 **후** 저장. 실행 중에는 State 읽기/쓰기를 Redis에 직접 하지 않는다. |
| **MemorySaver** | LangGraph 체크포인터는 **인메모리**. Redis의 `graph_state`는 별도 영속 계층. |

```python
# app/application/services/eval_service.py (개념)
self.checkpointer = MemorySaver()
self.graph = create_main_graph(self.checkpointer)
```

### 3.2 시점별 State 위치

| 시점 | State 위치 |
|------|------------|
| LangGraph 실행 전 | Redis → 로드 후 메모리 변수 |
| LangGraph 실행 중 | **메모리** |
| LangGraph 실행 후 | `save_state`로 Redis |

### 3.3 직렬화 / 역직렬화

**Redis → LangGraph**

- Redis에서 온 dict의 `messages`를 `HumanMessage` / `AIMessage` 등으로 복원.  
- `turn`, `timestamp` 등 커스텀 속성 보존.

**LangGraph → Redis**

- `_serialize_messages`: `BaseMessage` → dict, JSON 저장 가능 형태.

개념 예:

```python
# Redis dict → 메모리
messages = state.get("messages", [])  # 이미 역직렬화된 BaseMessage 리스트

# (잘못된 가정) 실행 중 Redis에서 직접 messages 읽기 — 하지 않음
```

### 3.4 일반 채팅 시퀀스

1. `POST /api/chat/messages`  
2. `get_state` → Redis `graph_state:*` → 역직렬화 → 메모리  
3. `ainvoke` — 메모리에서만 State 갱신  
4. Writer에서 `messages` append  
5. `save_state` — 직렬화 후 Redis

### 3.5 제출 시 노드별 데이터 소스

| 노드 | 주요 소스 | 비고 |
|------|-----------|------|
| **N4 Eval Turn Guard** | 메모리 State `messages` | `turn_mapping` Redis 조회 안 함 |
| **N5 Eval Code Execution** | State `code_content`, `problem_context` | Judge0 호출 |
| **N6 Eval Static Analysis** | State `code_content` | Radon CC 정적 분석 |
| **N7 Eval Code Agent** | State `code_content` + N5·N6 결과 | 단일 LLM 리뷰 |
| **N8 Holistic Debate** | Redis `turn_logs:*` (직접 조회) + N5 상세 metrics + N6 지표 + N7 리뷰 | 서브그래프 토론 (2라운드×3 에이전트 + 판결) |
| **N9 Aggregate Final Scores** | N4 `aggregate_turn_score` + N8 `holistic_flow_score` + N5 점수 | 최종 집계·DB 저장 |

제출 시 N4 이후 흐름(개념):

1. `submit_code()` → `get_state` (Redis → 메모리)  
2. `ainvoke`  
3. N4: `state.get("messages")` — 메모리, 턴별 V3.0 루브릭 평가 → Redis `turn_logs`, PG `prompt_evaluations`  
4. N5 → N6 → N7 → N8 순차 실행  
5. N8: Redis `turn_logs` 직접 재조회 → 서브그래프 토론 → `holistic_flow_score`, `r4_context_maintenance_score`  
6. N9: 최종 점수 집계 → PG `scores`  
7. 그래프 종료 후 `save_state` → Redis `graph_state`

---

## 4. DB 저장 전략

### 4.1 Redis

- **시점**: LangGraph **한 번 실행이 끝난 뒤** `state_repo.save_state`로 `graph_state` 갱신이 기본 패턴.  
- **턴 로그**: 노드 4에서 `turn_logs:{session_id}:{turn}`에 JSON 저장.  
- **턴 매핑**: `turn_mapping:{session_id}` — **노드 4 평가 경로에서는 사용하지 않음**(messages에서 턴 추출).  
- **TTL**: `graph_state` 등은 설정값 사용(문서상 예: **3600초** 또는 환경에 따라 **86400초** 등 — `config`의 `CHECKPOINT_TTL` 계열과 맞출 것).

### 4.2 PostgreSQL — 현재 동작과 설계 이슈

- **평가·점수**: 제출 플로우에서 `prompt_evaluations`, `scores`, `submissions`, 세션 종료 필드가 갱신된다.  
- **대화 텍스트**: 현재 운영 설명상 **Redis `graph_state`의 `messages`가 사실상의 소스**이며, `prompt_messages`에 매 채팅마다 넣는 것은 필수로 문서화되어 있지 않다.

### 4.3 LangGraph ↔ PostgreSQL 변환 (참고 구현 스케치)

Redis dict 한 건을 `PromptMessage`로 옮길 때 개념:

- `type` 매핑: `human`/`user` → `USER`, `ai`/`assistant` → `ASSISTANT`.  
- `meta`에 `timestamp`, `original_type` 등 보존.  
- `session_repo.add_message_from_langgraph_state` 같은 헬퍼로 일원화할 수 있음.

### 4.4 형식 변환 매트릭스

| 항목 | LangGraph(메모리) | Redis | PostgreSQL |
|------|-------------------|--------|------------|
| 메시지 타입 | `HumanMessage`, `AIMessage` | `{"type": "human"\|"ai", ...}` | `PromptRoleEnum` |
| 구조 | LangChain 객체 | JSON dict | 행(ORM) |
| 턴 | 객체 속성 | dict `turn` | 컬럼 `turn` |
| 타임스탬프 | 객체 속성 | dict 필드 | `meta` JSONB 등 |

### 4.5 직렬화 함수 예시 (개념 코드)

**LangGraph → Redis**

```python
def serialize_langgraph_message(msg) -> dict:
    if hasattr(msg, "type"):
        return {
            "type": msg.type,
            "content": msg.content,
            "turn": getattr(msg, "turn", None),
            "timestamp": getattr(msg, "timestamp", None),
        }
    if isinstance(msg, dict):
        return msg
    return {"content": str(msg)}
```

**Redis dict → LangGraph**

```python
def deserialize_redis_message(msg_dict: dict):
    from langchain_core.messages import HumanMessage, AIMessage
    msg_type = msg_dict.get("type", "unknown")
    content = msg_dict.get("content", "")
    if msg_type == "human":
        msg = HumanMessage(content=content)
    elif msg_type == "ai":
        msg = AIMessage(content=content)
    else:
        raise ValueError(f"Unknown message type: {msg_type}")
    if "turn" in msg_dict:
        msg.turn = msg_dict["turn"]
    if "timestamp" in msg_dict:
        msg.timestamp = msg_dict["timestamp"]
    return msg
```

### 4.6 장점·개선 방향 (요약)

**장점**

- Redis: 낮은 지연으로 State·턴 로그 관리.  
- PostgreSQL: 평가·점수·세션 영구 보관.  
- 역할 분리가 명확.

**개선 아이디어**

1. 변환 로직 중앙화(`serialize` / `deserialize` / DB 적재).  
2. `turn`, `timestamp` 등 메타 손실 방지 규칙 명문화.  
3. (선택) 채팅 중 백그라운드로 `prompt_messages` 동기화.  
4. 변환 실패 시 롤백·재시도·모니터링.

권장 순서 예: 변환 함수 테스트 → 채팅 중 DB 저장(선택) → 메타 보존 강화 → 에러 처리.

---

## 부록: 평가 시 데이터 소스 재확인 (현행)

| 노드 | 데이터 소스 | 저장 위치 |
|------|------------|----------|
| **N4** | 메모리 `messages`만 (Redis 직접 읽기 없음) | Redis `turn_logs`, PG `prompt_evaluations` |
| **N5** | State `code_content`, `problem_context` | State 필드 (`code_correctness_score` 등) |
| **N6** | State `code_content` | State `code_quality_metrics` |
| **N7** | State `code_content` + N5·N6 결과 | State `code_eval_report` |
| **N8** | Redis `turn_logs:*` (직접 재조회) + N5~N7 State 필드 | State `holistic_flow_score`, `r4_context_maintenance_score`, `debate_log` |
| **N9** | 모든 평가 State 필드 | PG `scores` |
| **일반 채팅** | 없음 (평가 없음) | Redis `graph_state`, `turn_mapping`, `session_token` |
