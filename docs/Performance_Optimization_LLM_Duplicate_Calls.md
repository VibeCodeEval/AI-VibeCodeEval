# LLM 중복 호출 성능 최적화

## 🔍 문제 분석

### 현재 문제점

#### 1. 4번 노드 (Turn Evaluator) - LLM 중복 호출

**위치**: `app/domain/langgraph/nodes/turn_evaluator/evaluators.py`

**문제**:
- `_evaluate_turn` 함수에서 **LLM을 두 번 호출**:
  1. 첫 번째: 원본 LLM 호출 (토큰 추출용) - line 261
  2. 두 번째: 구조화된 출력 Chain 실행 (평가용) - line 272

**코드**:
```python
# 원본 LLM 호출 (토큰 사용량 추출용)
raw_response = await llm.ainvoke(formatted_messages)

# 토큰 사용량 추출
tokens = extract_token_usage(raw_response)
accumulate_tokens(state, tokens, token_type="eval")

# 평가 Chain 실행 (구조화된 출력 파싱) - 여기서 LLM을 다시 호출!
chain_result = await chain.ainvoke(chain_input)
```

**영향**:
- 각 평가 함수마다 LLM을 2번 호출
- 8개 평가 함수가 있다면 총 **16번의 LLM 호출**
- 시간이 **2배**로 소요됨

#### 2. 6번 노드 6.a (Holistic Flow Evaluator) - LLM 중복 호출

**위치**: `app/domain/langgraph/nodes/holistic_evaluator/flow.py`

**문제**:
- 동일한 문제: LLM을 두 번 호출
  1. 첫 번째: 원본 LLM 호출 (토큰 추출용) - line 231
  2. 두 번째: 구조화된 출력 Chain 실행 (평가용) - line 247

**영향**:
- Holistic Flow 평가마다 LLM을 2번 호출
- 시간이 **2배**로 소요됨

---

## 💡 해결 방안

### 방안 1: 구조화된 출력에서 토큰 추출 (권장)

**핵심 아이디어**: `with_structured_output`의 내부 LLM 호출에서 토큰을 추출

**구현 방법**:
1. `with_structured_output`은 내부적으로 LLM을 호출
2. 호출 결과에서 토큰 정보를 추출할 수 있어야 함
3. LangChain의 `invoke`/`ainvoke`는 응답 메타데이터를 포함할 수 있음

**코드 예시**:
```python
async def _evaluate_turn_optimized(state: EvalTurnState, eval_type: str, criteria: str) -> Dict[str, Any]:
    """최적화된 턴 평가 (LLM 1회 호출)"""
    try:
        # 평가 Chain 생성
        chain = create_evaluation_chain(eval_type, criteria)
        
        chain_input = {"state": state}
        
        # Chain 실행 (구조화된 출력)
        # with_structured_output은 내부적으로 LLM을 호출하므로
        # 응답 메타데이터에서 토큰을 추출할 수 있어야 함
        chain_result = await chain.ainvoke(chain_input)
        
        # Chain 실행 후 응답 메타데이터 확인
        # LangChain의 응답 객체는 response_metadata를 포함할 수 있음
        if hasattr(chain_result, 'response_metadata'):
            tokens = extract_token_usage_from_metadata(chain_result.response_metadata)
            if tokens:
                accumulate_tokens(state, tokens, token_type="eval")
        
        # 또는 Chain 내부에서 토큰 정보를 전달하도록 수정
        # ...
        
        return chain_result
```

**문제점**:
- `with_structured_output`의 응답은 Pydantic 모델이므로 메타데이터가 없을 수 있음
- LangChain의 구조화된 출력은 원본 응답 메타데이터를 보존하지 않을 수 있음

### 방안 2: 구조화된 출력 Chain 내부에서 토큰 추출 (권장)

**핵심 아이디어**: Chain 내부에서 원본 LLM 응답을 캡처하여 토큰 추출

**구현 방법**:
1. Chain 내부에서 원본 LLM 호출
2. 원본 응답에서 토큰 추출
3. 구조화된 출력 파싱
4. 토큰 정보를 Chain 결과에 포함

**코드 예시**:
```python
def create_evaluation_chain_optimized(eval_type: str, criteria: str):
    """최적화된 평가 Chain (LLM 1회 호출)"""
    llm = get_llm()
    structured_llm = llm.with_structured_output(TurnEvaluation)
    
    async def call_llm_and_extract_tokens(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """LLM 호출 및 토큰 추출 (비동기)"""
        messages = inputs.get("messages", [])
        
        # 원본 LLM 호출 (토큰 추출용)
        raw_response = await llm.ainvoke(messages)
        
        # 토큰 추출
        tokens = extract_token_usage(raw_response)
        
        # 구조화된 출력 파싱 (동일한 메시지로)
        # 주의: structured_llm은 내부적으로 LLM을 다시 호출하므로
        # 이 방법도 여전히 2번 호출됨
        
        # 대안: 원본 응답을 직접 파싱
        structured_result = parse_structured_output(raw_response, TurnEvaluation)
        
        return {
            "structured_result": structured_result,
            "tokens": tokens,  # 토큰 정보 포함
        }
    
    chain = (
        RunnableLambda(prepare_evaluation_input)
        | RunnableLambda(format_messages)
        | RunnableLambda(call_llm_and_extract_tokens)  # 비동기 함수는 RunnableLambda로 직접 사용 불가
        | RunnableLambda(process_output_with_response)
    )
    
    return chain
```

**문제점**:
- `RunnableLambda`는 비동기 함수를 직접 지원하지 않음
- `with_structured_output`은 내부적으로 LLM을 다시 호출하므로 여전히 2번 호출됨

### 방안 3: 원본 응답을 직접 파싱 (최적)

**핵심 아이디어**: 원본 LLM 응답을 받아서 직접 구조화된 출력으로 파싱

**구현 방법**:
1. 원본 LLM 호출 (1회)
2. 원본 응답에서 토큰 추출
3. 원본 응답을 JSON으로 파싱하여 Pydantic 모델로 변환

**코드 예시**:
```python
async def _evaluate_turn_optimized_v2(state: EvalTurnState, eval_type: str, criteria: str) -> Dict[str, Any]:
    """최적화된 턴 평가 (LLM 1회 호출, 원본 응답 직접 파싱)"""
    try:
        chain_input = {"state": state}
        
        # 메시지 포맷팅
        prepared_input = prepare_evaluation_input_internal(chain_input, eval_type, criteria)
        formatted_messages = format_evaluation_messages(prepared_input)
        
        # 원본 LLM 호출 (1회만!)
        llm = get_llm()
        raw_response = await llm.ainvoke(formatted_messages)
        
        # 토큰 사용량 추출
        tokens = extract_token_usage(raw_response)
        if tokens:
            accumulate_tokens(state, tokens, token_type="eval")
        
        # 원본 응답을 구조화된 출력으로 파싱
        # 방법 1: JSON 모드 사용 (Gemini는 JSON 모드 지원)
        if hasattr(raw_response, 'content'):
            content = raw_response.content
            # JSON 파싱
            import json
            try:
                # JSON 응답 파싱
                if isinstance(content, str):
                    # JSON 문자열인 경우
                    parsed_json = json.loads(content)
                else:
                    # 이미 dict인 경우
                    parsed_json = content
                
                # Pydantic 모델로 변환
                structured_result = TurnEvaluation(**parsed_json)
            except (json.JSONDecodeError, ValueError) as e:
                # JSON 파싱 실패 시 fallback: 구조화된 출력 Chain 사용
                logger.warning(f"JSON 파싱 실패, 구조화된 출력 Chain 사용: {e}")
                structured_llm = llm.with_structured_output(TurnEvaluation)
                structured_result = await structured_llm.ainvoke(formatted_messages)
        
        # 결과 처리
        result = {
            "intent": structured_result.intent,
            "score": structured_result.score,
            "average": structured_result.score,
            "rubrics": [r.dict() for r in structured_result.rubrics],
            "final_reasoning": structured_result.final_reasoning,
        }
        
        # State에 누적된 토큰 정보를 result에 포함
        if "eval_tokens" in state:
            result["eval_tokens"] = state["eval_tokens"]
        
        return result
```

**장점**:
- ✅ LLM 호출 1회만
- ✅ 토큰 추출 가능
- ✅ 구조화된 출력 파싱 가능

**단점**:
- ❌ LLM이 JSON 형식으로 응답하지 않을 수 있음
- ❌ JSON 파싱 실패 시 fallback 필요

### 방안 4: JSON 모드 사용 (Gemini 지원)

**핵심 아이디어**: Gemini의 JSON 모드 사용하여 구조화된 출력 직접 받기

**구현 방법**:
1. LLM 호출 시 JSON 모드 활성화
2. JSON 응답을 직접 받아서 Pydantic 모델로 파싱
3. 토큰 정보는 응답 메타데이터에서 추출

**코드 예시**:
```python
async def _evaluate_turn_optimized_v3(state: EvalTurnState, eval_type: str, criteria: str) -> Dict[str, Any]:
    """최적화된 턴 평가 (JSON 모드 사용)"""
    try:
        chain_input = {"state": state}
        
        # 메시지 포맷팅
        prepared_input = prepare_evaluation_input_internal(chain_input, eval_type, criteria)
        formatted_messages = format_evaluation_messages(prepared_input)
        
        # JSON 모드로 LLM 호출
        llm = get_llm()
        
        # Gemini JSON 모드 설정
        # 주의: ChatGoogleGenerativeAI는 response_format 파라미터 지원 여부 확인 필요
        # 또는 프롬프트에 JSON 형식 요청 추가
        
        # JSON 형식 요청을 프롬프트에 추가
        json_format_prompt = """
다음 형식의 JSON으로 응답하세요:
{
  "intent": "의도",
  "score": 0-100,
  "rubrics": [...],
  "final_reasoning": "..."
}
"""
        
        # 시스템 프롬프트에 JSON 형식 요청 추가
        formatted_messages[0].content += "\n\n" + json_format_prompt
        
        # LLM 호출 (1회만!)
        raw_response = await llm.ainvoke(formatted_messages)
        
        # 토큰 사용량 추출
        tokens = extract_token_usage(raw_response)
        if tokens:
            accumulate_tokens(state, tokens, token_type="eval")
        
        # JSON 파싱
        import json
        import re
        
        content = raw_response.content
        
        # JSON 추출 (마크다운 코드 블록 제거)
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            parsed_json = json.loads(json_str)
            structured_result = TurnEvaluation(**parsed_json)
        else:
            # JSON 파싱 실패 시 fallback
            structured_llm = llm.with_structured_output(TurnEvaluation)
            structured_result = await structured_llm.ainvoke(formatted_messages)
        
        # 결과 처리
        result = {
            "intent": structured_result.intent,
            "score": structured_result.score,
            "average": structured_result.score,
            "rubrics": [r.dict() for r in structured_result.rubrics],
            "final_reasoning": structured_result.final_reasoning,
        }
        
        if "eval_tokens" in state:
            result["eval_tokens"] = state["eval_tokens"]
        
        return result
```

---

## 🎯 최종 추천 방안

### 단기 해결책: 방안 3 (원본 응답 직접 파싱)

**이유**:
- ✅ 구현이 간단함
- ✅ LLM 호출 1회로 최적화
- ✅ 기존 코드 구조 최소 변경

**구현 단계**:
1. `_evaluate_turn` 함수 수정
2. 원본 LLM 호출 후 JSON 파싱
3. 파싱 실패 시 기존 `with_structured_output` 사용 (fallback)

### 장기 해결책: 방안 4 (JSON 모드 사용)

**이유**:
- ✅ 가장 효율적 (LLM 호출 1회)
- ✅ 구조화된 출력 보장
- ✅ 토큰 추출 가능

**구현 단계**:
1. Gemini JSON 모드 지원 확인
2. 프롬프트에 JSON 형식 요청 추가
3. JSON 파싱 로직 구현
4. Fallback 메커니즘 추가

---

## 📊 예상 성능 개선

### 현재 (LLM 2회 호출)
- 4번 노드: 8개 평가 × 2회 = **16회 LLM 호출**
- 6.a 노드: **2회 LLM 호출**
- **총 소요 시간**: T × 2

### 최적화 후 (LLM 1회 호출)
- 4번 노드: 8개 평가 × 1회 = **8회 LLM 호출**
- 6.a 노드: **1회 LLM 호출**
- **총 소요 시간**: T × 1

**성능 개선**: **약 50% 시간 단축**

---

## 🔧 구현 우선순위

1. **높음**: 4번 노드 최적화 (가장 많은 LLM 호출)
2. **높음**: 6.a 노드 최적화 (긴 프롬프트로 인한 긴 응답 시간)
3. **중간**: 다른 노드들도 동일한 패턴 확인 및 최적화









