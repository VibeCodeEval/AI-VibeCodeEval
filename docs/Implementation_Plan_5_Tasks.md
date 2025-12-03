# 5개 작업 구현 계획

## 📋 목차

1. [큐 어댑터 (judge_queue 추상화)](#1-큐-어댑터-judge_queue-추상화)
2. [언어별 실행 (컨테이너 빌드/실행)](#2-언어별-실행-컨테이너-빌드실행)
3. [실행 리포팅 (이벤트 발행)](#3-실행-리포팅-이벤트-발행)
4. [성능 집계 (n회 중앙값 / peak RSS / LOC)](#4-성능-집계-n회-중앙값--peak-rss--loc)
5. [대화 저장 (prompt_sessions/messages)](#5-대화-저장-prompt_sessionsmessages)

---

## 1. 큐 어댑터 (judge_queue 추상화)

### 📌 목표
- 메모리 기반 큐 → Redis 기반 큐로 추상화
- Adapter 패턴으로 구현하여 향후 다른 큐 시스템으로 교체 가능하도록

### 🔍 현재 상태
- Judge0 API 직접 호출 (`app/domain/langgraph/nodes/holistic_evaluator/performance.py`)
- 큐 시스템 없음
- TODO 주석으로 "Judge0 API 연동" 표시만 있음

### 📐 설계

#### 1.1 인터페이스 정의
```python
# app/domain/queue/adapters/base.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class JudgeTask:
    """코드 실행 태스크"""
    task_id: str
    code: str
    language: str
    test_cases: list
    timeout: int = 5
    memory_limit: int = 128  # MB
    meta: Optional[Dict[str, Any]] = None

@dataclass
class JudgeResult:
    """실행 결과"""
    task_id: str
    status: str  # "success", "timeout", "error", "memory_limit"
    output: str
    error: Optional[str]
    execution_time: float  # seconds
    memory_used: int  # bytes
    exit_code: int

class QueueAdapter(ABC):
    """큐 어댑터 인터페이스"""
    
    @abstractmethod
    async def enqueue(self, task: JudgeTask) -> str:
        """태스크를 큐에 추가"""
        pass
    
    @abstractmethod
    async def dequeue(self) -> Optional[JudgeTask]:
        """큐에서 태스크를 가져옴"""
        pass
    
    @abstractmethod
    async def get_result(self, task_id: str) -> Optional[JudgeResult]:
        """실행 결과 조회"""
        pass
    
    @abstractmethod
    async def get_status(self, task_id: str) -> str:
        """태스크 상태 조회 (pending, processing, completed, failed)"""
        pass
```

#### 1.2 메모리 어댑터 (개발/테스트용)
```python
# app/domain/queue/adapters/memory.py
from typing import Dict, Optional
from collections import deque
import asyncio

class MemoryQueueAdapter(QueueAdapter):
    """메모리 기반 큐 (개발/테스트용)"""
    
    def __init__(self):
        self.queue: deque = deque()
        self.results: Dict[str, JudgeResult] = {}
        self.status: Dict[str, str] = {}
        self.lock = asyncio.Lock()
    
    async def enqueue(self, task: JudgeTask) -> str:
        async with self.lock:
            self.queue.append(task)
            self.status[task.task_id] = "pending"
        return task.task_id
    
    async def dequeue(self) -> Optional[JudgeTask]:
        async with self.lock:
            if self.queue:
                task = self.queue.popleft()
                self.status[task.task_id] = "processing"
                return task
        return None
    
    async def get_result(self, task_id: str) -> Optional[JudgeResult]:
        return self.results.get(task_id)
    
    async def get_status(self, task_id: str) -> str:
        return self.status.get(task_id, "unknown")
```

#### 1.3 Redis 어댑터 (프로덕션용)
```python
# app/domain/queue/adapters/redis.py
import json
from typing import Optional
from app.infrastructure.cache.redis_client import RedisClient

class RedisQueueAdapter(QueueAdapter):
    """Redis 기반 큐 (프로덕션용)"""
    
    def __init__(self, redis: RedisClient):
        self.redis = redis
        self.queue_key = "judge_queue:pending"
        self.result_prefix = "judge_result:"
        self.status_prefix = "judge_status:"
    
    async def enqueue(self, task: JudgeTask) -> str:
        """Redis List에 태스크 추가"""
        task_json = json.dumps({
            "task_id": task.task_id,
            "code": task.code,
            "language": task.language,
            "test_cases": task.test_cases,
            "timeout": task.timeout,
            "memory_limit": task.memory_limit,
            "meta": task.meta or {}
        })
        await self.redis.client.lpush(self.queue_key, task_json)
        await self.redis.client.set(
            f"{self.status_prefix}{task.task_id}",
            "pending",
            ex=3600  # 1시간 TTL
        )
        return task.task_id
    
    async def dequeue(self) -> Optional[JudgeTask]:
        """Redis List에서 태스크 가져오기 (BLPOP)"""
        result = await self.redis.client.brpop(self.queue_key, timeout=1)
        if result:
            _, task_json = result
            task_data = json.loads(task_json)
            task = JudgeTask(**task_data)
            await self.redis.client.set(
                f"{self.status_prefix}{task.task_id}",
                "processing",
                ex=3600
            )
            return task
        return None
    
    async def get_result(self, task_id: str) -> Optional[JudgeResult]:
        """Redis에서 결과 조회"""
        result_json = await self.redis.client.get(f"{self.result_prefix}{task_id}")
        if result_json:
            result_data = json.loads(result_json)
            return JudgeResult(**result_data)
        return None
    
    async def get_status(self, task_id: str) -> str:
        """Redis에서 상태 조회"""
        status = await self.redis.client.get(f"{self.status_prefix}{task_id}")
        return status.decode() if status else "unknown"
```

#### 1.4 팩토리 패턴
```python
# app/domain/queue/factory.py
from app.core.config import settings
from app.infrastructure.cache import redis_client
from app.domain.queue.adapters.base import QueueAdapter
from app.domain.queue.adapters.memory import MemoryQueueAdapter
from app.domain.queue.adapters.redis import RedisQueueAdapter

def create_queue_adapter() -> QueueAdapter:
    """환경에 따라 적절한 어댑터 생성"""
    if settings.USE_REDIS_QUEUE:
        return RedisQueueAdapter(redis_client)
    else:
        return MemoryQueueAdapter()
```

### 📁 파일 구조
```
app/domain/queue/
├── __init__.py
├── adapters/
│   ├── __init__.py
│   ├── base.py          # 인터페이스
│   ├── memory.py        # 메모리 구현
│   └── redis.py         # Redis 구현
├── factory.py           # 팩토리
└── service.py          # 큐 서비스 (Worker)
```

### ✅ 구현 단계
1. [ ] 인터페이스 정의 (`base.py`)
2. [ ] 메모리 어댑터 구현 (`memory.py`)
3. [ ] Redis 어댑터 구현 (`redis.py`)
4. [ ] 팩토리 패턴 구현 (`factory.py`)
5. [ ] 테스트 코드 작성
6. [ ] 기존 Judge0 호출 코드를 큐 시스템으로 교체

---

## 2. 언어별 실행 (컨테이너 빌드/실행)

### 📌 목표
- 각 프로그래밍 언어별로 Docker 컨테이너 빌드/실행
- Runner 이미지와 Dockerfile 생성
- Judge0 대신 자체 실행 환경 구축

### 🔍 현재 상태
- Judge0 API 설정만 있음 (`JUDGE0_API_URL`)
- 실제 연동 코드 없음 (TODO 주석)
- 컨테이너 실행 시스템 없음

### 📐 설계

#### 2.1 Runner 이미지 구조
```
runners/
├── python/
│   ├── Dockerfile
│   └── run.sh
├── java/
│   ├── Dockerfile
│   └── run.sh
├── cpp/
│   ├── Dockerfile
│   └── run.sh
└── javascript/
    ├── Dockerfile
    └── run.sh
```

#### 2.2 Python Runner 예시
```dockerfile
# runners/python/Dockerfile
FROM python:3.11-slim

# 보안: 비특권 사용자
RUN useradd -m -u 1000 runner && \
    mkdir -p /app && \
    chown -R runner:runner /app

WORKDIR /app

# 실행 스크립트
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh

USER runner

ENTRYPOINT ["/app/run.sh"]
```

```bash
#!/bin/bash
# runners/python/run.sh
set -e

# 입력 파일 읽기
CODE_FILE="/app/code.py"
INPUT_FILE="/app/input.txt"
OUTPUT_FILE="/app/output.txt"
ERROR_FILE="/app/error.txt"
TIMEOUT=${TIMEOUT:-5}
MEMORY_LIMIT=${MEMORY_LIMIT:-128}  # MB

# 메모리 제한 설정 (ulimit)
ulimit -v $((MEMORY_LIMIT * 1024))  # KB

# Python 실행 (타임아웃 적용)
timeout ${TIMEOUT}s python3 "$CODE_FILE" < "$INPUT_FILE" > "$OUTPUT_FILE" 2> "$ERROR_FILE" || {
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 124 ]; then
        echo "TIMEOUT" > "$ERROR_FILE"
    fi
    exit $EXIT_CODE
}
```

#### 2.3 실행 서비스
```python
# app/infrastructure/execution/runner.py
import docker
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path

class CodeRunner:
    """코드 실행 서비스"""
    
    def __init__(self):
        self.client = docker.from_env()
        self.image_prefix = "ai-vibe-runner"
    
    async def run_code(
        self,
        code: str,
        language: str,
        test_cases: list,
        timeout: int = 5,
        memory_limit: int = 128
    ) -> Dict[str, Any]:
        """코드 실행"""
        image_name = f"{self.image_prefix}:{language}"
        
        # 컨테이너 실행
        container = self.client.containers.run(
            image=image_name,
            command=["/app/run.sh"],
            volumes={
                str(Path("/tmp/code")): {"bind": "/app", "mode": "rw"}
            },
            environment={
                "TIMEOUT": str(timeout),
                "MEMORY_LIMIT": str(memory_limit)
            },
            mem_limit=f"{memory_limit}m",
            cpu_period=100000,
            cpu_quota=50000,  # 50% CPU
            network_disabled=True,  # 네트워크 비활성화
            remove=True,  # 실행 후 삭제
            detach=True
        )
        
        # 결과 대기
        result = container.wait(timeout=timeout + 5)
        
        # 출력 읽기
        logs = container.logs()
        
        return {
            "exit_code": result["StatusCode"],
            "output": logs.decode("utf-8"),
            "memory_used": result.get("Memory", 0)
        }
```

### 📁 파일 구조
```
runners/
├── python/
│   ├── Dockerfile
│   └── run.sh
├── java/
│   ├── Dockerfile
│   └── run.sh
├── cpp/
│   ├── Dockerfile
│   └── run.sh
└── javascript/
    ├── Dockerfile
    └── run.sh

app/infrastructure/execution/
├── __init__.py
├── runner.py          # 실행 서비스
└── builder.py         # 이미지 빌드
```

### ✅ 구현 단계
1. [ ] 각 언어별 Dockerfile 작성
2. [ ] 실행 스크립트 작성 (run.sh)
3. [ ] 이미지 빌드 스크립트 작성
4. [ ] CodeRunner 서비스 구현
5. [ ] 보안 설정 (네트워크 비활성화, 리소스 제한)
6. [ ] 테스트 코드 작성

---

## 3. 실행 리포팅 (이벤트 발행)

### 📌 목표
- 코드 실행 과정의 이벤트 발행 (build, case_end, summary, score)
- 이벤트 프로토콜 정의
- 이벤트 버스 구현

### 🔍 현재 상태
- CallbackService 존재 (Spring Boot 콜백)
- 이벤트 시스템 없음
- 이벤트 프로토콜 없음

### 📐 설계

#### 3.1 이벤트 프로토콜
```python
# app/domain/events/protocol.py
from dataclasses import dataclass
from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime

class EventType(str, Enum):
    BUILD = "build"
    CASE_END = "case_end"
    SUMMARY = "summary"
    SCORE = "score"

@dataclass
class BaseEvent:
    """기본 이벤트"""
    event_type: EventType
    session_id: str
    task_id: str
    timestamp: datetime
    meta: Optional[Dict[str, Any]] = None

@dataclass
class BuildEvent(BaseEvent):
    """빌드 시작 이벤트"""
    language: str
    code_length: int
    test_cases_count: int

@dataclass
class CaseEndEvent(BaseEvent):
    """테스트 케이스 종료 이벤트"""
    case_index: int
    case_name: str
    passed: bool
    execution_time: float
    memory_used: int
    output: str
    error: Optional[str] = None

@dataclass
class SummaryEvent(BaseEvent):
    """실행 요약 이벤트"""
    total_cases: int
    passed_cases: int
    failed_cases: int
    total_execution_time: float
    peak_memory: int
    median_execution_time: float

@dataclass
class ScoreEvent(BaseEvent):
    """점수 계산 이벤트"""
    correctness_score: float
    performance_score: float
    total_score: float
    breakdown: Dict[str, float]
```

#### 3.2 이벤트 버스
```python
# app/domain/events/bus.py
from typing import List, Callable, Awaitable
from app.domain.events.protocol import BaseEvent

class EventBus:
    """이벤트 버스"""
    
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
    
    def subscribe(self, event_type: str, handler: Callable[[BaseEvent], Awaitable[None]]):
        """이벤트 구독"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
    
    async def publish(self, event: BaseEvent):
        """이벤트 발행"""
        handlers = self.subscribers.get(event.event_type.value, [])
        for handler in handlers:
            await handler(event)
```

#### 3.3 이벤트 핸들러
```python
# app/application/services/event_handlers.py
from app.domain.events.protocol import BaseEvent, BuildEvent, CaseEndEvent, SummaryEvent, ScoreEvent
from app.application.services.callback_service import CallbackService

class EventHandlers:
    """이벤트 핸들러"""
    
    def __init__(self, callback_service: CallbackService):
        self.callback_service = callback_service
    
    async def handle_build(self, event: BuildEvent):
        """빌드 이벤트 처리"""
        await self.callback_service.send_callback({
            "type": "build",
            "session_id": event.session_id,
            "task_id": event.task_id,
            "language": event.language,
            "code_length": event.code_length,
            "test_cases_count": event.test_cases_count,
            "timestamp": event.timestamp.isoformat()
        })
    
    async def handle_case_end(self, event: CaseEndEvent):
        """케이스 종료 이벤트 처리"""
        await self.callback_service.send_callback({
            "type": "case_end",
            "session_id": event.session_id,
            "task_id": event.task_id,
            "case_index": event.case_index,
            "case_name": event.case_name,
            "passed": event.passed,
            "execution_time": event.execution_time,
            "memory_used": event.memory_used,
            "output": event.output,
            "error": event.error,
            "timestamp": event.timestamp.isoformat()
        })
    
    async def handle_summary(self, event: SummaryEvent):
        """요약 이벤트 처리"""
        await self.callback_service.send_callback({
            "type": "summary",
            "session_id": event.session_id,
            "task_id": event.task_id,
            "total_cases": event.total_cases,
            "passed_cases": event.passed_cases,
            "failed_cases": event.failed_cases,
            "total_execution_time": event.total_execution_time,
            "peak_memory": event.peak_memory,
            "median_execution_time": event.median_execution_time,
            "timestamp": event.timestamp.isoformat()
        })
    
    async def handle_score(self, event: ScoreEvent):
        """점수 이벤트 처리"""
        await self.callback_service.send_callback({
            "type": "score",
            "session_id": event.session_id,
            "task_id": event.task_id,
            "correctness_score": event.correctness_score,
            "performance_score": event.performance_score,
            "total_score": event.total_score,
            "breakdown": event.breakdown,
            "timestamp": event.timestamp.isoformat()
        })
```

### 📁 파일 구조
```
app/domain/events/
├── __init__.py
├── protocol.py        # 이벤트 프로토콜
└── bus.py            # 이벤트 버스

app/application/services/
└── event_handlers.py  # 이벤트 핸들러
```

### ✅ 구현 단계
1. [ ] 이벤트 프로토콜 정의
2. [ ] 이벤트 버스 구현
3. [ ] 이벤트 핸들러 구현
4. [ ] 코드 실행 서비스에 이벤트 발행 통합
5. [ ] 테스트 코드 작성

---

## 4. 성능 집계 (n회 중앙값 / peak RSS / LOC)

### 📌 목표
- n회 실행의 중앙값 계산
- Peak RSS (메모리 사용량) 수집
- LOC (Lines of Code) 수집
- 집계기/리포터 모듈 구현

### 🔍 현재 상태
- `eval_code_performance` 노드 존재
- LLM 기반 평가만 있음
- 실제 실행 데이터 수집 없음

### 📐 설계

#### 4.1 성능 메트릭 수집
```python
# app/domain/performance/metrics.py
from dataclasses import dataclass
from typing import List, Optional
import statistics

@dataclass
class ExecutionMetrics:
    """실행 메트릭"""
    execution_times: List[float]  # 초 단위
    memory_usages: List[int]  # bytes
    exit_codes: List[int]
    outputs: List[str]
    errors: List[Optional[str]]

@dataclass
class AggregatedMetrics:
    """집계된 메트릭"""
    median_execution_time: float
    mean_execution_time: float
    min_execution_time: float
    max_execution_time: float
    peak_memory: int  # peak RSS
    median_memory: int
    total_lines_of_code: int
    success_rate: float
    total_runs: int
```

#### 4.2 집계기
```python
# app/domain/performance/aggregator.py
from typing import List
from app.domain.performance.metrics import ExecutionMetrics, AggregatedMetrics
import statistics

class PerformanceAggregator:
    """성능 집계기"""
    
    @staticmethod
    def aggregate(metrics: ExecutionMetrics, runs: int = 5) -> AggregatedMetrics:
        """n회 실행 결과 집계"""
        if not metrics.execution_times:
            raise ValueError("No execution metrics available")
        
        # 중앙값 계산
        median_time = statistics.median(metrics.execution_times)
        mean_time = statistics.mean(metrics.execution_times)
        min_time = min(metrics.execution_times)
        max_time = max(metrics.execution_times)
        
        # Peak RSS (최대 메모리 사용량)
        peak_memory = max(metrics.memory_usages) if metrics.memory_usages else 0
        median_memory = statistics.median(metrics.memory_usages) if metrics.memory_usages else 0
        
        # LOC 계산 (코드에서)
        # TODO: 코드 파싱하여 LOC 계산
        
        # 성공률
        success_count = sum(1 for code in metrics.exit_codes if code == 0)
        success_rate = success_count / len(metrics.exit_codes) if metrics.exit_codes else 0
        
        return AggregatedMetrics(
            median_execution_time=median_time,
            mean_execution_time=mean_time,
            min_execution_time=min_time,
            max_execution_time=max_time,
            peak_memory=peak_memory,
            median_memory=median_memory,
            total_lines_of_code=0,  # TODO: LOC 계산
            success_rate=success_rate,
            total_runs=len(metrics.execution_times)
        )
```

#### 4.3 LOC 계산
```python
# app/domain/performance/loc_counter.py
import ast
from typing import List

class LOCCounter:
    """LOC (Lines of Code) 카운터"""
    
    @staticmethod
    def count_lines(code: str) -> int:
        """총 라인 수"""
        return len(code.splitlines())
    
    @staticmethod
    def count_effective_lines(code: str) -> int:
        """실제 코드 라인 수 (주석, 빈 줄 제외)"""
        lines = code.splitlines()
        effective = 0
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                effective += 1
        return effective
    
    @staticmethod
    def count_statements(code: str, language: str = "python") -> int:
        """문장 수 (AST 기반)"""
        if language == "python":
            try:
                tree = ast.parse(code)
                return len([node for node in ast.walk(tree) if isinstance(node, ast.stmt)])
            except:
                return 0
        return 0
```

#### 4.4 리포터
```python
# app/domain/performance/reporter.py
from app.domain.performance.metrics import AggregatedMetrics
from typing import Dict, Any

class PerformanceReporter:
    """성능 리포터"""
    
    @staticmethod
    def generate_report(metrics: AggregatedMetrics) -> Dict[str, Any]:
        """성능 리포트 생성"""
        return {
            "execution_time": {
                "median": metrics.median_execution_time,
                "mean": metrics.mean_execution_time,
                "min": metrics.min_execution_time,
                "max": metrics.max_execution_time,
                "unit": "seconds"
            },
            "memory": {
                "peak_rss": metrics.peak_memory,
                "median_rss": metrics.median_memory,
                "unit": "bytes"
            },
            "code_metrics": {
                "total_lines_of_code": metrics.total_lines_of_code,
                "unit": "lines"
            },
            "reliability": {
                "success_rate": metrics.success_rate,
                "total_runs": metrics.total_runs
            }
        }
```

### 📁 파일 구조
```
app/domain/performance/
├── __init__.py
├── metrics.py         # 메트릭 데이터 클래스
├── aggregator.py      # 집계기
├── loc_counter.py     # LOC 계산
└── reporter.py        # 리포터
```

### ✅ 구현 단계
1. [ ] ExecutionMetrics, AggregatedMetrics 정의
2. [ ] PerformanceAggregator 구현 (중앙값 계산)
3. [ ] LOCCounter 구현
4. [ ] PerformanceReporter 구현
5. [ ] 코드 실행 서비스에 통합
6. [ ] 테스트 코드 작성

---

## 5. 대화 저장 (prompt_sessions/messages)

### 📌 목표
- prompt_sessions와 prompt_messages 테이블에 대화 저장
- Repository와 Schema DTO 완성
- LangGraph 실행 중 자동 저장

### 🔍 현재 상태
- ✅ `PromptSession`, `PromptMessage` 모델 존재 (`app/infrastructure/persistence/models/sessions.py`)
- ✅ `SessionRepository` 존재 (`app/infrastructure/repositories/session_repository.py`)
- ❌ 실제 저장 로직 없음 (EvalService에서 호출 안 함)

### 📐 설계

#### 5.1 DTO 정의
```python
# app/presentation/schemas/session.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.infrastructure.persistence.models.enums import PromptRoleEnum

class PromptMessageDTO(BaseModel):
    """프롬프트 메시지 DTO"""
    turn: int
    role: PromptRoleEnum
    content: str
    token_count: int = 0
    meta: Optional[dict] = None

class PromptSessionDTO(BaseModel):
    """프롬프트 세션 DTO"""
    id: Optional[int] = None
    exam_id: int
    participant_id: int
    spec_id: Optional[int] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    total_tokens: int = 0
    messages: List[PromptMessageDTO] = []
```

#### 5.2 저장 서비스
```python
# app/application/services/session_storage_service.py
from typing import Dict, Any, Optional
from app.infrastructure.repositories.session_repository import SessionRepository
from app.infrastructure.persistence.models.enums import PromptRoleEnum
from app.infrastructure.persistence.session import get_db_context

class SessionStorageService:
    """세션 저장 서비스"""
    
    def __init__(self, session_repo: SessionRepository):
        self.session_repo = session_repo
    
    async def save_turn(
        self,
        session_id: str,
        turn: int,
        human_message: str,
        ai_message: str,
        token_count: int = 0,
        meta: Optional[Dict[str, Any]] = None
    ):
        """턴 저장"""
        # PostgreSQL session_id 조회 (또는 생성)
        pg_session = await self.session_repo.get_session_by_external_id(session_id)
        
        if not pg_session:
            # 세션 생성 필요 (exam_id, participant_id는 state에서 가져옴)
            # TODO: state에서 exam_id, participant_id 추출
            pass
        
        # 메시지 저장
        await self.session_repo.add_message(
            session_id=pg_session.id,
            turn=turn,
            role=PromptRoleEnum.USER,
            content=human_message,
            token_count=token_count,
            meta=meta
        )
        
        await self.session_repo.add_message(
            session_id=pg_session.id,
            turn=turn,
            role=PromptRoleEnum.ASSISTANT,
            content=ai_message,
            token_count=token_count,
            meta=meta
        )
```

#### 5.3 EvalService 통합
```python
# app/application/services/eval_service.py (수정)
async def process_message(...):
    # ... 기존 코드 ...
    
    # 대화 저장
    if result.get("ai_message"):
        async with get_db_context() as db:
            session_repo = SessionRepository(db)
            storage_service = SessionStorageService(session_repo)
            
            await storage_service.save_turn(
                session_id=session_id,
                turn=result.get("current_turn", 0),
                human_message=human_message,
                ai_message=result.get("ai_message"),
                token_count=token_summary.get("chat_tokens", {}).get("total_tokens", 0),
                meta={
                    "intent": result.get("intent_type"),
                    "is_guardrail_failed": result.get("is_guardrail_failed", False)
                }
            )
```

#### 5.4 Repository 확장
```python
# app/infrastructure/repositories/session_repository.py (추가)
async def get_session_by_external_id(self, external_id: str) -> Optional[PromptSession]:
    """외부 세션 ID로 조회 (Redis session_id -> PostgreSQL id 매핑)"""
    # Redis에서 매핑 조회 또는 직접 조회
    # TODO: external_id 매핑 테이블 또는 Redis 키 사용
    pass

async def add_message(
    self,
    session_id: int,
    turn: int,
    role: PromptRoleEnum,
    content: str,
    token_count: int = 0,
    meta: Optional[dict] = None
) -> PromptMessage:
    """메시지 추가"""
    message = PromptMessage(
        session_id=session_id,
        turn=turn,
        role=role,
        content=content,
        token_count=token_count,
        meta=meta,
        created_at=datetime.utcnow()
    )
    self.db.add(message)
    await self.db.flush()
    return message
```

### 📁 파일 구조
```
app/presentation/schemas/
└── session.py          # DTO 정의

app/application/services/
└── session_storage_service.py  # 저장 서비스
```

### ✅ 구현 단계
1. [ ] DTO 정의 (PromptSessionDTO, PromptMessageDTO)
2. [ ] SessionStorageService 구현
3. [ ] Repository 확장 (get_session_by_external_id, add_message)
4. [ ] EvalService에 저장 로직 통합
5. [ ] 테스트 코드 작성

---

## 📊 전체 구현 우선순위

### Phase 1: 기반 구축 (1-2주)
1. **큐 어댑터** (1주)
   - 인터페이스 정의
   - 메모리 어댑터 구현
   - Redis 어댑터 구현

2. **대화 저장** (1주)
   - DTO 정의
   - 저장 서비스 구현
   - EvalService 통합

### Phase 2: 실행 시스템 (2-3주)
3. **언어별 실행** (2주)
   - Dockerfile 작성
   - 실행 스크립트 작성
   - CodeRunner 서비스 구현

4. **성능 집계** (1주)
   - 메트릭 수집
   - 집계기 구현
   - LOC 계산

### Phase 3: 이벤트 시스템 (1주)
5. **실행 리포팅** (1주)
   - 이벤트 프로토콜 정의
   - 이벤트 버스 구현
   - 핸들러 구현

---

## 🔗 의존성 관계

```
큐 어댑터
  ↓
언어별 실행 → 성능 집계
  ↓
실행 리포팅
  ↓
대화 저장
```

---

## 📝 참고사항

1. **보안**: 컨테이너 실행 시 네트워크 비활성화, 리소스 제한 필수
2. **성능**: Redis 큐 사용 시 연결 풀 관리
3. **확장성**: Adapter 패턴으로 향후 다른 큐 시스템으로 교체 가능
4. **모니터링**: 이벤트 시스템으로 실행 과정 추적 가능
5. **데이터**: PostgreSQL에 영구 저장하여 분석 및 감사 가능

