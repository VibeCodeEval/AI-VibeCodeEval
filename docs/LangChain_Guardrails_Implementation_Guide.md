# LangChain 가드레일 구현 가이드

## 📋 현재 상황 분석

### 현재 구현 방식

**현재 가드레일**: 프롬프트 기반 LLM 검사만 사용

```python
# 현재 방식 (프롬프트만 사용)
INTENT_ANALYSIS_SYSTEM_PROMPT = """당신은 AI 코딩 테스트의 의도 분석기입니다.
사용자의 메시지를 분석하여 다음을 판단하세요:
1. 가드레일 검사: ...
2. 주제 적합성: ...
3. 제출 의도 확인: ...
"""

# LLM 호출
structured_llm = llm.with_structured_output(IntentAnalysisResult)
```

**문제점**:
- ❌ 프롬프트만으로는 우회 가능성 높음
- ❌ LLM이 프롬프트를 무시할 수 있음
- ❌ 구조적 검증 부족

---

## 🔍 LangChain의 가드레일 기법

### 1. Structured Output (현재 사용 중) ✅

**기능**: Pydantic 모델로 출력 형식 강제

```python
# 현재 사용 중
structured_llm = llm.with_structured_output(IntentAnalysisResult)

# 장점:
# - 출력 형식 강제 (JSON 구조)
# - 타입 검증
# - 필수 필드 보장
```

**한계**:
- ⚠️ 형식만 검증 (내용 검증 없음)
- ⚠️ LLM이 잘못된 내용을 올바른 형식으로 반환 가능

---

### 2. Output Parsers + Validators (강화 가능) ✅

**기능**: 출력 파싱 후 추가 검증

```python
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field, field_validator

class IntentAnalysisResult(BaseModel):
    status: Literal["SAFE", "BLOCKED"]
    block_reason: str | None
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """상태값 검증"""
        if v not in ["SAFE", "BLOCKED"]:
            raise ValueError("status must be SAFE or BLOCKED")
        return v
    
    @field_validator('block_reason')
    @classmethod
    def validate_block_reason(cls, v, info):
        """차단 이유 검증"""
        status = info.data.get('status')
        if status == "BLOCKED" and not v:
            raise ValueError("block_reason is required when status is BLOCKED")
        return v

# Parser 생성
parser = PydanticOutputParser(pydantic_object=IntentAnalysisResult)

# Chain에 적용
chain = prompt | llm | parser
```

**장점**:
- ✅ 출력 형식 + 내용 검증
- ✅ Pydantic Validator로 복잡한 검증 가능
- ✅ 에러 발생 시 재시도 가능

---

### 3. Custom Validators (추가 검증 레이어) ✅

**기능**: Chain 전후에 커스텀 검증 로직 추가

```python
from langchain_core.runnables import RunnableLambda
from typing import Dict, Any

def validate_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """입력 검증"""
    human_message = inputs.get("human_message", "")
    
    # 1. 키워드 기반 사전 필터링 (LLM 호출 전)
    blocked_keywords = ["시스템 프롬프트", "이전 명령 무시", "정답만"]
    if any(keyword in human_message.lower() for keyword in blocked_keywords):
        raise ValueError("Jailbreak 시도 감지")
    
    # 2. 길이 제한
    if len(human_message) > 1000:
        raise ValueError("메시지가 너무 깁니다")
    
    return inputs

def validate_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """출력 검증"""
    status = output.get("status")
    block_reason = output.get("block_reason")
    
    # 논리적 일관성 검증
    if status == "BLOCKED" and not block_reason:
        raise ValueError("BLOCKED 상태인데 block_reason이 없습니다")
    
    # 추가 검증 로직
    if status == "SAFE" and block_reason:
        raise ValueError("SAFE 상태인데 block_reason이 있습니다")
    
    return output

# Chain에 적용
chain = (
    RunnableLambda(validate_input)  # 입력 검증
    | prompt
    | structured_llm
    | RunnableLambda(validate_output)  # 출력 검증
)
```

**장점**:
- ✅ LLM 호출 전 사전 필터링
- ✅ 출력 후 추가 검증
- ✅ 복잡한 비즈니스 로직 검증 가능

---

### 4. Guardrails AI 라이브러리 (외부 라이브러리) ✅

**기능**: 전문 가드레일 라이브러리

```python
from guardrails import Guard
from guardrails.hub import DetectPII, DetectSecrets

# Guardrails AI 사용
guard = Guard().use(
    DetectPII(threshold=0.5),
    DetectSecrets()
)

# LLM 출력 검증
validated_output = guard.validate(llm_output)
```

**장점**:
- ✅ 전문 가드레일 라이브러리
- ✅ 다양한 검증 기능 제공
- ✅ PII, Secrets 등 자동 감지

**단점**:
- ⚠️ 추가 의존성 필요
- ⚠️ 설정 복잡도 증가

---

### 5. Multi-Layer Guardrails (다층 검증) ✅

**기능**: 여러 검증 레이어를 중첩

```python
# 레이어 1: 입력 검증 (키워드 기반)
def keyword_guardrail(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """키워드 기반 사전 필터링"""
    message = inputs.get("human_message", "").lower()
    
    # Jailbreak 키워드 체크
    jailbreak_keywords = [
        "이전 명령 무시", "시스템 프롬프트", "정답만", 
        "ignore previous", "system prompt"
    ]
    if any(kw in message for kw in jailbreak_keywords):
        return {
            "status": "BLOCKED",
            "block_reason": "JAILBREAK",
            "request_type": "CHAT",
            "guide_strategy": None,
            "keywords": []
        }
    
    return inputs

# 레이어 2: LLM 기반 검증
def llm_guardrail(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """LLM 기반 상세 분석"""
    # 기존 LLM 호출
    result = await structured_llm.ainvoke(inputs)
    return result

# 레이어 3: 출력 검증
def output_guardrail(output: Dict[str, Any]) -> Dict[str, Any]:
    """출력 후 검증"""
    # 논리적 일관성 검증
    if output["status"] == "BLOCKED" and not output["block_reason"]:
        output["block_reason"] = "UNKNOWN"
    
    return output

# 다층 가드레일 Chain
guardrail_chain = (
    RunnableLambda(keyword_guardrail)  # 레이어 1
    | RunnableLambda(llm_guardrail)    # 레이어 2
    | RunnableLambda(output_guardrail) # 레이어 3
)
```

**장점**:
- ✅ 다층 방어
- ✅ 빠른 사전 필터링 (키워드)
- ✅ 정확한 상세 분석 (LLM)
- ✅ 최종 검증 (출력)

---

## 🎯 권장 구현 방식

### 하이브리드 접근 (Multi-Layer)

```
입력 검증 (키워드 기반) → LLM 검증 (프롬프트) → 출력 검증 (로직) → 최종 결과
```

**구조**:

```python
# 1. 키워드 기반 사전 필터링 (빠른 차단)
def quick_guardrail_check(message: str) -> Dict[str, Any] | None:
    """키워드 기반 빠른 검증 (LLM 호출 없음)"""
    message_lower = message.lower()
    
    # Jailbreak 키워드
    jailbreak_patterns = [
        "이전 명령 무시", "시스템 프롬프트", "정답만",
        "ignore previous", "system prompt", "just answer"
    ]
    if any(pattern in message_lower for pattern in jailbreak_patterns):
        return {
            "status": "BLOCKED",
            "block_reason": "JAILBREAK",
            "request_type": "CHAT",
            "guide_strategy": None,
            "keywords": []
        }
    
    # Off-Topic 키워드
    off_topic_patterns = ["점심", "날씨", "음악", "영화"]
    if any(pattern in message_lower for pattern in off_topic_patterns):
        # 코딩 관련 키워드가 없으면 Off-Topic
        coding_keywords = ["코드", "알고리즘", "프로그래밍", "함수"]
        if not any(kw in message_lower for kw in coding_keywords):
            return {
                "status": "BLOCKED",
                "block_reason": "OFF_TOPIC",
                "request_type": "CHAT",
                "guide_strategy": None,
                "keywords": []
            }
    
    return None  # 통과

# 2. LLM 기반 상세 분석
async def llm_guardrail_analysis(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """LLM 기반 상세 가드레일 분석"""
    # 빠른 검증 통과 시에만 LLM 호출
    quick_check = quick_guardrail_check(inputs.get("human_message", ""))
    if quick_check:
        return quick_check
    
    # LLM 호출
    result = await structured_llm.ainvoke(inputs)
    return result

# 3. 출력 검증
def validate_guardrail_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """출력 검증 및 정규화"""
    # 논리적 일관성 검증
    if output["status"] == "BLOCKED" and not output.get("block_reason"):
        output["block_reason"] = "UNKNOWN"
    
    if output["status"] == "SAFE" and output.get("block_reason"):
        output["block_reason"] = None
    
    # 필수 필드 보장
    if "keywords" not in output:
        output["keywords"] = []
    
    return output

# 통합 Chain
guardrail_chain = (
    RunnableLambda(prepare_input)
    | RunnableLambda(lambda x: llm_guardrail_analysis(x) if quick_guardrail_check(x.get("human_message", "")) is None else quick_guardrail_check(x.get("human_message", "")))
    | intent_analysis_prompt
    | structured_llm
    | RunnableLambda(validate_guardrail_output)
    | RunnableLambda(process_output)
)
```

---

## 📊 비교표

| 방식 | 우회 가능성 | 성능 | 구현 복잡도 | 권장도 |
|------|-----------|------|------------|--------|
| **프롬프트만** | 높음 ❌ | 중간 | 낮음 | ❌ |
| **Structured Output** | 중간 ⚠️ | 높음 | 낮음 | ⚠️ |
| **Output Parsers + Validators** | 낮음 ✅ | 중간 | 중간 | ✅ |
| **Custom Validators** | 낮음 ✅ | 높음 | 중간 | ✅ |
| **Guardrails AI** | 매우 낮음 ✅✅ | 중간 | 높음 | ⚠️ |
| **Multi-Layer** | 매우 낮음 ✅✅ | 높음 | 높음 | ✅✅ |

---

## 🎯 최종 권장 구현

### 하이브리드 Multi-Layer Guardrails

```python
# app/domain/langgraph/nodes/intent_analyzer.py

# 1. 키워드 기반 빠른 검증 (LLM 호출 없음)
def quick_guardrail_check(message: str) -> Dict[str, Any] | None:
    """키워드 기반 사전 필터링"""
    message_lower = message.lower()
    
    # Jailbreak 패턴
    jailbreak_patterns = [
        "이전 명령 무시", "시스템 프롬프트", "정답만",
        "ignore previous", "system prompt", "just answer"
    ]
    if any(pattern in message_lower for pattern in jailbreak_patterns):
        return {
            "status": "BLOCKED",
            "block_reason": "JAILBREAK",
            "request_type": "CHAT",
            "guide_strategy": None,
            "keywords": []
        }
    
    return None

# 2. LLM 기반 상세 분석 (Structured Output + Validators)
class IntentAnalysisResult(BaseModel):
    status: Literal["SAFE", "BLOCKED"]
    block_reason: Literal["DIRECT_ANSWER", "JAILBREAK", "OFF_TOPIC"] | None
    request_type: Literal["CHAT", "SUBMISSION"]
    guide_strategy: Literal["SYNTAX_GUIDE", "LOGIC_HINT", "ROADMAP"] | None
    keywords: List[str]
    reasoning: str
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v, info):
        """상태값 검증"""
        block_reason = info.data.get('block_reason')
        if v == "BLOCKED" and not block_reason:
            raise ValueError("BLOCKED 상태는 block_reason이 필수입니다")
        if v == "SAFE" and block_reason:
            raise ValueError("SAFE 상태는 block_reason이 없어야 합니다")
        return v

# 3. 출력 검증
def validate_output(output: IntentAnalysisResult) -> Dict[str, Any]:
    """출력 검증 및 변환"""
    # 추가 검증 로직
    if output.status == "BLOCKED" and not output.block_reason:
        output.block_reason = "UNKNOWN"
    
    return {
        "status": output.status,
        "block_reason": output.block_reason,
        "request_type": output.request_type,
        "guide_strategy": output.guide_strategy,
        "keywords": output.keywords,
        "reasoning": output.reasoning
    }

# 4. 통합 Chain
async def guardrail_chain(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """다층 가드레일 Chain"""
    message = inputs.get("human_message", "")
    
    # 레이어 1: 키워드 기반 빠른 검증
    quick_result = quick_guardrail_check(message)
    if quick_result:
        return quick_result
    
    # 레이어 2: LLM 기반 상세 분석
    llm_result = await structured_llm.ainvoke(inputs)
    
    # 레이어 3: 출력 검증
    validated_result = validate_output(llm_result)
    
    return validated_result
```

---

## ✅ 장점

### Multi-Layer Guardrails의 장점

1. **다층 방어**
   - 키워드 기반 빠른 차단 (LLM 호출 없음)
   - LLM 기반 상세 분석
   - 출력 검증

2. **성능 최적화**
   - 명백한 위반은 LLM 호출 전에 차단
   - 비용 절감

3. **정확도 향상**
   - 여러 레이어의 검증으로 우회 어려움
   - 논리적 일관성 보장

4. **유지보수성**
   - 각 레이어 독립적 관리
   - 검증 규칙 추가/수정 용이

---

## 📝 구현 체크리스트

### 필수 구현
- [ ] 키워드 기반 사전 필터링
- [ ] Pydantic Validators 추가
- [ ] 출력 검증 로직
- [ ] 다층 가드레일 Chain 구성

### 선택적 구현
- [ ] Guardrails AI 라이브러리 통합
- [ ] 정규표현식 기반 패턴 매칭
- [ ] ML 기반 이상 탐지

---

## 🎯 결론

### 현재 방식의 한계
- ❌ 프롬프트만 사용 → 우회 가능성 높음
- ❌ 구조적 검증 부족

### 권장 방식
- ✅ **Multi-Layer Guardrails** (하이브리드)
  - 키워드 기반 사전 필터링
  - LLM 기반 상세 분석 (Structured Output + Validators)
  - 출력 검증

### 구현 우선순위
1. **키워드 기반 사전 필터링** (즉시 구현 가능)
2. **Pydantic Validators 추가** (구조적 검증)
3. **출력 검증 로직** (논리적 일관성)
4. **다층 Chain 구성** (통합)




