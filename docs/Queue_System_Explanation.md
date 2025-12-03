# 큐 시스템 동작 방식 설명

## 🎯 왜 큐 시스템이 필요한가?

### 현재 문제점
```
사용자 코드 제출
    ↓
LangGraph 노드 (6c, 6d)에서 코드 실행 요청
    ↓
❌ 직접 실행? → API 서버가 블로킹됨 (느림)
❌ Judge0 직접 호출? → 외부 의존성, 확장성 부족
```

### 큐 시스템 도입 후
```
사용자 코드 제출
    ↓
큐에 작업 추가 (enqueue) → 즉시 응답 반환 ✅
    ↓
별도 Worker 프로세스가 큐에서 작업 가져와서 실행 (dequeue)
    ↓
결과를 Redis에 저장
    ↓
API에서 결과 조회 (polling 또는 callback)
```

---

## 📊 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    API 서버 (FastAPI)                        │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  LangGraph 노드 (6c, 6d)                           │    │
│  │  - 코드 실행 요청                                   │    │
│  │  - 큐에 작업 추가 (enqueue)                        │    │
│  │  - 즉시 task_id 반환                               │    │
│  └────────────────────────────────────────────────────┘    │
│                          ↓                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │  QueueAdapter                                       │    │
│  │  - enqueue(task) → task_id                         │    │
│  │  - get_status(task_id) → "pending"                 │    │
│  │  - get_result(task_id) → 결과 조회                 │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    Redis                                     │
│                                                              │
│  judge_queue:pending  [Task1, Task2, Task3, ...]            │
│  judge_status:task_1  "processing"                          │
│  judge_result:task_1  {output: "...", time: 0.5s, ...}     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              Worker 프로세스 (별도 프로세스)                 │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Queue Worker                                      │    │
│  │  while True:                                       │    │
│  │    task = queue.dequeue()  # 큐에서 작업 가져오기  │    │
│  │    result = execute_code(task)  # 코드 실행        │    │
│  │    save_result(task_id, result)  # 결과 저장       │    │
│  └────────────────────────────────────────────────────┘    │
│                          ↓                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Code Executor                                      │    │
│  │  - Docker 컨테이너 실행                            │    │
│  │  - 테스트 케이스 실행                               │    │
│  │  - 메모리/시간 측정                                │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 상세 동작 흐름

### 1단계: 코드 제출 (API 서버)

```python
# app/domain/langgraph/nodes/holistic_evaluator/performance.py

async def _eval_code_performance_impl(state: MainGraphState):
    code_content = state.get("code_content")
    
    # 큐 어댑터 생성
    queue = create_queue_adapter()  # Redis 또는 Memory
    
    # 작업 생성
    task = JudgeTask(
        task_id=f"task_{session_id}_{timestamp}",
        code=code_content,
        language="python",
        test_cases=get_test_cases(spec_id),
        timeout=5,
        memory_limit=128
    )
    
    # 큐에 추가 (비동기, 즉시 반환)
    task_id = await queue.enqueue(task)
    
    # 상태: "pending" → "processing" → "completed"
    
    # 즉시 task_id 반환 (블로킹 없음!)
    return {
        "task_id": task_id,
        "status": "pending",
        "code_performance_score": None  # 아직 계산 안 됨
    }
```

**핵심**: API 서버는 큐에 작업만 추가하고 즉시 응답 반환. 코드 실행은 기다리지 않음!

---

### 2단계: Worker가 작업 처리 (별도 프로세스)

```python
# app/application/workers/judge_worker.py

async def worker_loop():
    """Worker 메인 루프"""
    queue = create_queue_adapter()
    executor = CodeExecutor()
    
    while True:
        # 큐에서 작업 가져오기 (BLPOP - 블로킹 대기)
        task = await queue.dequeue()
        
        if task is None:
            await asyncio.sleep(0.1)  # 큐가 비어있으면 잠시 대기
            continue
        
        try:
            # 상태를 "processing"으로 변경
            await queue.set_status(task.task_id, "processing")
            
            # 코드 실행 (Docker 컨테이너에서)
            result = await executor.execute(
                code=task.code,
                language=task.language,
                test_cases=task.test_cases,
                timeout=task.timeout,
                memory_limit=task.memory_limit
            )
            
            # 결과 생성
            judge_result = JudgeResult(
                task_id=task.task_id,
                status="success",
                output=result.output,
                error=result.error,
                execution_time=result.execution_time,
                memory_used=result.memory_used,
                exit_code=result.exit_code
            )
            
            # 결과를 Redis에 저장
            await queue.save_result(task.task_id, judge_result)
            
            # 상태를 "completed"로 변경
            await queue.set_status(task.task_id, "completed")
            
        except Exception as e:
            # 에러 발생 시
            error_result = JudgeResult(
                task_id=task.task_id,
                status="error",
                output="",
                error=str(e),
                execution_time=0,
                memory_used=0,
                exit_code=1
            )
            await queue.save_result(task.task_id, error_result)
            await queue.set_status(task.task_id, "failed")
```

**핵심**: Worker는 별도 프로세스로 계속 실행되며, 큐에서 작업을 가져와서 실행하고 결과를 저장.

---

### 3단계: 결과 조회 (API 서버)

```python
# app/domain/langgraph/nodes/holistic_evaluator/performance.py

async def _eval_code_performance_impl(state: MainGraphState):
    # ... 작업 추가 후 ...
    
    task_id = await queue.enqueue(task)
    
    # 폴링으로 결과 대기 (또는 WebSocket으로 실시간 전달)
    max_wait = 30  # 최대 30초 대기
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        status = await queue.get_status(task_id)
        
        if status == "completed":
            # 결과 조회
            result = await queue.get_result(task_id)
            
            # 성능 점수 계산
            score = calculate_performance_score(result)
            
            return {
                "task_id": task_id,
                "status": "completed",
                "code_performance_score": score,
                "execution_time": result.execution_time,
                "memory_used": result.memory_used
            }
        
        elif status == "failed":
            return {
                "task_id": task_id,
                "status": "failed",
                "code_performance_score": 0,
                "error": "코드 실행 실패"
            }
        
        # 아직 처리 중이면 잠시 대기
        await asyncio.sleep(0.5)
    
    # 타임아웃
    return {
        "task_id": task_id,
        "status": "timeout",
        "code_performance_score": None
    }
```

**핵심**: API는 폴링으로 결과를 확인하거나, WebSocket으로 실시간 업데이트를 받을 수 있음.

---

## 🔀 큐 어댑터의 역할

### Adapter 패턴이란?

**인터페이스는 동일, 구현은 다름**

```python
# 인터페이스 (추상 클래스)
class QueueAdapter(ABC):
    @abstractmethod
    async def enqueue(self, task: JudgeTask) -> str:
        pass
    
    @abstractmethod
    async def dequeue(self) -> Optional[JudgeTask]:
        pass

# 메모리 구현 (개발/테스트용)
class MemoryQueueAdapter(QueueAdapter):
    def __init__(self):
        self.queue = deque()  # Python 메모리
    
    async def enqueue(self, task):
        self.queue.append(task)  # 메모리에 추가
    
    async def dequeue(self):
        return self.queue.popleft()  # 메모리에서 가져오기

# Redis 구현 (프로덕션용)
class RedisQueueAdapter(QueueAdapter):
    def __init__(self, redis):
        self.redis = redis
    
    async def enqueue(self, task):
        await self.redis.lpush("judge_queue", json.dumps(task))  # Redis에 추가
    
    async def dequeue(self):
        result = await self.redis.brpop("judge_queue")  # Redis에서 가져오기
        return json.loads(result[1])
```

**장점**:
- 개발 시: MemoryQueueAdapter 사용 (Redis 없이도 테스트 가능)
- 프로덕션: RedisQueueAdapter 사용 (분산 환경, 영속성)
- 코드 변경 없이 교체 가능!

---

## 📦 Redis 큐 구조

### Redis 데이터 구조

```
# 대기 중인 작업 큐 (List)
judge_queue:pending
  → ["{task_json}", "{task_json}", ...]  # LPUSH로 추가, BRPOP으로 가져오기

# 작업 상태 (String, TTL 1시간)
judge_status:task_123
  → "pending" | "processing" | "completed" | "failed"

# 실행 결과 (String, TTL 1시간)
judge_result:task_123
  → "{result_json}"  # JSON 문자열
```

### Redis 명령어 예시

```python
# 작업 추가
await redis.lpush("judge_queue:pending", task_json)

# 작업 가져오기 (블로킹, 최대 1초 대기)
result = await redis.brpop("judge_queue:pending", timeout=1)
if result:
    _, task_json = result
    task = json.loads(task_json)

# 상태 저장
await redis.set("judge_status:task_123", "processing", ex=3600)

# 결과 저장
await redis.set("judge_result:task_123", result_json, ex=3600)
```

---

## 🚀 실제 사용 예시

### 시나리오: 사용자가 코드 제출

```
1. 사용자: "코드 제출합니다"
   ↓
2. API: POST /api/chat/submit
   ↓
3. LangGraph: eval_code_performance 노드 실행
   ↓
4. 큐에 작업 추가:
   task_id = "task_abc123"
   status = "pending"
   ↓
5. API 즉시 응답:
   {
     "task_id": "task_abc123",
     "status": "pending",
     "message": "코드 실행 중..."
   }
   ↓
6. Worker (별도 프로세스):
   - 큐에서 task_abc123 가져오기
   - Docker 컨테이너에서 코드 실행
   - 결과 저장
   ↓
7. 클라이언트 폴링:
   GET /api/judge/result?task_id=task_abc123
   ↓
8. API 응답:
   {
     "task_id": "task_abc123",
     "status": "completed",
     "score": 85.5,
     "execution_time": 0.5,
     "memory_used": 1024
   }
```

---

## 💡 왜 이렇게 복잡하게?

### 문제 1: 동기 실행의 한계
```python
# ❌ 동기 실행 (현재 방식)
result = await execute_code(code)  # 5초 대기
return result  # 사용자는 5초 동안 기다림
```

**문제점**:
- API 서버가 블로킹됨
- 동시 요청 처리 불가
- 타임아웃 위험

### 해결: 비동기 큐
```python
# ✅ 비동기 큐
task_id = await queue.enqueue(task)  # 0.01초
return {"task_id": task_id}  # 즉시 응답

# Worker가 별도로 처리
# 클라이언트는 폴링 또는 WebSocket으로 결과 확인
```

**장점**:
- API 서버는 즉시 응답
- Worker는 독립적으로 실행
- 확장 가능 (Worker 여러 개 실행 가능)

---

## 🔧 구현 단계

### Step 1: 인터페이스 정의
```python
# app/domain/queue/adapters/base.py
class QueueAdapter(ABC):
    @abstractmethod
    async def enqueue(self, task: JudgeTask) -> str:
        """큐에 작업 추가"""
        pass
```

### Step 2: 메모리 구현 (테스트용)
```python
# app/domain/queue/adapters/memory.py
class MemoryQueueAdapter(QueueAdapter):
    # Python deque 사용
```

### Step 3: Redis 구현 (프로덕션)
```python
# app/domain/queue/adapters/redis.py
class RedisQueueAdapter(QueueAdapter):
    # Redis List 사용
```

### Step 4: Worker 구현
```python
# app/application/workers/judge_worker.py
async def main():
    queue = create_queue_adapter()
    while True:
        task = await queue.dequeue()
        if task:
            result = await execute_code(task)
            await queue.save_result(task.task_id, result)
```

### Step 5: 통합
```python
# app/domain/langgraph/nodes/holistic_evaluator/performance.py
queue = create_queue_adapter()
task_id = await queue.enqueue(task)
# 결과 조회 로직 추가
```

---

## 📝 요약

1. **큐 시스템의 목적**: 코드 실행을 비동기로 처리하여 API 서버의 응답 속도 향상
2. **동작 방식**: 
   - API → 큐에 작업 추가 → 즉시 응답
   - Worker → 큐에서 작업 가져오기 → 실행 → 결과 저장
   - API → 결과 조회 (폴링 또는 WebSocket)
3. **Adapter 패턴**: 인터페이스는 동일, 구현은 다름 (Memory vs Redis)
4. **장점**: 확장성, 비동기 처리, 독립적인 Worker 프로세스

---

## ❓ 자주 묻는 질문

### Q1: Worker는 언제 실행되나요?
**A**: 별도 프로세스로 계속 실행됩니다. `python -m app.workers.judge_worker` 명령으로 시작.

### Q2: 큐가 꽉 차면?
**A**: Redis는 메모리 기반이므로, 메모리 부족 시 에러 발생. 모니터링 필요.

### Q3: Worker가 죽으면?
**A**: 다른 Worker가 작업을 가져가거나, 재시작 시 남은 작업 처리. 결과는 Redis에 저장되어 있음.

### Q4: 결과는 언제까지 보관?
**A**: Redis TTL 설정 (예: 1시간). 이후 자동 삭제.

### Q5: 동시에 여러 Worker 실행 가능?
**A**: 네! Redis List는 여러 Worker가 동시에 BRPOP해도 안전하게 처리됩니다.

