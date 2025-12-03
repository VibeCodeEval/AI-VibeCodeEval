# LLM 인스턴스 관리 가이드

## 📋 질문 1: "LLM 여러번 호출"이 무슨 뜻인가?

### 현재 상황 분석

#### ❌ 문제가 되는 코드 (이전)
```python
# writer.py - 매번 새 LLM 인스턴스 생성
def create_writer_chain():
    llm = get_llm()  # ⚠️ 매번 새로 생성!
    chain = (...)
    return chain

async def writer_llm(state: MainGraphState):
    chain = create_writer_chain()  # ⚠️ 매번 호출될 때마다 새 Chain 생성
    ai_content = await chain.ainvoke(state)
```

**문제점:**
- `writer_llm()` 함수가 호출될 때마다:
  1. `create_writer_chain()` 실행
  2. `get_llm()` 실행 → **새 LLM 인스턴스 생성**
  3. Chain 생성
  4. LLM 호출

**영향:**
- LLM 인스턴스 생성 오버헤드 (미미하지만 누적 가능)
- 메모리에 불필요한 인스턴스가 쌓일 수 있음

#### ✅ 개선된 코드 (현재)
```python
# writer.py - 모듈 레벨에서 캐싱
_writer_chain = None
_writer_llm = None

def get_writer_chain():
    global _writer_chain, _writer_llm
    if _writer_chain is None:
        _writer_llm = get_llm()  # ✅ 1번만 생성
        _writer_chain = (...)
    return _writer_chain  # ✅ 재사용

async def writer_llm(state: MainGraphState):
    chain = get_writer_chain()  # ✅ 캐싱된 Chain 재사용
    ai_content = await chain.ainvoke(state)
```

**개선점:**
- 첫 호출 시에만 LLM 인스턴스 생성
- 이후 호출에서는 캐싱된 인스턴스 재사용

---

## 📋 질문 2: 싱글톤으로 하면 지속적으로 연결해서 사용한다는 뜻인가?

### ❌ 오해: "연결 유지"가 아님

**중요한 점:**
- LLM 인스턴스는 **"연결"을 유지하지 않습니다**
- 각 API 호출은 **독립적인 HTTP 요청**입니다
- 싱글톤 패턴은 **인스턴스 재사용**을 의미합니다

### ✅ 실제 의미

```python
# 싱글톤 패턴의 의미
_llm_instance = None

def get_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ChatGoogleGenerativeAI(...)  # ✅ 1번만 생성
    return _llm_instance  # ✅ 같은 인스턴스 반환

# 사용 예시
llm1 = get_llm()  # 첫 호출: 새 인스턴스 생성
llm2 = get_llm()  # 두 번째 호출: 같은 인스턴스 반환
# llm1 is llm2  # True (같은 객체)

# 각 API 호출은 여전히 독립적
response1 = await llm1.ainvoke("Hello")  # HTTP 요청 1
response2 = await llm2.ainvoke("World")  # HTTP 요청 2 (독립적)
```

**핵심:**
- ✅ **인스턴스 재사용**: 같은 설정의 LLM 객체를 재사용
- ❌ **연결 유지 아님**: 각 API 호출은 독립적인 HTTP 요청
- ✅ **메모리 절약**: 불필요한 객체 생성 방지
- ✅ **초기화 오버헤드 감소**: 설정 파싱 등 1번만 수행

---

## 📋 질문 3: 노드별로 다른 LLM 설정을 사용할 예정인데, 싱글톤이 별로인가?

### 현재 노드별 LLM 설정 분석

| 노드 | Temperature | Model | Max Tokens |
|------|-------------|-------|------------|
| **Intent Analyzer** | 0.3 | DEFAULT_LLM_MODEL | 기본값 |
| **Writer** | settings.LLM_TEMPERATURE | DEFAULT_LLM_MODEL | settings.LLM_MAX_TOKENS |
| **Turn Evaluator** | 0.1 | DEFAULT_LLM_MODEL | 기본값 |
| **Holistic Evaluator** | 0.1 | DEFAULT_LLM_MODEL | 기본값 |
| **System Nodes** | 0.3 | DEFAULT_LLM_MODEL | 기본값 |

### ⚠️ 문제점: 단일 싱글톤은 부적합

**만약 단일 싱글톤을 사용한다면:**
```python
# ❌ 잘못된 예시
_llm_instance = None

def get_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ChatGoogleGenerativeAI(temperature=0.3)  # 고정값
    return _llm_instance

# 문제: 모든 노드가 같은 temperature를 사용하게 됨
# - Intent Analyzer: 0.3 ✅
# - Turn Evaluator: 0.1이어야 하는데 0.3 사용 ❌
```

### ✅ 해결 방안: 노드별 싱글톤 (Factory Pattern)

```python
# ✅ 올바른 예시: 노드별로 다른 설정의 LLM 인스턴스 캐싱
_llm_cache = {}

def get_llm(node_name: str, temperature: float = None, model: str = None):
    """
    노드별로 다른 설정의 LLM 인스턴스 캐싱
    
    Args:
        node_name: 노드 이름 (예: "intent_analyzer", "writer", "turn_evaluator")
        temperature: 온도 설정 (노드별로 다를 수 있음)
        model: 모델 이름 (노드별로 다를 수 있음)
    
    Returns:
        캐싱된 LLM 인스턴스
    """
    # 캐시 키 생성 (노드명 + 설정 조합)
    cache_key = f"{node_name}_{temperature}_{model}"
    
    if cache_key not in _llm_cache:
        _llm_cache[cache_key] = ChatGoogleGenerativeAI(
            model=model or settings.DEFAULT_LLM_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=temperature or 0.3,
        )
    
    return _llm_cache[cache_key]

# 사용 예시
# Intent Analyzer
intent_llm = get_llm("intent_analyzer", temperature=0.3)

# Turn Evaluator
eval_llm = get_llm("turn_evaluator", temperature=0.1)

# Writer
writer_llm = get_llm("writer", temperature=settings.LLM_TEMPERATURE)
```

### 🎯 권장 구조: 노드별 모듈 레벨 캐싱 (현재 구조 유지)

**현재 구조가 이미 적합합니다:**

```python
# ✅ intent_analyzer.py - 노드별로 독립적인 캐싱
llm = get_llm()  # temperature=0.3
structured_llm = llm.with_structured_output(IntentAnalysisResult)
intent_analysis_chain = (...)

# ✅ turn_evaluator/utils.py - 노드별로 독립적인 캐싱
def get_llm():
    return ChatGoogleGenerativeAI(temperature=0.1)  # 다른 설정

# ✅ writer.py - 노드별로 독립적인 캐싱
_writer_llm = None
def get_writer_chain():
    global _writer_llm
    if _writer_llm is None:
        _writer_llm = get_llm()  # temperature=settings.LLM_TEMPERATURE
    return _writer_chain
```

**장점:**
- ✅ 각 노드가 독립적인 설정 사용 가능
- ✅ 노드별로 캐싱되어 불필요한 재생성 방지
- ✅ 코드가 명확하고 유지보수 용이

**단점:**
- ⚠️ 노드가 많아지면 메모리 사용량 증가 (하지만 미미함)

---

## 📊 최종 권장 사항

### 현재 구조 유지 (노드별 모듈 레벨 캐싱)

**이유:**
1. ✅ 노드별로 다른 설정 사용 가능
2. ✅ 각 노드 내에서 인스턴스 재사용
3. ✅ 코드가 명확하고 이해하기 쉬움
4. ✅ 메모리 사용량 증가는 미미함 (노드당 1개 인스턴스)

**현재 구조 예시:**
```python
# intent_analyzer.py
llm = get_llm()  # temperature=0.3, 모듈 레벨에서 1번만 생성
intent_analysis_chain = (...)  # 모듈 레벨에서 1번만 생성

# turn_evaluator/utils.py
def get_llm():
    return ChatGoogleGenerativeAI(temperature=0.1)  # 노드별 독립 설정

# writer.py
_writer_chain = None
_writer_llm = None
def get_writer_chain():
    global _writer_chain, _writer_llm
    if _writer_chain is None:
        _writer_llm = get_llm()  # temperature=settings.LLM_TEMPERATURE
        _writer_chain = (...)
    return _writer_chain
```

---

## 🔍 LangSmith Tracing 및 Middleware 계획

### LangSmith Tracing (6번 Node에 추가 예정)

**추가 위치:**
- `app/domain/langgraph/nodes/holistic_evaluator/flow.py` (6a)
- `app/domain/langgraph/nodes/holistic_evaluator/performance.py` (6c)
- `app/domain/langgraph/nodes/holistic_evaluator/correctness.py` (6d)

**구현 방법:**
```python
from langsmith import traceable

@traceable(name="eval_holistic_flow")
async def eval_holistic_flow(state: MainGraphState):
    # Chain 실행 시 자동으로 LangSmith에 추적
    result = await holistic_chain.ainvoke({"structured_logs": structured_logs})
    return result
```

**또는 Chain 레벨에서:**
```python
from langchain_core.runnables import RunnableConfig
from langsmith import traceable

# Chain에 LangSmith 통합
holistic_chain = (
    RunnableLambda(prepare_holistic_input)
    | RunnableLambda(format_holistic_messages)
    | structured_llm
    | RunnableLambda(process_holistic_output)
).with_config({"callbacks": [LangSmithTracer()]})
```

### Middleware 도입 (빠른 시일 내 예정)

**추가할 Middleware:**
1. **재시도 (Retry)**: Rate Limit, Timeout 시 자동 재시도
2. **Rate Limiting**: API 호출 빈도 제한
3. **로깅**: 모든 LLM 호출 로깅
4. **에러 처리**: 통일된 에러 처리

**구현 방법:**
```python
from langchain_core.runnables import RunnableLambda
from langchain_core.runnables.middleware import RunnableMiddleware

# 재시도 Middleware
class RetryMiddleware(RunnableMiddleware):
    async def ainvoke(self, input, config=None, **kwargs):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return await super().ainvoke(input, config, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

# Chain에 Middleware 적용
holistic_chain = (
    RetryMiddleware() |
    RunnableLambda(prepare_holistic_input)
    | RunnableLambda(format_holistic_messages)
    | structured_llm
    | RunnableLambda(process_holistic_output)
)
```

---

## 📝 요약

### 1. "LLM 여러번 호출"의 의미
- ❌ 문제: 매번 새 LLM 인스턴스 생성
- ✅ 해결: 모듈 레벨에서 캐싱 (현재 완료)

### 2. 싱글톤 패턴의 의미
- ❌ 오해: "연결 유지"가 아님
- ✅ 실제: 인스턴스 재사용 (같은 설정의 객체를 재사용)

### 3. 노드별 다른 LLM 설정
- ✅ 현재 구조가 적합: 노드별 모듈 레벨 캐싱
- ✅ 각 노드가 독립적인 설정 사용 가능
- ✅ 불필요한 재생성 방지

### 4. LangSmith & Middleware 계획
- ✅ LangSmith: 6번 Node에 추가 예정
- ✅ Middleware: 빠른 시일 내 도입 예정

---

**결론**: 현재 구조를 유지하되, LangSmith Tracing과 Middleware를 추가하는 것이 최적의 방안입니다.

