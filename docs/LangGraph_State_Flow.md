# LangGraph State와 Redis의 관계

## 🔍 핵심 개념

### LangGraph State vs Redis

1. **LangGraph State (메모리)**
   - LangGraph 실행 중에는 State가 **메모리**에 있음
   - 각 노드에서 `state.get("messages")`는 메모리의 State 객체에서 가져옴
   - `MemorySaver`를 사용하여 체크포인트 관리 (in-memory)

2. **Redis (영구 저장소)**
   - LangGraph 실행 **전**: Redis에서 State 로드
   - LangGraph 실행 **후**: Redis에 State 저장
   - 실행 중에는 Redis를 직접 사용하지 않음

---

## 📊 데이터 흐름 상세

### 1. 일반 채팅 (Chat)

```
[1] API 호출
    POST /api/chat/messages
    
[2] State 로드 (Redis → 메모리)
    state_repo.get_state(session_id)
    → Redis: graph_state:session_1000 조회
    → **역직렬화**: dict 형태의 messages → LangChain BaseMessage 객체로 변환
    → 메모리: state 변수에 저장 (LangGraph가 사용할 수 있는 형태)
    
[3] LangGraph 실행 (메모리)
    self.graph.ainvoke(state, config)
    → State는 메모리에서 실행됨
    → 각 노드에서 state.get("messages")는 메모리 State에서 가져옴
    
[4] Writer 노드에서 메시지 추가
    state["messages"].append(new_message)
    → 메모리 State에 메시지 추가
    
[5] State 저장 (메모리 → Redis)
    state_repo.save_state(session_id, result)
    → 메모리 State를 Redis에 저장
```

### 2. 제출 (Submit) - 4번 노드

```
[1] State 로드 (Redis → 메모리)
    state_repo.get_state(session_id)
    → Redis: graph_state:session_1000 조회
    → **역직렬화**: dict 형태의 messages → LangChain BaseMessage 객체로 변환
    → 메모리: state 변수에 저장 (LangGraph가 사용할 수 있는 형태)
    
[2] LangGraph 실행 (메모리)
    self.graph.ainvoke(state, config)
    → State는 메모리에서 실행됨
    
[3] 4번 노드: Eval Turn Guard
    messages = state.get("messages", [])
    → ⚠️ 메모리의 LangGraph State 객체에서 가져옴
    → Redis에서 직접 가져오는 것이 아님!
    
[4] 각 턴 평가
    - State의 messages 배열에서 턴별 메시지 추출
    - Eval Turn SubGraph 실행
    - 평가 결과를 Redis와 PostgreSQL에 저장
    
[5] State 저장 (메모리 → Redis)
    state_repo.save_state(session_id, result)
    → 메모리 State를 Redis에 저장
```

---

## ⚠️ 중요 사항

### 1. State 변환 (Redis → LangGraph)

**역직렬화 과정:**
```python
# Redis에서 가져온 dict 형태
redis_state = {
    "messages": [
        {"type": "human", "content": "...", "turn": 1},
        {"type": "ai", "content": "...", "turn": 1}
    ]
}

# StateRepository.get_state()에서 역직렬화
# dict → LangChain BaseMessage 객체로 변환
langgraph_state = {
    "messages": [
        HumanMessage(content="...", turn=1),
        AIMessage(content="...", turn=1)
    ]
}
```

### 2. State 접근 시점

**4번 노드에서:**
```python
# ❌ 잘못된 이해
messages = await redis_client.get_graph_state(session_id).get("messages")

# ✅ 올바른 이해
# LangGraph 실행 중에는 State가 메모리에 있음
# State는 이미 역직렬화되어 LangChain BaseMessage 객체로 변환됨
messages = state.get("messages", [])  # 메모리 State 객체에서 가져옴
# messages는 LangChain BaseMessage 객체 리스트
```

### 2. Redis의 역할

- **State 영구 저장**: LangGraph 실행 전/후에 State를 Redis에 저장/로드
- **체크포인트 관리**: LangGraph의 MemorySaver는 in-memory이므로, Redis에 별도 저장
- **턴 로그 저장**: `turn_logs:{session_id}:{turn}` (평가 결과) - **6번 노드에서 사용**
- **턴 매핑 저장**: `turn_mapping:{session_id}` (메시지 인덱스 매핑) - **4번 노드에서 사용하지 않음** (State의 messages에서 직접 조회)

### 3. 데이터 타입 변환

**Redis → LangGraph State:**
- `_deserialize_messages()`: dict → LangChain BaseMessage 객체
- `turn`, `timestamp` 등 커스텀 속성 보존

**LangGraph State → Redis:**
- `_serialize_messages()`: LangChain BaseMessage 객체 → dict
- JSON 직렬화 가능한 형태로 변환

### 4. LangGraph의 MemorySaver

```python
# app/application/services/eval_service.py
self.checkpointer = MemorySaver()  # in-memory checkpointer
self.graph = create_main_graph(self.checkpointer)
```

- MemorySaver는 **메모리**에만 체크포인트 저장
- Redis는 별도로 State를 저장/로드하는 용도
- LangGraph 실행 중에는 State가 메모리에 있음

### 5. 4번 노드 vs 6번 노드 데이터 소스

**4번 노드 (Eval Turn Guard):**
- **LangGraph State**에서 `messages` 추출 (메모리에서 직접 사용)
- State는 이미 역직렬화되어 LangChain BaseMessage 객체로 변환됨
- `turn` 정보는 메시지 객체의 속성으로 접근
- **Redis turn_mapping 조회하지 않음** - State의 messages에서 turn 정보로 직접 검색

**6번 노드 (Holistic Flow Evaluation):**
- **Redis**에서 `turn_logs:{session_id}:*` 조회
- 4번 노드에서 평가한 결과를 Redis에 저장한 것을 사용
- State의 messages는 참고용으로만 사용

---

## 🔄 정확한 데이터 흐름

### 제출 시 4번 노드 평가

```
1. eval_service.submit_code() 호출
   ↓
2. state_repo.get_state(session_id)
   → Redis에서 State 로드
   → 메모리 변수에 저장
   ↓
3. self.graph.ainvoke(state, config)
   → LangGraph 실행 시작
   → State는 메모리에서 실행됨
   ↓
4. 4번 노드: eval_turn_submit_guard(state)
   → state.get("messages", [])
   → ⚠️ 메모리의 LangGraph State 객체에서 가져옴
   → Redis에서 직접 가져오는 것이 아님!
   ↓
5. 각 턴 평가
   → State의 messages 배열에서 턴별 메시지 추출
   → Eval Turn SubGraph 실행
   ↓
6. 평가 결과 저장
   → Redis: turn_logs:{session_id}:{turn}
   → PostgreSQL: prompt_evaluations
   ↓
7. LangGraph 실행 완료
   ↓
8. state_repo.save_state(session_id, result)
   → 메모리 State를 Redis에 저장
```

---

## 📝 요약

| 시점 | State 위치 | 설명 |
|------|-----------|------|
| **LangGraph 실행 전** | Redis | `state_repo.get_state()`로 Redis에서 로드 |
| **LangGraph 실행 중** | **메모리** | 각 노드에서 `state.get()`은 메모리 State에서 가져옴 |
| **LangGraph 실행 후** | Redis | `state_repo.save_state()`로 Redis에 저장 |

**4번 노드에서 `state.get("messages")`는:**
- ✅ **LangGraph State (메모리)**에서 가져옴
- ❌ Redis에서 직접 가져오는 것이 아님

