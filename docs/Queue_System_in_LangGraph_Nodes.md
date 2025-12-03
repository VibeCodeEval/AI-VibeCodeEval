# LangGraph 노드 내 큐 시스템 통합

## 🤔 문제 제기

**사용자 질문**: Judge0도 LangGraph 노드 내에서 호출되는데, 왜 Judge0만 큐 시스템이 필요한가?

**핵심 이슈**:
- Judge0: `6c`, `6d` 노드 내에서 호출 예정
- Eval Turn SubGraph: 이미 백그라운드 실행 (`asyncio.create_task`)
- 둘 다 LangGraph 노드인데, 왜 Judge0만 큐 시스템?

---

## 📊 현재 상황 분석

### 1. Eval Turn SubGraph (현재 방식)

```python
# app/application/services/eval_service.py
async def process_message(...):
    # ... 메인 플로우 실행 ...
    
    # 일반 채팅인 경우 백그라운드로 실행
    if not is_submission and result.get("ai_message"):
        asyncio.create_task(
            self._run_eval_turn_background(session_id, result)
        )
```

**특징**:
- ✅ 이미 비동기 실행 (백그라운드)
- ❌ API 서버 프로세스 내부에서 실행
- ❌ API 서버 재시작 시 작업 손실
- ❌ Worker 확장 불가

### 2. Judge0 (계획 중)

```python
# app/domain/langgraph/nodes/holistic_evaluator/performance.py
async def _eval_code_performance_impl(state: MainGraphState):
    # TODO: Judge0 API 연동
    # 현재는 LLM 기반 평가로 대체
    
    # 만약 직접 호출한다면?
    result = await judge0_client.execute(code)  # 5-10초 블로킹
    return {"code_performance_score": result.score}
```

**특징**:
- ❌ 노드 내에서 동기적으로 호출 예정
- ❌ 5-10초 블로킹
- ❌ LangGraph 전체 플로우 지연

---

## 💡 해결 방안: 노드 내 큐 시스템 통합

### 방법 1: 노드 내에서 큐 사용 (폴링)

```python
# app/domain/langgraph/nodes/holistic_evaluator/performance.py

async def _eval_code_performance_impl(state: MainGraphState) -> Dict[str, Any]:
    """6c: 코드 성능 평가 (큐 시스템 사용)"""
    session_id = state.get("session_id", "unknown")
    code_content = state.get("code_content")
    
    if not code_content:
        return {"code_performance_score": None}
    
    # 1. 큐 어댑터 생성
    from app.domain.queue.factory import create_queue_adapter
    queue = create_queue_adapter()
    
    # 2. 작업 생성 및 큐에 추가
    from app.domain.queue.adapters.base import JudgeTask
    import uuid
    
    task = JudgeTask(
        task_id=f"perf_{session_id}_{uuid.uuid4().hex[:8]}",
        code=code_content,
        language="python",
        test_cases=get_test_cases(state),
        timeout=5,
        memory_limit=128
    )
    
    task_id = await queue.enqueue(task)
    logger.info(f"[6c] 작업 추가 - task_id: {task_id}")
    
    # 3. 결과 대기 (폴링)
    max_wait = 30  # 최대 30초 대기
    start_time = time.time()
    poll_interval = 0.5  # 0.5초마다 확인
    
    while time.time() - start_time < max_wait:
        status = await queue.get_status(task_id)
        
        if status == "completed":
            # 결과 조회
            result = await queue.get_result(task_id)
            
            # 성능 점수 계산
            score = calculate_performance_score(result)
            
            return {
                "code_performance_score": score,
                "execution_time": result.execution_time,
                "memory_used": result.memory_used,
                "updated_at": datetime.utcnow().isoformat()
            }
        
        elif status == "failed":
            logger.error(f"[6c] 작업 실패 - task_id: {task_id}")
            return {
                "code_performance_score": 0,
                "error": "코드 실행 실패",
                "updated_at": datetime.utcnow().isoformat()
            }
        
        # 아직 처리 중이면 대기
        await asyncio.sleep(poll_interval)
    
    # 타임아웃
    logger.warning(f"[6c] 작업 타임아웃 - task_id: {task_id}")
    return {
        "code_performance_score": None,
        "error": "타임아웃",
        "updated_at": datetime.utcnow().isoformat()
    }
```

**장점**:
- ✅ 노드 내에서 큐 시스템 사용 가능
- ✅ Worker가 별도로 실행
- ✅ 확장 가능

**단점**:
- ⚠️ 폴링으로 인한 약간의 오버헤드
- ⚠️ 최대 대기 시간 설정 필요

---

### 방법 2: 노드를 두 단계로 분리

```python
# Step 1: 작업 추가 노드
async def eval_code_performance_enqueue(state: MainGraphState) -> Dict[str, Any]:
    """6c-1: 코드 실행 작업 추가"""
    queue = create_queue_adapter()
    task = JudgeTask(...)
    task_id = await queue.enqueue(task)
    
    return {
        "judge_task_id": task_id,
        "judge_status": "pending"
    }

# Step 2: 결과 조회 노드
async def eval_code_performance_result(state: MainGraphState) -> Dict[str, Any]:
    """6c-2: 코드 실행 결과 조회"""
    task_id = state.get("judge_task_id")
    queue = create_queue_adapter()
    
    status = await queue.get_status(task_id)
    
    if status == "completed":
        result = await queue.get_result(task_id)
        score = calculate_performance_score(result)
        return {
            "code_performance_score": score,
            "judge_status": "completed"
        }
    elif status == "pending" or status == "processing":
        # 아직 처리 중이면 다시 이 노드로 돌아오기
        return {
            "judge_status": status,
            "code_performance_score": None
        }
    else:
        return {
            "judge_status": "failed",
            "code_performance_score": 0
        }
```

**그래프 구조**:
```
6c-1 (enqueue) → 조건부 분기 → 6c-2 (result)
                      ↓ (pending/processing)
                  6c-2로 다시 돌아가기
                      ↓ (completed/failed)
                  다음 노드로 진행
```

**장점**:
- ✅ LangGraph의 조건부 분기 활용
- ✅ 폴링 오버헤드 없음
- ✅ 상태 기반 라우팅

**단점**:
- ⚠️ 노드가 두 개로 분리됨
- ⚠️ 그래프 구조 복잡도 증가

---

## 🔄 Eval Turn SubGraph도 큐 시스템 적용

### 현재 방식 vs 큐 시스템

**현재 방식**:
```python
# EvalService에서 직접 실행
asyncio.create_task(
    self._run_eval_turn_background(session_id, result)
)
```

**큐 시스템 적용**:
```python
# app/domain/langgraph/nodes/writer.py
async def writer_llm(state: MainGraphState) -> Dict[str, Any]:
    # ... Writer LLM 실행 ...
    
    # 평가 작업을 큐에 추가
    if not state.get("is_submitted"):
        from app.domain.queue.factory import create_queue_adapter
        from app.domain.queue.adapters.base import EvalTurnTask
        
        eval_queue = create_queue_adapter(queue_type="eval")
        
        eval_task = EvalTurnTask(
            task_id=f"eval_{session_id}_{current_turn}",
            session_id=session_id,
            turn=current_turn,
            human_message=state.get("human_message"),
            ai_message=ai_content,
            problem_context=state.get("problem_context")
        )
        
        await eval_queue.enqueue(eval_task)
        logger.info(f"[Writer] 평가 작업 추가 - task_id: {eval_task.task_id}")
    
    return {"ai_message": ai_content, ...}
```

**Worker**:
```python
# app/application/workers/eval_worker.py
async def worker_loop():
    eval_queue = create_queue_adapter(queue_type="eval")
    
    while True:
        task = await eval_queue.dequeue()
        if task is None:
            await asyncio.sleep(0.1)
            continue
        
        try:
            # Eval Turn SubGraph 실행
            from app.domain.langgraph.subgraph_eval_turn import create_eval_turn_subgraph
            
            eval_turn_subgraph = create_eval_turn_subgraph()
            result = await eval_turn_subgraph.ainvoke({
                "session_id": task.session_id,
                "turn": task.turn,
                "human_message": task.human_message,
                "ai_message": task.ai_message,
                ...
            })
            
            # 결과 저장
            await eval_queue.save_result(task.task_id, result)
            
        except Exception as e:
            logger.error(f"평가 실패: {e}")
            await eval_queue.save_result(task.task_id, {"error": str(e)})
```

---

## 📊 비교: 현재 vs 큐 시스템

| 항목 | Eval Turn (현재) | Judge0 (계획) | Eval Turn (큐) | Judge0 (큐) |
|------|------------------|---------------|----------------|-------------|
| 실행 위치 | API 서버 프로세스 | 노드 내 동기 | 별도 Worker | 별도 Worker |
| 확장성 | ❌ | ❌ | ✅ | ✅ |
| 에러 격리 | ⚠️ | ❌ | ✅ | ✅ |
| 재시작 안정성 | ❌ | ❌ | ✅ | ✅ |
| 폴링 필요 | ❌ | ❌ | ❌ | ✅ (노드 내) |

---

## 🎯 결론 및 권장사항

### 1. Judge0는 큐 시스템 필수

**이유**:
- 코드 실행은 5-10초 소요 (블로킹)
- Docker 컨테이너 실행은 리소스 집약적
- 노드 내에서 폴링 방식으로 통합 가능

**구현**:
- 방법 1 (폴링) 권장: 간단하고 직관적
- 방법 2 (노드 분리): 더 복잡하지만 LangGraph 패턴에 부합

### 2. Eval Turn도 큐 시스템 적용 권장

**이유**:
- 현재 `asyncio.create_task()`는 프로세스 내부 실행
- API 서버 재시작 시 작업 손실
- Worker 확장 불가

**구현**:
- Writer 노드에서 큐에 작업 추가
- 별도 Eval Worker가 처리
- 폴링 불필요 (백그라운드 작업이므로)

### 3. 통합 전략

```
┌─────────────────────────────────────────────────────────┐
│              LangGraph 노드들                           │
│                                                         │
│  Writer Node                                            │
│    → Eval Queue에 작업 추가 (백그라운드)                │
│                                                         │
│  6c Performance Node                                    │
│    → Judge Queue에 작업 추가                            │
│    → 폴링으로 결과 대기                                 │
│    → 결과 반환                                          │
│                                                         │
│  6d Correctness Node                                    │
│    → Judge Queue에 작업 추가                            │
│    → 폴링으로 결과 대기                                 │
│    → 결과 반환                                          │
└─────────────────────────────────────────────────────────┘
         ↓                    ↓
┌─────────────────────────────────────────────────────────┐
│              Redis Queues                               │
│                                                         │
│  eval_queue:pending                                     │
│  judge_queue:pending                                    │
└─────────────────────────────────────────────────────────┘
         ↓                    ↓
┌─────────────────────────────────────────────────────────┐
│              Workers                                    │
│                                                         │
│  Eval Worker (Eval Turn SubGraph 실행)                 │
│  Judge Worker (코드 실행)                                │
└─────────────────────────────────────────────────────────┘
```

---

## 📝 요약

**사용자 질문에 대한 답변**:

1. **Judge0만 큐 시스템이 필요한가?**
   - ❌ 아니요. Eval Turn도 큐 시스템 적용 가능 (권장)

2. **노드 내에서 큐 시스템 사용 가능한가?**
   - ✅ 가능합니다. 폴링 방식으로 통합 가능

3. **차이점은?**
   - **Eval Turn**: 백그라운드 작업 (폴링 불필요)
   - **Judge0**: 노드 내에서 결과 필요 (폴링 필요)

4. **권장사항**:
   - Judge0: 큐 시스템 필수 (노드 내 폴링)
   - Eval Turn: 큐 시스템 권장 (백그라운드 큐)

**핵심**: 둘 다 큐 시스템 적용 가능하며, 노드 내에서도 사용 가능합니다!

