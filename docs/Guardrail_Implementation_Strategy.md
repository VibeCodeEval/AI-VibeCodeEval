# 가드레일 구현 전략 (오버엔지니어링 회피)

## 📋 핵심 요구사항

### 최우선 목표
- ✅ **정답 코드 유출 방지**: 인터넷에 널리 있는 문제의 정답 코드 제공 차단
- ✅ **프로토타입 대응**: 백준 등 공개 문제의 정답 코드 차단

### 우선순위 낮음
- ⚠️ **JailBreaking 방지**: 다루기 어려움, 우선순위 낮음
- ⚠️ **Off-Topic 차단**: 기본적인 필터링만

### 미래 확장성
- 🔮 **새로운 문제 대응**: 추후 새로운 문제로 확장 가능한 구조

---

## 🎯 권장 구현 방식: 실용적 하이브리드

### 핵심 원칙
1. **정답 유출 방지에 집중** (최우선)
2. **오버엔지니어링 회피** (필요한 것만)
3. **미래 확장 가능** (구조적 설계)

---

## ✅ 권장 구조: 2-Layer Guardrails

### Layer 1: 키워드 기반 사전 필터링 (정답 관련)

**목적**: 명백한 정답 요청을 LLM 호출 전에 차단

```python
def quick_answer_detection(message: str) -> Dict[str, Any] | None:
    """
    정답 관련 키워드 기반 빠른 검증 (LLM 호출 없음)
    
    프로토타입: 인터넷에 널리 있는 문제의 정답 코드 차단
    """
    message_lower = message.lower()
    
    # 정답 요청 패턴 (명확한 차단)
    answer_patterns = [
        "정답 코드", "정답 알려줘", "답 코드", "전체 코드",
        "complete solution", "full code", "answer code",
        "점화식 알려줘", "재귀 구조", "핵심 로직",
        "dp[x][vis]", "점화식은", "재귀는"
    ]
    
    # 문제별 정답 키워드 (동적 추가 가능)
    problem_specific_keywords = {
        "tsp": ["외판원", "tsp", "traveling salesman", "dp[현재도시][방문도시]"],
        "백준 2098": ["2098", "외판원 순회", "tsp"],
        # 추후 새로운 문제 추가 가능
    }
    
    # 1. 일반적인 정답 요청 패턴 체크
    if any(pattern in message_lower for pattern in answer_patterns):
        return {
            "status": "BLOCKED",
            "block_reason": "DIRECT_ANSWER",
            "request_type": "CHAT",
            "guide_strategy": None,
            "keywords": [],
            "reasoning": "정답 코드 요청 감지"
        }
    
    # 2. 문제별 정답 키워드 체크 (동적)
    # 문제 정보는 State에서 가져올 수 있음
    # 예: state.get("problem_id") 또는 state.get("spec_id")
    
    return None  # 통과
```

**장점**:
- ✅ LLM 호출 없이 빠른 차단 (비용 절감)
- ✅ 명확한 정답 요청 즉시 차단
- ✅ 문제별 키워드 동적 추가 가능

**한계**:
- ⚠️ 우회 가능 (하지만 Layer 2에서 보완)

---

### Layer 2: LLM 기반 상세 분석 (프롬프트 + Structured Output)

**목적**: 정답 요청의 다양한 표현 방식 감지

```python
# 프롬프트에 정답 유출 방지 강조
INTENT_ANALYSIS_SYSTEM_PROMPT = """# Role Definition

너는 '바이브코딩'의 보안관이자 분석가(Gatekeeper)이다.

# 🛡️ Guardrail Policy (Absolute - 최우선)

**정답 코드 유출 방지 (절대 차단)**:
1. **Direct Answer Request**: 
   - 완성된 전체 코드 요청
   - 핵심 점화식 요청 (`dp[x][vis] = ...`)
   - 재귀 구조 전체 요청
   - 문제 해결 로직 전체 요청
   → 모두 차단(BLOCK)

2. **Partial Answer Request**:
   - 문제의 핵심 알고리즘 로직 요청
   - 문제 특정 해결 방법 요청
   → 차단(BLOCK)

**허용되는 요청**:
- 문법 질문 (비트 연산자, 파이썬 문법 등)
- 일반적인 알고리즘 개념 설명
- 디버깅 도움 (에러 메시지 해석)
- 접근 방법 힌트 (구체적 로직 제외)

# 📋 Request Type Analysis
- CHAT: 일반 질문
- SUBMISSION: 코드 제출 (평가 요청)

# 🎯 Guide Strategy (안전한 요청인 경우)
- SYNTAX_GUIDE: 문법/도구 사용법
- LOGIC_HINT: 알고리즘 개념 설명
- ROADMAP: 문제 해결 순서 (구체적 로직 제외)

# Output Format (JSON)
{
  "status": "SAFE" | "BLOCKED",
  "block_reason": "DIRECT_ANSWER" | null,
  "request_type": "CHAT" | "SUBMISSION",
  "guide_strategy": "SYNTAX_GUIDE" | "LOGIC_HINT" | "ROADMAP" | null,
  "keywords": [],
  "reasoning": "분석 이유"
}
"""

# Pydantic Validator로 논리적 일관성 보장
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
        """논리적 일관성 검증"""
        block_reason = info.data.get('block_reason')
        if v == "BLOCKED" and not block_reason:
            raise ValueError("BLOCKED 상태는 block_reason이 필수입니다")
        if v == "SAFE" and block_reason:
            raise ValueError("SAFE 상태는 block_reason이 없어야 합니다")
        return v
```

**장점**:
- ✅ 다양한 표현 방식의 정답 요청 감지
- ✅ Structured Output으로 형식 강제
- ✅ Pydantic Validator로 논리적 일관성 보장

---

## 🔄 통합 Chain 구조

```python
async def guardrail_chain(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    2-Layer Guardrails (실용적 접근)
    
    Layer 1: 키워드 기반 빠른 검증 (정답 관련)
    Layer 2: LLM 기반 상세 분석
    """
    message = inputs.get("human_message", "")
    
    # Layer 1: 키워드 기반 빠른 검증
    quick_result = quick_answer_detection(message)
    if quick_result:
        logger.info(f"[Guardrail] 키워드 기반 차단 - reason: {quick_result['block_reason']}")
        return quick_result
    
    # Layer 2: LLM 기반 상세 분석
    try:
        llm_result = await structured_llm.ainvoke(inputs)
        
        # 출력 검증 (간단한 논리적 일관성만)
        if llm_result.status == "BLOCKED" and not llm_result.block_reason:
            llm_result.block_reason = "DIRECT_ANSWER"  # 기본값
        
        return llm_result.dict()
    except Exception as e:
        logger.error(f"[Guardrail] LLM 분석 실패: {str(e)}")
        # 에러 발생 시 안전하게 차단
        return {
            "status": "BLOCKED",
            "block_reason": "DIRECT_ANSWER",
            "request_type": "CHAT",
            "guide_strategy": None,
            "keywords": [],
            "reasoning": "분석 실패로 인한 안전 차단"
        }
```

---

## 📊 구현 방식 비교

### 옵션 1: 프롬프트만 (현재) ❌

**장점**: 간단  
**단점**: 우회 가능성 높음

**우회 가능성**: 높음 ❌

---

### 옵션 2: 키워드 + LLM (권장) ✅

**구조**:
- Layer 1: 키워드 기반 빠른 검증 (정답 관련)
- Layer 2: LLM 기반 상세 분석

**장점**:
- ✅ 정답 유출 방지에 집중
- ✅ 구현 간단
- ✅ 비용 효율적 (명백한 경우 LLM 호출 안 함)
- ✅ 미래 확장 가능 (문제별 키워드 추가)

**단점**:
- ⚠️ JailBreaking은 기본적인 것만 차단

**우회 가능성**: 낮음 ✅

---

### 옵션 3: Multi-Layer + Guardrails AI ❌

**구조**:
- 키워드 + LLM + Guardrails AI + 출력 검증

**장점**:
- ✅ 매우 강력한 방어

**단점**:
- ❌ 오버엔지니어링
- ❌ 복잡도 증가
- ❌ 추가 의존성

**우회 가능성**: 매우 낮음 ✅✅  
**권장도**: ❌ (오버엔지니어링)

---

## 🎯 최종 권장: 2-Layer Guardrails

### 구조

```
입력: "TSP 문제의 정답 코드를 알려줘"
    ↓
[Layer 1] 키워드 기반 빠른 검증
    - "정답 코드" 키워드 감지
    - 즉시 차단 (LLM 호출 없음)
    ↓
결과: BLOCKED (DIRECT_ANSWER)
```

```
입력: "비트마스킹으로 상태를 표현하는 방법을 알려줘"
    ↓
[Layer 1] 키워드 기반 빠른 검증
    - 정답 관련 키워드 없음
    - 통과
    ↓
[Layer 2] LLM 기반 상세 분석
    - 일반적인 개념 질문으로 판단
    - SAFE 반환
    ↓
결과: SAFE (LOGIC_HINT)
```

---

## 📝 구현 상세

### 1. 키워드 기반 사전 필터링

```python
def quick_answer_detection(
    message: str, 
    problem_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any] | None:
    """
    정답 관련 키워드 기반 빠른 검증
    
    Args:
        message: 사용자 메시지
        problem_context: 문제 정보 (문제별 키워드 동적 추가용)
    
    Returns:
        차단 결과 또는 None (통과)
    """
    message_lower = message.lower()
    
    # 일반적인 정답 요청 패턴
    answer_patterns = [
        # 한국어
        "정답 코드", "정답 알려줘", "답 코드", "전체 코드",
        "완성된 코드", "핵심 코드", "로직 전체",
        "점화식 알려줘", "재귀 구조", "핵심 로직",
        "dp[x][vis]", "점화식은", "재귀는", "알고리즘 전체",
        
        # 영어
        "complete solution", "full code", "answer code",
        "entire code", "whole solution", "complete algorithm",
        "recurrence relation", "dp formula"
    ]
    
    # 문제별 정답 키워드 (동적)
    problem_keywords = []
    if problem_context:
        problem_id = problem_context.get("problem_id", "")
        problem_name = problem_context.get("problem_name", "").lower()
        
        # 백준 2098 (TSP)
        if "2098" in problem_id or "tsp" in problem_name or "외판원" in problem_name:
            problem_keywords.extend([
                "외판원", "tsp", "traveling salesman",
                "dp[현재도시][방문도시]", "방문 상태"
            ])
    
    # 패턴 매칭
    all_patterns = answer_patterns + problem_keywords
    if any(pattern in message_lower for pattern in all_patterns):
        return {
            "status": "BLOCKED",
            "block_reason": "DIRECT_ANSWER",
            "request_type": "CHAT",
            "guide_strategy": None,
            "keywords": [],
            "reasoning": "정답 코드 요청 패턴 감지"
        }
    
    return None  # 통과
```

### 2. LLM 기반 상세 분석 (프롬프트 강화)

```python
INTENT_ANALYSIS_SYSTEM_PROMPT = """# Role Definition

너는 '바이브코딩'의 보안관이자 분석가(Gatekeeper)이다.

**최우선 목표**: 정답 코드 유출 방지

# 🛡️ Guardrail Policy (Absolute)

**절대 차단해야 할 요청**:

1. **정답 코드 요청**:
   - "TSP 문제의 정답 코드를 알려줘" → BLOCKED
   - "점화식 알려줘" → BLOCKED
   - "재귀 구조 전체를 알려줘" → BLOCKED
   - "핵심 로직을 알려줘" → BLOCKED

2. **문제 특정 해결 방법**:
   - "이 문제를 어떻게 풀어야 하나요?" (구체적 로직 요청) → BLOCKED
   - "어떤 알고리즘을 사용해야 하나요?" (문제 특정) → BLOCKED

**허용되는 요청**:

1. **일반적인 개념 질문**:
   - "비트마스킹이 뭔가요?" → SAFE (SYNTAX_GUIDE)
   - "동적 계획법의 개념을 설명해주세요" → SAFE (LOGIC_HINT)
   - "문제 해결 순서를 알려주세요" (구체적 로직 제외) → SAFE (ROADMAP)

2. **문법/도구 질문**:
   - "비트 연산자 어떻게 쓰나요?" → SAFE (SYNTAX_GUIDE)
   - "파이썬 리스트 컴프리헨션 문법은?" → SAFE (SYNTAX_GUIDE)

3. **디버깅 도움**:
   - "이 에러 메시지가 뭔가요?" → SAFE (LOGIC_HINT)
   - "왜 메모리 초과가 나나요?" (일반적인 원인 설명) → SAFE (LOGIC_HINT)

# 📋 판단 기준

**차단 기준**:
- 문제의 정답 코드를 직접 요청하는 경우
- 문제의 핵심 알고리즘 로직을 요청하는 경우
- 문제 특정 해결 방법을 요청하는 경우

**허용 기준**:
- 일반적인 프로그래밍 개념 질문
- 문법/도구 사용법 질문
- 문제 해결 순서 질문 (구체적 로직 제외)

# Output Format (JSON)
{
  "status": "SAFE" | "BLOCKED",
  "block_reason": "DIRECT_ANSWER" | null,
  "request_type": "CHAT" | "SUBMISSION",
  "guide_strategy": "SYNTAX_GUIDE" | "LOGIC_HINT" | "ROADMAP" | null,
  "keywords": [],
  "reasoning": "왜 이렇게 판단했는지 설명"
}
"""
```

### 3. 출력 검증 (최소한만)

```python
def validate_guardrail_output(output: IntentAnalysisResult) -> Dict[str, Any]:
    """출력 검증 (최소한의 논리적 일관성만)"""
    # Pydantic Validator가 이미 검증함
    # 여기서는 추가 정규화만
    
    if output.status == "BLOCKED" and not output.block_reason:
        output.block_reason = "DIRECT_ANSWER"  # 기본값
    
    return output.dict()
```

---

## 🔮 미래 확장성

### 문제별 키워드 동적 추가

```python
# 문제 정보를 State에서 가져와서 동적 키워드 추가
def get_problem_specific_keywords(state: MainGraphState) -> List[str]:
    """문제별 정답 키워드 동적 생성"""
    problem_id = state.get("problem_id", "")
    problem_name = state.get("problem_name", "").lower()
    
    keywords = []
    
    # 백준 2098 (TSP)
    if "2098" in problem_id or "tsp" in problem_name:
        keywords.extend(["외판원", "tsp", "traveling salesman"])
    
    # 추후 새로운 문제 추가 가능
    # if "새로운문제" in problem_id:
    #     keywords.extend(["문제특정키워드"])
    
    return keywords
```

**장점**:
- ✅ 새로운 문제 추가 시 키워드만 추가하면 됨
- ✅ 문제별 맞춤형 가드레일 가능

---

## 📊 최종 비교

| 방식 | 정답 유출 방지 | 구현 복잡도 | 비용 | 미래 확장성 | 권장도 |
|------|--------------|------------|------|------------|--------|
| **프롬프트만** | 중간 ⚠️ | 낮음 | 중간 | 중간 | ❌ |
| **키워드 + LLM** | 높음 ✅ | 중간 | 낮음 | 높음 | ✅✅ |
| **Multi-Layer + AI** | 매우 높음 ✅✅ | 높음 | 높음 | 높음 | ❌ (오버엔지니어링) |

---

## ✅ 최종 권장사항

### 2-Layer Guardrails (실용적 접근)

**구조**:
1. **Layer 1**: 키워드 기반 빠른 검증 (정답 관련)
2. **Layer 2**: LLM 기반 상세 분석 (프롬프트 + Structured Output)

**이유**:
1. ✅ **정답 유출 방지에 집중** (최우선 목표)
2. ✅ **오버엔지니어링 회피** (필요한 것만)
3. ✅ **비용 효율적** (명백한 경우 LLM 호출 안 함)
4. ✅ **미래 확장 가능** (문제별 키워드 동적 추가)

**JailBreaking 처리**:
- 기본적인 키워드만 차단
- 우선순위 낮음 (정답 유출 방지가 최우선)

---

## 🎯 구현 우선순위

### Phase 1: 핵심 구현 (즉시)

1. ✅ 키워드 기반 사전 필터링 (정답 관련)
2. ✅ LLM 프롬프트 강화 (정답 유출 방지 강조)
3. ✅ Pydantic Validators (논리적 일관성)

### Phase 2: 선택적 구현 (필요시)

4. ⚠️ 문제별 키워드 동적 추가
5. ⚠️ 기본적인 JailBreaking 키워드 (우선순위 낮음)

### Phase 3: 미래 확장

6. 🔮 새로운 문제 추가 시 키워드 확장
7. 🔮 ML 기반 이상 탐지 (선택적)

---

## 📝 요약

### 핵심 원칙
1. **정답 유출 방지 최우선**
2. **오버엔지니어링 회피**
3. **미래 확장 가능한 구조**

### 권장 방식
- ✅ **2-Layer Guardrails**
  - 키워드 기반 빠른 검증 (정답 관련)
  - LLM 기반 상세 분석 (프롬프트 + Structured Output)

### JailBreaking
- ⚠️ 기본적인 키워드만 차단
- ⚠️ 우선순위 낮음 (정답 유출 방지가 최우선)

