# 토큰 사용량 추적 구현 가이드

## 📋 개요

LangGraph 노드에서 LLM 호출 시 토큰 사용량을 정확하게 추적하기 위한 구현 가이드입니다.

**핵심 문제**: `with_structured_output`을 사용하면 Pydantic 모델만 반환되어 원본 LLM 응답의 메타데이터(토큰 사용량)가 손실됩니다.

**해결 방법**: Chain 실행 전에 원본 LLM을 먼저 호출하여 토큰 사용량을 추출한 후, 구조화된 출력으로 파싱합니다.

---

## 🔍 문제 분석

### `with_structured_output`의 한계

```python
# ❌ 문제가 되는 코드
structured_llm = llm.with_structured_output(IntentClassification)
result = await structured_llm.ainvoke(messages)
# result는 Pydantic 모델만 반환 → 원본 응답 메타데이터 손실
tokens = extract_token_usage(result)  # ❌ 실패 (Pydantic 모델에는 메타데이터 없음)
```

**원인**:
- `with_structured_output`은 내부적으로 원본 LLM 응답을 Pydantic 모델로 변환
- 변환 과정에서 `usage_metadata`, `response_metadata` 등이 손실됨
- 결과적으로 토큰 사용량 추출 불가

---

## ✅ 해결 방법

### 패턴 1: 원본 LLM 먼저 호출 (권장)

**적용 위치**: `with_structured_output`을 사용하는 모든 노드

```python
async def intent_analysis(state: EvalTurnState) -> Dict[str, Any]:
    """의도 분석 - 토큰 추적 개선 버전"""
    
    llm = get_llm()
    structured_llm = llm.with_structured_output(IntentClassification)
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt)
    ]
    
    # 1. 원본 LLM 호출 (토큰 사용량 추출용)
    raw_response = await llm.ainvoke(messages)
    
    # 2. 토큰 사용량 추출 및 State에 누적
    tokens = extract_token_usage(raw_response)
    if tokens:
        accumulate_tokens(state, tokens, token_type="eval")
    
    # 3. 구조화된 출력으로 파싱 (실제 사용)
    parsed_response = await structured_llm.ainvoke(messages)
    
    return {
        "intent_types": [intent.value for intent in parsed_response.intent_types],
        "intent_confidence": parsed_response.confidence,
    }
```

**장점**:
- ✅ 토큰 사용량 정확하게 추출 가능
- ✅ 구조화된 출력 유지
- ✅ 코드가 명확하고 이해하기 쉬움

**단점**:
- ⚠️ LLM을 두 번 호출 (원본 + 구조화된 출력)
- ⚠️ 비용이 약간 증가 (하지만 토큰 추적을 위해 필요)

---

## 📍 적용된 노드 목록

### ✅ 완료된 노드

#### 1. **2번 노드: Intent Analyzer**
- **파일**: `app/domain/langgraph/nodes/intent_analyzer.py`
- **함수**: `intent_analyzer()`
- **토큰 타입**: `chat`
- **적용 방식**: Chain 실행 전에 원본 LLM 호출

```python
# Chain 실행 전에 원본 LLM 호출하여 메타데이터 추출
formatted_messages = format_messages(prepare_input(chain_input))
raw_response = await llm.ainvoke(formatted_messages)

# 토큰 사용량 추출 및 State에 누적
tokens = extract_token_usage(raw_response)
if tokens:
    accumulate_tokens(state, tokens, token_type="chat")
```

#### 2. **4.0 노드: Intent Analysis (의도 분류)**
- **파일**: `app/domain/langgraph/nodes/turn_evaluator/analysis.py`
- **함수**: `intent_analysis()`
- **토큰 타입**: `eval`
- **적용 방식**: 원본 LLM 먼저 호출 후 구조화된 출력 파싱

```python
# 원본 LLM 응답 받기 (토큰 사용량 추출용)
raw_response = await llm.ainvoke(messages)

# 토큰 사용량 추출 및 State에 누적
tokens = extract_token_usage(raw_response)
if tokens:
    accumulate_tokens(state, tokens, token_type="eval")

# 구조화된 출력으로 파싱
parsed_response = await structured_llm.ainvoke(messages)
```

#### 3. **4번 노드: Turn Evaluator (평가 체인)**
- **파일**: `app/domain/langgraph/nodes/turn_evaluator/evaluators.py`
- **함수**: `_evaluate_turn()`
- **토큰 타입**: `eval`
- **적용 방식**: Chain 실행 전에 원본 LLM 호출

```python
# Chain 실행 전에 원본 LLM 호출하여 메타데이터 추출
prepared_input = prepare_evaluation_input_internal(chain_input, eval_type, criteria)
formatted_messages = format_evaluation_messages(prepared_input)

# 원본 LLM 호출 (토큰 사용량 추출용)
raw_response = await llm.ainvoke(formatted_messages)

# 토큰 사용량 추출 및 State에 누적
tokens = extract_token_usage(raw_response)
if tokens:
    accumulate_tokens(state, tokens, token_type="eval")
```

#### 4. **4.X 노드: Answer Summary (답변 요약)**
- **파일**: `app/domain/langgraph/nodes/turn_evaluator/summary.py`
- **함수**: `summarize_answer()`
- **토큰 타입**: `eval`
- **적용 방식**: Chain에서 LLM 응답 객체 보존 (원본 LLM 사용)

```python
# Chain에서 LLM 응답 객체 보존
summary_chain = (
    RunnableLambda(prepare_summary_input)
    | summary_prompt
    | get_llm()  # 원본 LLM 사용 (with_structured_output 없음)
    | RunnableLambda(extract_summary_with_response)
)

# 토큰 사용량 추출
llm_response = chain_result.get("_llm_response")
if llm_response:
    tokens = extract_token_usage(llm_response)
    if tokens:
        accumulate_tokens(state, tokens, token_type="eval")
```

#### 5. **6a 노드: Holistic Flow Evaluator**
- **파일**: `app/domain/langgraph/nodes/holistic_evaluator/flow.py`
- **함수**: `_eval_holistic_flow_impl()`
- **토큰 타입**: `eval`
- **적용 방식**: Chain 실행 전에 원본 LLM 호출

```python
# Chain 실행 전에 원본 LLM 호출하여 메타데이터 추출
prepared_input = prepare_holistic_input(chain_input)
formatted_messages = format_holistic_messages(prepared_input)

# 원본 LLM 호출 (토큰 사용량 추출용)
raw_response = await llm.ainvoke(formatted_messages)

# 토큰 사용량 추출 및 State에 누적
tokens = extract_token_usage(raw_response)
if tokens:
    accumulate_tokens(state, tokens, token_type="eval")
```

#### 6. **6c 노드: Code Performance Evaluator**
- **파일**: `app/domain/langgraph/nodes/holistic_evaluator/performance.py`
- **함수**: `_eval_code_performance_impl()`
- **토큰 타입**: `eval`
- **적용 방식**: Chain 실행 전에 원본 LLM 호출

#### 7. **6d 노드: Code Correctness Evaluator**
- **파일**: `app/domain/langgraph/nodes/holistic_evaluator/correctness.py`
- **함수**: `_eval_code_correctness_impl()`
- **토큰 타입**: `eval`
- **적용 방식**: Chain 실행 전에 원본 LLM 호출

#### 8. **3번 노드: Writer LLM**
- **파일**: `app/domain/langgraph/nodes/writer.py`
- **함수**: `writer_llm()`
- **토큰 타입**: `chat`
- **적용 방식**: Chain에서 LLM 응답 객체 보존 (원본 LLM 사용)

```python
# Chain에서 LLM 응답 객체 보존
_base_writer_chain = (
    RunnableLambda(prepare_writer_input)
    | RunnableLambda(format_writer_messages)
    | _writer_llm  # 원본 LLM 사용
    | RunnableLambda(extract_content_with_response)  # 응답 객체 보존
)

# 토큰 사용량 추출
llm_response = chain_result.get("_llm_response")
if llm_response:
    tokens = extract_token_usage(llm_response)
    if tokens:
        accumulate_tokens(state, tokens, token_type="chat")
```

---

## 🔧 구현 세부사항

### 토큰 추적 유틸리티

**파일**: `app/domain/langgraph/utils/token_tracking.py`

#### `extract_token_usage(response)`
- LLM 응답에서 토큰 사용량 추출
- Gemini API 형식 지원: `usage_metadata.input_tokens`, `usage_metadata.output_tokens`
- 다른 LLM 형식도 지원 (OpenAI 등)

#### `accumulate_tokens(state, new_tokens, token_type)`
- State에 토큰 사용량 누적
- `token_type`: `"chat"` 또는 `"eval"`
- State의 `chat_tokens` 또는 `eval_tokens` 필드에 누적

#### `get_token_summary(state)`
- State에서 토큰 사용량 요약 반환
- `{"chat_tokens": {...}, "eval_tokens": {...}}` 형식

---

## 📊 토큰 타입 분류

### `chat` 타입 (채팅 검사)
- **2번 노드**: Intent Analyzer
- **3번 노드**: Writer LLM

### `eval` 타입 (평가)
- **4번 노드**: Turn Evaluator (의도 분석, 평가, 요약)
- **6번 노드**: Holistic Evaluator (플로우, 성능, 정확성)

---

## ⚠️ 주의사항

### 1. LLM 이중 호출
- `with_structured_output` 사용 시 원본 LLM을 먼저 호출하면 LLM이 두 번 호출됨
- 비용이 약간 증가하지만, 토큰 추적을 위해 필요
- 향후 LangChain에서 메타데이터 보존 기능이 추가되면 개선 가능

### 2. 에러 처리
- 원본 LLM 호출 실패 시 구조화된 출력도 실패할 가능성 높음
- 토큰 추적 실패는 경고 로그만 남기고 계속 진행

### 3. 성능 영향
- LLM 호출이 두 번 발생하므로 응답 시간이 약간 증가
- 하지만 토큰 추적의 정확성을 위해 필요

---

## 🧪 테스트

### 토큰 추적 확인 방법

```python
# 테스트 스크립트: test_token_tracking.py
def test_chat_with_tokens():
    """일반 채팅 메시지 전송 및 토큰 사용량 확인"""
    response = requests.post("/api/chat/message", json={
        "session_id": "test-session",
        "message": "DP에 대해 설명해줘"
    })
    
    result = response.json()
    
    # 토큰 사용량 확인
    if "chat_tokens" in result:
        print(f"Chat tokens: {result['chat_tokens']}")
    
    if "eval_tokens" in result:
        print(f"Eval tokens: {result['eval_tokens']}")
```

---

## 📈 향후 개선 방향

### 1. LangChain 개선 대응
- LangChain에서 `with_structured_output`이 메타데이터를 보존하도록 개선되면
- 원본 LLM 호출 없이 토큰 추적 가능

### 2. 캐싱 최적화
- 동일한 메시지에 대한 구조화된 출력 결과를 캐싱
- 원본 LLM 호출 결과를 재사용

### 3. 비동기 최적화
- 원본 LLM 호출과 구조화된 출력을 병렬 처리 (불가능 - 구조화된 출력이 원본 응답 필요)
- 대신 원본 응답을 재사용하는 방식 고려

---

## 📝 참고 자료

- [LangChain Structured Output](https://python.langchain.com/docs/modules/model_io/output_parsers/structured)
- [Gemini API Usage Metadata](https://ai.google.dev/api/generate-content#usage-metadata)
- [Token Tracking Utility](../app/domain/langgraph/utils/token_tracking.py)


