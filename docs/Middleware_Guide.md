# Middleware 가이드

## 📋 목차

1. [개요](#개요)
2. [Middleware vs 가드레일](#middleware-vs-가드레일)
3. [파일 구조](#파일-구조)
4. [구성 요소](#구성-요소)
5. [사용 방법](#사용-방법)
6. [설정](#설정)
7. [리팩토링 및 개선 사항](#리팩토링-및-개선-사항)
8. [적용 전략](#적용-전략)
9. [State 관리](#state-관리)
10. [연동성 체크리스트](#연동성-체크리스트)

---

## 개요

Middleware는 LLM 호출 전후의 **기술적 처리**를 담당하는 모듈입니다. Rate Limiting, Retry, Logging 등의 기능을 제공하여 안정성과 모니터링을 향상시킵니다.

### 주요 기능

- ✅ **Rate Limiting**: LLM 호출 빈도 제한 (비용 절감)
- ✅ **Retry**: 에러 발생 시 자동 재시도 (안정성)
- ✅ **Logging**: 실행 로깅 (모니터링)

---

## Middleware vs 가드레일

### ✅ 별도의 개념입니다

#### 1. Middleware (기술적 처리)

**위치**: `app/domain/langgraph/middleware/`

**역할**: LLM 호출 전후의 **기술적 처리**

**구성 요소**:
- ✅ **Rate Limiting Middleware**: LLM 호출 빈도 제한 (비용 절감)
- ✅ **Retry Middleware**: 에러 발생 시 자동 재시도 (안정성)
- ✅ **Logging Middleware**: 실행 로깅 (모니터링)

**특징**:
- 모든 LLM 호출에 공통 적용
- 기술적 문제 해결 (Rate Limit, 네트워크 에러, 타임아웃 등)
- 비즈니스 로직과 무관

#### 2. 가드레일 (Guardrail) - 비즈니스 로직 검사

**위치**: `app/domain/langgraph/nodes/intent_analyzer.py`

**역할**: 사용자 요청의 **비즈니스 로직 검사**

**검사 항목**:
- ✅ **부적절한 요청 차단**: 시스템 조작 시도, 정책 위반
- ✅ **Off-Topic 질문 차단**: 코딩과 무관한 질문 (예: 점심 메뉴 추천)
- ✅ **제출 의도 확인**: 사용자가 최종 제출을 원하는지 확인
- ✅ **정책 준수 확인**: 테스트 정책에 맞는 요청인지 확인

**특징**:
- Intent Analyzer 노드에서만 수행
- LLM 기반 프롬프트 검사
- 비즈니스 정책과 직접 관련

### 실행 순서

```
사용자 요청
    ↓
[Middleware] Rate Limiting 체크 (기술적)
    ↓
[Middleware] Retry 로직 (기술적)
    ↓
[Middleware] Logging (기술적)
    ↓
[가드레일] Intent Analyzer에서 비즈니스 로직 검사
    ↓
[Writer] 동적 시스템 프롬프트 적용 (가드레일 결과 반영)
```

### 비교표

| 구분 | Middleware | 가드레일 (Guardrail) |
|------|-----------|---------------------|
| **목적** | 기술적 처리 | 비즈니스 로직 검사 |
| **위치** | `app/domain/langgraph/middleware/` | `app/domain/langgraph/nodes/intent_analyzer.py` |
| **적용 범위** | 모든 LLM 호출 | Intent Analyzer 노드만 |
| **처리 내용** | Rate Limiting, Retry, Logging | 부적절한 요청 차단, 제출 의도 확인 |
| **의존성** | LLM 호출 전후 | LLM 기반 검사 (비즈니스 로직) |
| **설정** | `config.py`의 `MIDDLEWARE_*` 설정 | 프롬프트 템플릿 (`INTENT_ANALYSIS_SYSTEM_PROMPT`) |
| **결과** | 기술적 에러 처리 | `is_guardrail_failed`, `guardrail_message` |

---

## 파일 구조

```
app/domain/langgraph/middleware/
├── __init__.py              # Middleware 모듈 export
├── factory.py               # Factory 함수 (공통 생성)
├── rate_limiting.py         # Rate Limiting Middleware
├── retry.py                 # Retry Middleware
├── logging.py               # Logging Middleware
└── example_usage.py         # 사용 예시 (참고용)
```

### Import 구조

#### `__init__.py`

```python
from app.domain.langgraph.middleware.rate_limiting import RateLimitingMiddleware
from app.domain.langgraph.middleware.retry import RetryMiddleware
from app.domain.langgraph.middleware.logging import LoggingMiddleware
from app.domain.langgraph.middleware.factory import (
    create_middleware_stack,
    wrap_chain_with_middleware
)

__all__ = [
    "RateLimitingMiddleware",
    "RetryMiddleware",
    "LoggingMiddleware",
    "create_middleware_stack",
    "wrap_chain_with_middleware",
]
```

---

## 구성 요소

### 1. Rate Limiting Middleware

**목적**: LLM 호출 빈도 제한 (비용 절감)

**기능**:
- 주어진 기간 내 최대 호출 횟수 제한
- Rate Limit 초과 시 자동 대기
- 키 기반 제한 지원 (선택사항)

**사용 예시**:
```python
rate_limiter = RateLimitingMiddleware(
    max_calls=15,      # 60초에 15회 제한
    period=60.0
)
```

### 2. Retry Middleware

**목적**: 에러 발생 시 자동 재시도 (안정성)

**기능**:
- Rate Limit, Timeout 등 일시적 에러 자동 재시도
- Exponential/Linear/Fixed 백오프 전략
- 최대 재시도 횟수 제한

**사용 예시**:
```python
retry_middleware = RetryMiddleware(
    max_retries=3,
    initial_delay=1.0,
    max_delay=60.0,
    backoff_strategy="exponential"  # exponential, linear, fixed
)
```

### 3. Logging Middleware

**목적**: 실행 로깅 (모니터링)

**기능**:
- 입력/출력 로깅
- 실행 시간 측정
- 에러 로깅

**사용 예시**:
```python
logging_middleware = LoggingMiddleware(
    log_level=logging.INFO,
    log_input=True,
    log_output=True,
    log_timing=True
)
```

---

## 사용 방법

### 권장 방식: Factory 함수 사용

```python
from app.domain.langgraph.middleware import wrap_chain_with_middleware

# 기본 Chain 구성
_base_chain = (
    RunnableLambda(prepare_input)
    | prompt_template
    | llm
    | RunnableLambda(process_output)
)

# Middleware 적용 (한 줄로 간단하게)
chain = wrap_chain_with_middleware(
    _base_chain,
    name="Chain Name"
)
```

### 적용 순서

Middleware는 다음 순서로 적용됩니다:

1. **Rate Limiting** (최외곽)
2. **Retry**
3. **Logging** (최내곽)
4. **Chain**

이 순서는 모든 노드에서 일관되게 유지됩니다.

### 실제 사용 예시

#### Intent Analyzer 노드

```python
# app/domain/langgraph/nodes/intent_analyzer.py
from app.domain.langgraph.middleware import wrap_chain_with_middleware

# 기본 Chain 구성
_base_intent_analysis_chain = (
    RunnableLambda(prepare_input)
    | intent_analysis_prompt
    | structured_llm
    | RunnableLambda(process_output)
)

# Middleware 적용
intent_analysis_chain = wrap_chain_with_middleware(
    _base_intent_analysis_chain,
    name="Intent Analyzer"
)
```

#### Writer 노드

```python
# app/domain/langgraph/nodes/writer.py
from app.domain.langgraph.middleware import wrap_chain_with_middleware

def get_writer_chain():
    # 기본 Chain 구성
    _base_writer_chain = (
        RunnableLambda(prepare_writer_input)
        | RunnableLambda(format_writer_messages)
        | _writer_llm
        | RunnableLambda(lambda x: x.content if hasattr(x, 'content') else str(x))
    )
    
    # Middleware 적용
    _writer_chain = wrap_chain_with_middleware(
        _base_writer_chain,
        name="Writer LLM"
    )
    
    return _writer_chain
```

---

## 설정

### 환경 변수 설정

`app/core/config.py`에서 Middleware 설정을 관리합니다:

```python
# Middleware 설정
MIDDLEWARE_RATE_LIMIT_MAX_CALLS: int = 15  # Rate limit 최대 호출 횟수
MIDDLEWARE_RATE_LIMIT_PERIOD: float = 60.0  # Rate limit 기간 (초)
MIDDLEWARE_RETRY_MAX_RETRIES: int = 3  # 최대 재시도 횟수
MIDDLEWARE_RETRY_INITIAL_DELAY: float = 1.0  # 초기 대기 시간 (초)
MIDDLEWARE_RETRY_MAX_DELAY: float = 60.0  # 최대 대기 시간 (초)
MIDDLEWARE_RETRY_BACKOFF_STRATEGY: str = "exponential"  # 백오프 전략
MIDDLEWARE_LOGGING_ENABLED: bool = True  # Logging Middleware 활성화 여부
```

### 설정 매핑

| 설정 | RateLimitingMiddleware | RetryMiddleware | LoggingMiddleware |
|------|----------------------|-----------------|-------------------|
| `MIDDLEWARE_RATE_LIMIT_MAX_CALLS` | ✅ `max_calls` | - | - |
| `MIDDLEWARE_RATE_LIMIT_PERIOD` | ✅ `period` | - | - |
| `MIDDLEWARE_RETRY_MAX_RETRIES` | - | ✅ `max_retries` | - |
| `MIDDLEWARE_RETRY_INITIAL_DELAY` | - | ✅ `initial_delay` | - |
| `MIDDLEWARE_RETRY_MAX_DELAY` | - | ✅ `max_delay` | - |
| `MIDDLEWARE_RETRY_BACKOFF_STRATEGY` | - | ✅ `backoff_strategy` | - |
| `MIDDLEWARE_LOGGING_ENABLED` | - | - | ✅ `log_level` (조건부) |

---

## 리팩토링 및 개선 사항

### 개선 전후 비교

#### 이전 방식 (중복 코드)

```python
# intent_analyzer.py (33줄)
_rate_limiter = RateLimitingMiddleware(
    max_calls=settings.MIDDLEWARE_RATE_LIMIT_MAX_CALLS,
    period=settings.MIDDLEWARE_RATE_LIMIT_PERIOD
)
_retry_middleware = RetryMiddleware(
    max_retries=settings.MIDDLEWARE_RETRY_MAX_RETRIES,
    initial_delay=settings.MIDDLEWARE_RETRY_INITIAL_DELAY,
    max_delay=settings.MIDDLEWARE_RETRY_MAX_DELAY,
    backoff_strategy=settings.MIDDLEWARE_RETRY_BACKOFF_STRATEGY
)
_logging_middleware = LoggingMiddleware(
    log_level=logging.INFO if settings.MIDDLEWARE_LOGGING_ENABLED else logging.DEBUG,
    log_input=True,
    log_output=True,
    log_timing=True
)

intent_analysis_chain = _rate_limiter.wrap(
    _retry_middleware.wrap(
        _logging_middleware.wrap(
            _base_intent_analysis_chain,
            name="Intent Analyzer"
        )
    )
)
```

#### 개선 후 (Factory 함수 사용)

```python
# intent_analyzer.py (3줄)
from app.domain.langgraph.middleware import wrap_chain_with_middleware

intent_analysis_chain = wrap_chain_with_middleware(
    _base_intent_analysis_chain,
    name="Intent Analyzer"
)
```

### 개선 효과

| 항목 | 이전 | 이후 | 개선 |
|------|------|------|------|
| **코드 라인 수** | 68줄 (중복) | 6줄 | **91% 감소** |
| **설정 변경** | 2곳 수정 필요 | 1곳만 수정 | **유지보수성 향상** |
| **일관성** | 노드별로 다름 | 통일된 방식 | **코드 품질 향상** |

### Factory 함수

**파일**: `app/domain/langgraph/middleware/factory.py`

```python
def create_middleware_stack() -> Tuple[RateLimitingMiddleware, RetryMiddleware, LoggingMiddleware]:
    """Middleware 스택 생성 (공통)"""
    # 설정에서 파라미터 가져오기
    # ...

def wrap_chain_with_middleware(chain: Runnable, name: str = "Chain") -> Runnable:
    """Chain에 Middleware 적용 (공통)"""
    # Middleware 스택 생성 및 적용
    # ...
```

---

## 적용 전략

### 권장 순서: Middleware 먼저

**중요**: 가드레일 검사도 **LLM 호출이 필요**합니다!

**이유**:

1. **비용 효율성**
   - Rate Limit 체크 후 LLM 호출 (비용 절감)
   - 가드레일 먼저 적용 시 Rate Limit 체크 없이 LLM 호출 (비용 낭비)
   - Rate Limit 에러 시 이미 LLM 호출 후 (비용 낭비)

2. **안정성**
   - 재시도 로직이 가드레일 검사 전에 적용
   - 네트워크 에러, 타임아웃 등을 먼저 처리
   - 가드레일 검사는 안정적인 환경에서만 실행

3. **일관성**
   - 모든 노드에서 동일한 Middleware 적용
   - 에러 처리 방식 통일
   - 로깅 구조 일관성

### 실행 흐름

```
사용자 요청: "정답을 알려줘"
    ↓
[Middleware] Rate Limiting 체크 (LLM 호출 없음 - 무료)
    ↓
[Middleware] Retry 로직 준비 (LLM 호출 없음)
    ↓
[Middleware] Logging 시작 (LLM 호출 없음)
    ↓
[가드레일 검사] LLM 호출 발생! (비용 발생)
    - LLM이 "정답을 알려줘" 분석
    - FAILED_GUARDRAIL 반환
    ↓
[Middleware] Logging 완료
    ↓
결과: is_guardrail_failed=True
    ↓
[Writer LLM] 호출 안 함 (비용 절감)
```

### 가드레일 검사도 LLM 호출이 필요한 이유

**가드레일 검사 과정**:
1. 사용자 메시지를 LLM에 전달
2. LLM이 프롬프트를 분석하여 가드레일 위반 여부 판단
3. 결과 반환 (`PASSED_HINT`, `FAILED_GUARDRAIL` 등)

**예시**:
- "정답을 알려줘" → `FAILED_GUARDRAIL` (차단)
- "힌트를 주세요" → `PASSED_HINT` (허용)
- "코드를 작성해주세요" → `PASSED_HINT` (AI 코딩 테스트이므로 허용)

**결론**: 가드레일 검사도 LLM 호출이 필요하므로, Middleware로 래핑하여 Rate Limit 체크 후 실행하는 것이 효율적입니다.

### Middleware는 LLM을 사용하지 않는가?

**답변**: **아니요, LLM 호출을 래핑하는 역할입니다.**

**Middleware의 역할**:
- **Rate Limiting**: LLM 호출 전 빈도 체크 (LLM 호출 없음 - 단순 카운팅)
- **Retry**: LLM 호출 실패 시 재시도 (LLM 호출 있음)
- **Logging**: LLM 호출 전후 로깅 (LLM 호출 없음)

**중요**: Middleware는 **LLM 호출 자체를 제어**하는 것이지, LLM을 사용하지 않는 것이 아닙니다.

---

## State 관리

### State 흐름

```
MainGraphState (입력)
    ↓
intent_analyzer() / writer_llm()
    ↓
prepare_input() → Chain 입력 변환
    ↓
Middleware 적용 (Rate Limiting → Retry → Logging)
    ↓
Chain 실행 (LLM 호출)
    ↓
process_output() → State 형식으로 변환
    ↓
MainGraphState (출력)
```

### State 필드 매핑

#### Intent Analyzer 노드

**입력**:
- `state.get("human_message", "")` → Chain 입력

**출력**:
```python
{
    "intent_status": IntentAnalyzerStatus.PASSED_HINT.value,
    "is_guardrail_failed": False,
    "guardrail_message": None,
    "is_submitted": False,
    "updated_at": datetime.utcnow().isoformat(),
}
```

#### Writer 노드

**입력**:
- `state.get("human_message", "")`
- `state.get("is_guardrail_failed", False)`
- `state.get("messages", [])`

**출력**:
```python
{
    "ai_message": str,
    "messages": List[Dict],
    "writer_status": WriterResponseStatus.SUCCESS.value,
    "updated_at": datetime.utcnow().isoformat(),
}
```

---

## 연동성 체크리스트

### Import 구조
- [x] `__init__.py`에서 모든 Middleware export
- [x] 노드에서 올바른 import 경로 사용
- [x] 순환 참조 없음
- [x] Factory 함수 export

### Parameter Mapping
- [x] 설정 → RateLimitingMiddleware 매핑 정확
- [x] 설정 → RetryMiddleware 매핑 정확
- [x] 설정 → LoggingMiddleware 매핑 정확
- [x] 모든 설정이 사용됨

### State 관리
- [x] 입력 State 필드 올바르게 추출
- [x] 출력 State 형식 일관성
- [x] State 필드 타입 일치

### 코드 일관성
- [x] Middleware 적용 순서 일관됨
- [x] Factory 함수 사용 (중복 코드 제거)
- [x] Import 위치 통일 (모듈 상단)

---

## 오버엔지니어링 분석

### ✅ 적절한 엔지니어링

**현재 적용**:
- ✅ Runnable & Chain: 코드 가독성 향상 (필수)
- ✅ LangSmith Tracing: 디버깅 용이성 (선택, State 제어)
- ✅ Middleware: Rate Limiting, 재시도 자동화 (필수)
- ✅ 동적 시스템 프롬프트: Role 기반 맞춤형 답변 (필수)

**판단**: ✅ **적절한 엔지니어링**

### ❌ 오버엔지니어링

**불필요한 적용**:
- ❌ Tools: Judge0 직접 연동이 더 효율적
- ❌ Agents: 고정된 평가 플로우가 더 적합
- ❌ Multi-Agent: LangGraph로 병렬 처리 가능

**판단**: ❌ **오버엔지니어링** (적용하지 않음)

---

## 향후 확장

### 추가 Middleware가 필요한 경우

**새로운 방식** (Factory 함수 사용):
- `factory.py`만 수정하면 모든 노드에 자동 적용

```python
# factory.py만 수정
def create_middleware_stack():
    # 새로운 Middleware 추가
    new_middleware = NewMiddleware(...)
    return rate_limiter, retry_middleware, logging_middleware, new_middleware
```

---

## 관련 문서

- `app/domain/langgraph/middleware/factory.py`: Factory 함수 구현
- `app/domain/langgraph/middleware/example_usage.py`: 사용 예시
- `app/core/config.py`: 설정 관리
- `docs/Runnable_Chain_Guide.md`: Runnable & Chain 가이드
- `docs/LangSmith_Guide.md`: LangSmith Tracing 가이드

---

## 요약

### ✅ Middleware는 별도의 개념입니다

1. **Middleware**: 
   - 로깅, 오류 처리, Rate Limiting 등 **기술적 처리**를 담당
   - 모든 LLM 호출에 공통 적용

2. **가드레일 (Guardrail)**:
   - 비즈니스 정책 검사 (부적절한 요청 차단 등)
   - Intent Analyzer 노드에서만 수행
   - 별도로 설정 및 관리

### 🎯 권장 사용법

```python
# ✅ 권장: Factory 함수 사용
from app.domain.langgraph.middleware import wrap_chain_with_middleware

chain = wrap_chain_with_middleware(
    base_chain,
    name="Chain Name"
)
```

### 📊 개선 효과

- **코드 중복**: 91% 감소 (68줄 → 6줄)
- **유지보수성**: 설정 변경 시 한 곳만 수정
- **일관성**: 모든 노드에서 동일한 방식 적용

