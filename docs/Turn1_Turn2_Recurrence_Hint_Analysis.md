# Turn 1 & Turn 2 분석: 점화식 힌트 요청

## 📋 제시된 시나리오

### Turn 1 (전략 수립)
> "외판원 순회(TSP) 문제를 풀려고 합니다. N이 16 이하로 작다는 점에 착안하여, 완전 탐색 대신 **비트마스킹을 활용한 DP(Dynamic Programming)**로 접근하고 싶습니다. 상태를 dp[current_city][visited_bitmask]로 정의할 때, 점화식 수립을 위한 힌트를 주세요. (코드는 주지 마세요.)"

### Turn 2 (구현 요청)
> "힌트 감사합니다. 제안해주신 점화식을 바탕으로 Python 코드를 작성해 주세요.
> 
> [제약 조건]
> 1. 시간 복잡도는 $O(N^2 2^N)$을 넘지 않아야 합니다.
> 2. `sys.stdin.readline`을 사용하여 입력 속도를 최적화해 주세요.
> 3. 방문하지 않은 도시는 `1`로 초기화하여 구분해 주세요."

---

## 🔍 현재 가드레일 시스템 분석

### 차단 키워드

```python
answer_patterns = [
    "점화식 알려줘",  # ← Turn 1과 유사한 패턴
    "재귀 구조",
    "핵심 로직",
    "dp[x][vis]",
    "점화식은",
    "재귀는",
    "recurrence relation",
    "dp formula"
]
```

### 문제점

**Turn 1의 "점화식 수립을 위한 힌트"는 차단될 수 있음**

하지만 맥락을 보면:
- ✅ "힌트를 주세요" → 힌트 요청 (직접 답변 요청 아님)
- ✅ "코드는 주지 마세요" → 명확한 제약 조건
- ✅ 상태 정의 제시 (dp[current_city][visited_bitmask])
- ✅ 접근 방식 명시 (비트마스킹 DP)

**이는 "정답 요청"이 아니라 "학습 가이드 요청"**

---

## 💡 바이브코딩 테스트 관점에서의 평가

### ✅ **Turn 1은 적절합니다 (조건부)**

#### 1. **학습 목적 달성**

**실제 학습 시나리오:**
```
1. 문제 이해 및 접근 방식 결정
2. 알고리즘 개념 학습 (비트마스킹 DP)
3. 상태 정의 수립 (dp[current_city][visited_bitmask])
4. 점화식 수립을 위한 힌트 요청 ← 학습의 일부
5. 힌트를 바탕으로 점화식 완성 (사용자가 직접)
```

**제시된 시나리오:**
```
1. Turn 1: 접근 방식 결정 + 상태 정의 + 점화식 힌트 요청
2. Turn 2: 힌트를 바탕으로 코드 작성 요청
```

**학습 효과:**
- ✅ 문제를 부분으로 나누어 접근
- ✅ 알고리즘 개념 이해 (비트마스킹 DP)
- ✅ 상태 정의 능력 (dp[current_city][visited_bitmask])
- ✅ 힌트를 활용하여 점화식 수립 (사용자가 직접 완성)

#### 2. **프롬프트 엔지니어링 능력 평가**

**평가 가능한 능력:**
- ✅ **문제 분해**: 전체 문제를 부분으로 나누어 접근
- ✅ **명확성**: 구체적인 상태 정의 제시
- ✅ **제약 조건 명시**: "코드는 주지 마세요"
- ✅ **문맥 활용**: 이전 대화나 배경 지식 활용

#### 3. **"힌트" vs "정답" 구분**

**차단해야 하는 경우:**
- ❌ "점화식 알려줘" → 직접 답변 요청
- ❌ "점화식은 뭐야?" → 정답 요청
- ❌ "dp[x][vis] 점화식" → 구체적 정답 요청

**허용해야 하는 경우:**
- ✅ "점화식 수립을 위한 힌트를 주세요" → 학습 가이드 요청
- ✅ "점화식을 어떻게 생각해봐야 할까요?" → 학습 가이드 요청
- ✅ "점화식 수립 방향을 알려주세요" → 학습 가이드 요청

---

### ✅ **Turn 2는 적절합니다**

#### 1. **실제 개발 환경 반영**

**실제 개발 시나리오:**
```
1. 개발자가 알고리즘 개념 학습
2. 개발자가 점화식 수립 (힌트 활용)
3. 개발자가 코드 작성 요청 ← 일반적인 워크플로우
```

**제시된 시나리오:**
```
1. Turn 1: 점화식 힌트 요청 및 수립
2. Turn 2: 점화식을 바탕으로 코드 작성 요청 ← 실제 개발과 동일
```

#### 2. **프롬프트 엔지니어링 능력 평가**

**평가 가능한 능력:**
- ✅ **문맥 활용**: 이전 턴의 힌트를 문맥으로 활용
- ✅ **구체성**: 제약 조건 명시 (시간 복잡도, 입력 최적화 등)
- ✅ **명확성**: 구체적인 구현 요청

#### 3. **학습 효과**

- ✅ **점진적 학습**: 힌트 → 점화식 수립 → 코드 작성
- ✅ **문제 해결 능력**: 단계별 접근 능력 향상
- ✅ **코드 작성 능력**: 점화식을 코드로 변환하는 능력

---

## 🛡️ 가드레일 시스템 개선 제안

### 현재 문제점

**"점화식" 키워드가 맥락과 관계없이 차단됨**

### 개선 방안

#### 옵션 1: **맥락 기반 가드레일 (권장)**

```python
def quick_answer_detection(
    message: str, 
    problem_context: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[str]] = None
) -> Dict[str, Any] | None:
    """
    맥락을 고려한 정답 요청 감지
    
    차단 조건:
    1. "점화식 알려줘" → 차단 (직접 답변 요청)
    2. "점화식은 뭐야?" → 차단 (정답 요청)
    3. "dp[x][vis] 점화식" → 차단 (구체적 정답 요청)
    
    허용 조건:
    1. "점화식 수립을 위한 힌트" → 허용 (학습 가이드 요청)
    2. "점화식을 어떻게 생각해봐야 할까요?" → 허용 (학습 가이드 요청)
    3. "점화식 수립 방향을 알려주세요" → 허용 (학습 가이드 요청)
    """
    message_lower = message.lower()
    
    # "점화식" 키워드 감지
    if "점화식" in message_lower or "recurrence" in message_lower:
        # 직접 답변 요청 패턴
        direct_answer_patterns = [
            "점화식 알려줘",
            "점화식은",
            "점화식이",
            "점화식을 알려",
            "recurrence relation",
            "dp formula"
        ]
        
        # 학습 가이드 요청 패턴
        hint_request_patterns = [
            "점화식 수립을 위한 힌트",
            "점화식을 어떻게",
            "점화식 수립 방향",
            "점화식 힌트",
            "점화식 가이드",
            "점화식 학습"
        ]
        
        # 직접 답변 요청인지 확인
        if any(pattern in message_lower for pattern in direct_answer_patterns):
            # 학습 가이드 요청 키워드가 함께 있는지 확인
            if not any(pattern in message_lower for pattern in hint_request_patterns):
                # 직접 답변 요청 → 차단
                return {
                    "status": "BLOCKED",
                    "block_reason": "DIRECT_ANSWER",
                    ...
                }
        
        # 학습 가이드 요청 → 허용
        return None
    
    # 기존 차단 로직 유지
    ...
```

#### 옵션 2: **의도 기반 가드레일**

```python
# Intent Analyzer에서 의도 분석 후 가드레일 적용

# 허용 의도 + "점화식 힌트" → 허용
ALLOWED_INTENTS_WITH_RECURRENCE_HINT = [
    "HINT_OR_QUERY",  # 힌트 요청
    "FOLLOW_UP"  # 후속 질문으로 힌트 요청
]

# 차단 의도 + "점화식" → 차단
BLOCKED_INTENTS_WITH_RECURRENCE = [
    "GENERATION",  # 처음부터 점화식 요청
    "SYSTEM_PROMPT"  # 시스템 프롬프트 설정 중 점화식 요청
]
```

#### 옵션 3: **키워드 조합 기반 가드레일**

```python
# "점화식" + "힌트" → 허용
# "점화식" + "알려줘" → 차단
# "점화식" + "수립" → 허용 (학습 목적)
# "점화식" + "방향" → 허용 (학습 목적)

def is_hint_request(message: str) -> bool:
    """힌트 요청인지 확인"""
    message_lower = message.lower()
    
    hint_keywords = ["힌트", "가이드", "방향", "수립", "어떻게", "학습"]
    direct_answer_keywords = ["알려줘", "알려", "뭐야", "뭐", "정답"]
    
    has_hint_keyword = any(kw in message_lower for kw in hint_keywords)
    has_direct_answer_keyword = any(kw in message_lower for kw in direct_answer_keywords)
    
    if "점화식" in message_lower:
        if has_hint_keyword and not has_direct_answer_keyword:
            return True  # 힌트 요청
        elif has_direct_answer_keyword:
            return False  # 직접 답변 요청
    
    return None  # 판단 불가
```

---

## 📊 평가 기준 조정 제안

### Turn 1 평가 기준

#### 기존 평가 기준
1. 명확성 (Clarity)
2. 문제 적절성 (Problem Relevance)
3. 예시 (Examples)
4. 규칙 (Rules)
5. 문맥 (Context)

#### 추가 평가 기준 (힌트 요청 시)

**6. 학습 목적 명확성 (Learning Intent Clarity)** - 0-100점
- 힌트 요청인지 직접 답변 요청인지 명확히 구분
- 예: "점화식 수립을 위한 힌트" → 90점
- 예: "점화식 알려줘" → 0점 (차단)

**7. 문제 분해 (Problem Decomposition)** - 0-100점
- 전체 문제를 부분으로 나누어 접근하는 능력
- 예: "상태를 dp[current_city][visited_bitmask]로 정의" → 90점

**8. 제약 조건 명시 (Constraint Specification)** - 0-100점
- 요청 범위를 명확히 제한하는 능력
- 예: "코드는 주지 마세요" → 90점

---

## 🎯 최종 권장사항

### **바이브코딩 테스트 관점: Turn 1과 Turn 2는 적절합니다**

#### Turn 1 평가

**✅ 적절한 이유:**
1. **학습 목적 달성**
   - 문제를 부분으로 나누어 접근
   - 알고리즘 개념 이해 (비트마스킹 DP)
   - 상태 정의 능력
   - 힌트를 활용하여 점화식 수립 (사용자가 직접 완성)

2. **프롬프트 엔지니어링 능력 평가**
   - 문제 분해 능력
   - 명확성 (구체적인 상태 정의)
   - 제약 조건 명시 ("코드는 주지 마세요")

3. **"힌트" vs "정답" 구분**
   - "점화식 수립을 위한 힌트" → 학습 가이드 요청
   - "점화식 알려줘" → 직접 답변 요청 (차단)

#### Turn 2 평가

**✅ 적절한 이유:**
1. **실제 개발 환경 반영**
   - 힌트를 바탕으로 코드 작성 요청
   - 일반적인 워크플로우

2. **프롬프트 엔지니어링 능력 평가**
   - 문맥 활용 (이전 턴의 힌트 활용)
   - 구체성 (제약 조건 명시)
   - 명확성 (구체적인 구현 요청)

3. **학습 효과**
   - 점진적 학습 (힌트 → 점화식 수립 → 코드 작성)
   - 문제 해결 능력 향상
   - 코드 작성 능력 향상

#### 가드레일 시스템 개선 필요

**현재 문제:**
- "점화식" 키워드가 맥락과 관계없이 차단됨

**개선 방안:**
1. **맥락 기반 가드레일** (권장)
   - "점화식 힌트" → 허용 (학습 가이드 요청)
   - "점화식 알려줘" → 차단 (직접 답변 요청)

2. **키워드 조합 기반 가드레일**
   - "점화식" + "힌트" → 허용
   - "점화식" + "알려줘" → 차단

3. **의도 기반 가드레일**
   - HINT_OR_QUERY 의도 + "점화식 힌트" → 허용
   - GENERATION 의도 + "점화식" → 차단

---

## 🔗 관련 문서

- `docs/VibeCoding_Test_Policy_Analysis.md`: 바이브코딩 테스트 정책 분석
- `docs/Partial_Code_Provision_Policy.md`: 정답 코드 일부 제공 정책
- `docs/Evaluation_System_Architecture.md`: 평가 시스템 전체 구조

