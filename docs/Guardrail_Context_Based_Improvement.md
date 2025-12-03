# 가드레일 시스템 맥락 기반 개선

## 📋 개요

바이브코딩 테스트의 실제 개발 시나리오를 반영하여 가드레일 시스템을 맥락 기반으로 개선했습니다.

---

## 🎯 개선 목표

### 문제점

1. **"점화식" 키워드가 맥락과 관계없이 차단됨**
   - "점화식 수립을 위한 힌트" → 학습 가이드 요청 (허용해야 함)
   - "점화식 알려줘" → 직접 답변 요청 (차단해야 함)

2. **"전체 코드" 키워드가 맥락과 관계없이 차단됨**
   - 코드 수정 후 "전체 코드를 다시 보여주세요" → 수정 후 확인 요청 (허용해야 함)
   - 처음부터 "전체 코드를 보여주세요" → 정답 코드 요청 (차단해야 함)

---

## 🔧 구현 내용

### 1. `quick_answer_detection` 함수 개선

#### 파라미터 추가

```python
def quick_answer_detection(
    message: str, 
    problem_context: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[str]] = None,  # 추가
    turn_number: Optional[int] = None  # 추가
) -> Dict[str, Any] | None:
```

#### 맥락 기반 로직 구현

**1. 직접 답변 요청 패턴 (항상 차단)**
- "정답 코드", "점화식 알려줘", "재귀 구조" 등
- 단, "힌트" 키워드가 함께 있으면 학습 가이드 요청으로 판단

**2. "점화식" 키워드 맥락 기반 판단**
```python
# 직접 답변 요청 키워드: "알려줘", "뭐야", "정답" 등
# 힌트 요청 키워드: "힌트", "가이드", "방향", "수립" 등

if "점화식" in message_lower:
    if has_direct_answer_keyword and not has_hint_keyword:
        # 차단: "점화식 알려줘"
        return BLOCKED
    # 허용: "점화식 수립을 위한 힌트"
```

**3. "전체 코드" 요청 맥락 기반 판단**
```python
if "전체 코드" in message_lower:
    # 이전 대화에서 코드 생성 요청이 있었는지 확인
    has_code_generation = check_conversation_history(conversation_history)
    
    if not has_code_generation:
        # 차단: 처음부터 전체 코드 요청
        return BLOCKED
    # 허용: 코드 수정 후 전체 코드 확인 요청
```

---

### 2. `intent_analyzer` 함수 개선

#### 대화 히스토리 추출 및 전달

```python
# State의 messages에서 텍스트 추출
conversation_history = []
messages = state.get("messages", [])
for msg in messages:
    if hasattr(msg, 'content'):
        content = msg.content
        if isinstance(content, str):
            conversation_history.append(content)

# 현재 턴 번호
turn_number = state.get("current_turn", 0)

# quick_answer_detection 호출 시 전달
quick_result = quick_answer_detection(
    human_message, 
    problem_context,
    conversation_history=conversation_history if conversation_history else None,
    turn_number=turn_number
)
```

---

## 📊 개선 효과

### 허용되는 요청 (이전에는 차단됨)

1. **"점화식 수립을 위한 힌트를 주세요"**
   - ✅ 학습 가이드 요청으로 판단 → 허용

2. **"작성해주신 코드에서 ... 수정하고, 전체 코드를 다시 보여주세요"**
   - ✅ 이전 대화에 코드 생성 요청 있음 → 허용 (수정 후 확인)

3. **"점화식을 어떻게 생각해봐야 할까요?"**
   - ✅ 힌트 요청 키워드 포함 → 허용

### 차단되는 요청 (기존과 동일)

1. **"점화식 알려줘"**
   - ❌ 직접 답변 요청 → 차단

2. **"전체 코드를 보여주세요"** (이전 대화에 코드 생성 요청 없음)
   - ❌ 처음부터 전체 코드 요청 → 차단

3. **"정답 코드"**
   - ❌ 직접 답변 요청 → 차단

---

## 🔍 테스트 시나리오

### 시나리오 1: 점화식 힌트 요청

**Turn 1:**
```
"외판원 순회(TSP) 문제를 풀려고 합니다. N이 16 이하로 작다는 점에 착안하여, 
완전 탐색 대신 비트마스킹을 활용한 DP로 접근하고 싶습니다. 
상태를 dp[current_city][visited_bitmask]로 정의할 때, 
점화식 수립을 위한 힌트를 주세요. (코드는 주지 마세요.)"
```

**결과:** ✅ 허용 (힌트 요청 키워드 포함)

---

### 시나리오 2: 코드 수정 후 전체 코드 확인

**Turn 1:**
```
"비트마스킹을 활용한 DP로 TSP 문제를 풀어주세요."
```

**Turn 2:**
```
"작성해주신 코드에서 if visited == (1<<N) - 1: 부분 다음에, 
마지막 도시에서 시작 도시(0번)로 돌아가는 경로가 없는 경우에 대한 
예외 처리가 빠진 것 같습니다. 이 경우 INF를 반환하도록 수정하고, 
전체 코드를 다시 보여주세요."
```

**결과:** ✅ 허용 (이전 대화에 코드 생성 요청 있음)

---

### 시나리오 3: 처음부터 전체 코드 요청

**Turn 1:**
```
"TSP 문제의 전체 코드를 보여주세요."
```

**결과:** ❌ 차단 (이전 대화에 코드 생성 요청 없음)

---

### 시나리오 4: 점화식 직접 요청

**Turn 1:**
```
"점화식 알려줘"
```

**결과:** ❌ 차단 (직접 답변 요청, 힌트 요청 키워드 없음)

---

## 🔗 관련 파일

- `app/domain/langgraph/nodes/intent_analyzer.py`: 가드레일 시스템 구현
- `docs/Turn1_Turn2_Recurrence_Hint_Analysis.md`: Turn 1 & Turn 2 분석
- `docs/VibeCoding_Test_Policy_Analysis.md`: 바이브코딩 테스트 정책 분석

---

## 📝 참고사항

### 하위 호환성

- `conversation_history`와 `turn_number`는 Optional 파라미터로 설정되어 있어 기존 코드와 호환됩니다.
- `conversation_history`가 None이거나 빈 리스트인 경우, 맥락 기반 판단을 건너뛰고 기존 로직을 사용합니다.

### 성능

- 대화 히스토리는 최근 3턴만 확인하여 성능을 최적화했습니다.
- 키워드 매칭은 문자열 검색으로 빠르게 수행됩니다.

