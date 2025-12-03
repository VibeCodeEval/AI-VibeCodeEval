# Runnable & Chain 구조 가이드

## 📋 목차

1. [개요](#개요)
2. [구현 현황](#구현-현황)
3. [구조 및 패턴](#구조-및-패턴)
4. [Tradeoff 분석](#tradeoff-분석)
5. [사용 방법](#사용-방법)
6. [향후 개선 방안](#향후-개선-방안)

---

## 개요

LangChain의 **Runnable & Chain** 구조를 도입하여 코드 가독성, 재사용성, 테스트 용이성을 향상시켰습니다.

### 핵심 개념

- **Runnable**: LangChain의 기본 실행 단위 (LLM, 프롬프트, 함수 등)
- **Chain**: 여러 Runnable을 `|` 연산자로 연결한 실행 파이프라인
- **RunnableLambda**: Python 함수를 Runnable로 변환

### 공식 문서

- **Runnable**: https://python.langchain.com/docs/expression_language/
- **Chain**: https://python.langchain.com/docs/expression_language/get_started

---

## 구현 현황

### ✅ 변경된 노드

1. **Intent Analyzer** (`app/domain/langgraph/nodes/intent_analyzer.py`)
2. **Writer LLM** (`app/domain/langgraph/nodes/writer.py`)
3. **Turn Evaluator** (`app/domain/langgraph/nodes/turn_evaluator/evaluators.py`)
4. **Holistic Evaluator** (`app/domain/langgraph/nodes/holistic_evaluator/`)
5. **System Nodes** (`app/domain/langgraph/nodes/system_nodes.py`)

### 변경 전후 비교

#### 변경 전
```python
llm = get_llm()
analyzer_llm = llm.with_structured_output(IntentAnalysisResult)
result = await analyzer_llm.ainvoke([...])
```

#### 변경 후
```python
# Chain 구성
intent_analysis_chain = (
    RunnableLambda(prepare_input)
    | intent_analysis_prompt  # ChatPromptTemplate
    | structured_llm
    | RunnableLambda(process_output)
)

# Chain 실행
result = await intent_analysis_chain.ainvoke({"human_message": human_message})
```

---

## 구조 및 패턴

### 표준 Chain 구조

```python
"""
[구조]
- 상수: 프롬프트 템플릿
- Chain 구성 함수: 평가 Chain 생성
- 내부 구현: 실제 평가 로직
- 외부 래퍼: LangSmith 추적 제어
"""
# ===== 상수 =====
SYSTEM_PROMPT = """..."""

# ===== Chain 구성 함수 =====
def prepare_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """입력 준비"""
    return {...}

def format_messages(inputs: Dict[str, Any]) -> list:
    """메시지 포맷팅"""
    return [...]

def process_output(result: Model) -> Dict[str, Any]:
    """출력 처리"""
    return {...}

# ===== Chain 생성 =====
llm = get_llm()
structured_llm = llm.with_structured_output(OutputModel)

chain = (
    RunnableLambda(prepare_input)
    | RunnableLambda(format_messages)
    | structured_llm
    | RunnableLambda(process_output)
)

# ===== 실행 =====
result = await chain.ainvoke(inputs)
```

### 주요 패턴

#### 1. 프롬프트 템플릿 사용
```python
from langchain_core.prompts import ChatPromptTemplate

intent_analysis_prompt = ChatPromptTemplate.from_messages([
    ("system", INTENT_ANALYSIS_SYSTEM_PROMPT),
    ("user", "{human_message}")
])
```

#### 2. 입력/출력 처리 분리
```python
# 입력 준비
def prepare_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
    human_message = inputs.get("human_message", "")
    return {"human_message": human_message.strip()}

# 출력 처리
def process_output(result: Model) -> Dict[str, Any]:
    return {
        "intent_status": result.status,
        "guardrail_passed": result.guardrail_passed,
    }
```

#### 3. Chain 캐싱
```python
# 모듈 레벨 캐싱 (Writer LLM)
_writer_chain = None
_writer_llm = None

def get_writer_chain():
    global _writer_chain, _writer_llm
    if _writer_chain is None:
        _writer_llm = get_llm()
        _writer_chain = create_writer_chain(_writer_llm)
    return _writer_chain
```

---

## Tradeoff 분석

### ✅ 장점

| 항목 | 설명 | 평가 |
|------|------|------|
| **가독성** | 데이터 흐름이 `\|` 연산자로 시각적으로 명확 | ✅ **대폭 개선** |
| **재사용성** | Chain을 함수로 생성하여 재사용 가능 | ✅ **대폭 개선** |
| **테스트** | 각 `RunnableLambda` 함수를 독립적으로 테스트 가능 | ✅ **대폭 개선** |
| **유지보수** | 프롬프트 중앙화, 일관된 패턴 | ✅ **대폭 개선** |

### ⚠️ 단점

| 항목 | 설명 | 완화 방안 |
|------|------|----------|
| **성능** | 5-10ms 오버헤드 (RunnableLambda 추가 호출) | ✅ Chain 캐싱 |
| **에러 추적** | Chain 내부 어느 단계에서 에러 발생했는지 추적 어려움 | ✅ 단계별 로깅 추가 |
| **메모리** | Chain과 LLM 인스턴스가 메모리에 상주 | ⚠️ LLM 싱글톤 패턴 |
| **학습 곡선** | LangChain 개념 학습 필요 | ⚠️ 문서화 |

### 최종 평가

**장점 > 단점** ✅
- 코드 가독성과 유지보수성이 중요한 경우
- 테스트 커버리지를 높여야 하는 경우
- 프롬프트 관리가 중요한 경우
- **현재 프로젝트는 이 경우에 해당**

---

## 사용 방법

### 1. 기본 Chain 생성

```python
from langchain_core.runnables import RunnableLambda
from langchain_core.prompts import ChatPromptTemplate

# 프롬프트 템플릿
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("user", "{input}")
])

# Chain 구성
chain = (
    RunnableLambda(lambda x: {"input": x["message"]})
    | prompt
    | llm
    | RunnableLambda(lambda x: x.content)
)

# 실행
result = await chain.ainvoke({"message": "Hello"})
```

### 2. 구조화된 출력 사용

```python
from pydantic import BaseModel

class OutputModel(BaseModel):
    status: str
    score: float

# Chain 구성
structured_llm = llm.with_structured_output(OutputModel)

chain = (
    RunnableLambda(prepare_input)
    | prompt
    | structured_llm
    | RunnableLambda(process_output)
)
```

### 3. 에러 처리

```python
try:
    result = await chain.ainvoke(inputs)
except Exception as e:
    logger.error(f"[Chain] 에러 발생: {str(e)}", exc_info=True)
    # Chain 단계별 로깅으로 어느 단계에서 에러 발생했는지 확인
```

### 4. 디버깅

```python
# Chain 단계별 로깅
def prepare_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
    logger.debug(f"[Chain] prepare_input 완료 - message 길이: {len(inputs['message'])}")
    return inputs

def process_output(result: Model) -> Dict[str, Any]:
    logger.debug(f"[Chain] process_output 완료 - status: {result.status}")
    return {"status": result.status}
```

---

## 향후 개선 방안

### ✅ 완료된 개선

1. **Writer Chain 캐싱**: 매번 Chain 생성 → 모듈 레벨 캐싱
2. **에러 추적 개선**: Chain 단계별 로깅 추가
3. **프롬프트 상수화**: 시스템 프롬프트를 상수로 분리

### ⚠️ 단기 개선 (1-2주)

1. **LLM 인스턴스 싱글톤 패턴**
   - 각 노드에서 LLM 인스턴스 재사용
   - 메모리 사용량 감소

2. **State 전달 방식 표준화**
   - 각 Chain마다 State 전달 방식 통일
   - 유지보수성 향상

### 📋 장기 개선 (1-2개월)

1. **LangSmith Tracing 활성화**
   - Chain 실행 추적
   - 디버깅 용이성 향상

2. **Middleware 도입**
   - 재시도 로직
   - Rate Limiting
   - 로깅 미들웨어

3. **커스텀 에러 핸들러**
   - Chain 단계별 에러 처리
   - 자동 재시도

---

## 주요 변경 사항

### Intent Analyzer

**변경점:**
- `ChatPromptTemplate` 사용으로 프롬프트 관리 개선
- `RunnableLambda`로 입력/출력 처리 분리
- 시스템 프롬프트를 상수로 분리 (`INTENT_ANALYSIS_SYSTEM_PROMPT`)

### Writer LLM

**변경점:**
- 입력 준비 로직을 `RunnableLambda`로 분리
- 메시지 포맷팅을 별도 함수로 분리
- 시스템 프롬프트를 템플릿 상수로 분리
- **Chain 캐싱**: 모듈 레벨에서 캐싱하여 성능 개선

### Turn Evaluator

**변경점:**
- 평가 Chain을 함수로 생성 (`create_evaluation_chain`)
- 각 의도별 평가 함수에서 재사용
- 프롬프트 템플릿 상수화

### Holistic Evaluator

**변경점:**
- 각 평가 노드(6a, 6c, 6d)에 Chain 구조 적용
- 프롬프트 템플릿 상수화
- 가중치 상수화

---

## 테스트

### 단위 테스트

```python
# Chain 단계별 테스트
def test_prepare_input():
    inputs = {"human_message": "테스트 메시지"}
    result = prepare_input(inputs)
    assert "human_message" in result

def test_process_output():
    mock_result = IntentAnalysisResult(status="PASSED_HINT", ...)
    result = process_output(mock_result)
    assert result["intent_status"] == "PASSED_HINT"
```

### 통합 테스트

```python
# 전체 Chain 테스트
@pytest.mark.asyncio
async def test_intent_analysis_chain():
    chain = create_intent_analysis_chain()
    result = await chain.ainvoke({"human_message": "테스트"})
    assert "intent_status" in result
```

---

## 주의 사항

### 1. 성능 고려
- Chain 캐싱으로 오버헤드 최소화
- 불필요한 `RunnableLambda` 최소화

### 2. 에러 처리
- Chain 단계별 로깅으로 에러 추적
- 각 단계에서 명확한 에러 메시지

### 3. 메모리 관리
- LLM 인스턴스 싱글톤 패턴 고려
- Chain 캐싱 시 메모리 사용량 모니터링

### 4. State 전달
- 일관된 State 전달 방식 유지
- Chain 간 데이터 형식 통일

---

## 관련 파일

### 구현
- `app/domain/langgraph/nodes/intent_analyzer.py`: Intent Analyzer Chain
- `app/domain/langgraph/nodes/writer.py`: Writer LLM Chain
- `app/domain/langgraph/nodes/turn_evaluator/evaluators.py`: Turn Evaluator Chains
- `app/domain/langgraph/nodes/holistic_evaluator/`: Holistic Evaluator Chains
- `app/domain/langgraph/nodes/system_nodes.py`: System Nodes Chains

### 테스트
- `tests/test_chains.py`: Chain 단위 테스트
- `tests/test_nodes_chains.py`: 노드 통합 테스트

---

## 참고 자료

- **LangChain 공식 문서**: https://python.langchain.com/docs/expression_language/
- **Runnable 가이드**: https://python.langchain.com/docs/expression_language/get_started
- **Chain 구성**: https://python.langchain.com/docs/expression_language/how_to/

