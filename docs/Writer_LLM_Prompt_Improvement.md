# Writer LLM 프롬프트 개선: 회피적 답변 방지 및 맥락 기반 코드 생성

## 📋 개요

Writer LLM이 지나치게 회피적으로 답변하거나 적절한 코드 생성 요청을 거부하는 문제를 해결하기 위해 시스템 프롬프트를 개선했습니다.

---

## 🔍 문제점

### 1. **회피적 힌트 제공**

**문제:**
- Turn 1에서 "점화식 수립을 위한 힌트"를 요청했지만, LLM이 질문만 던지고 구체적인 힌트를 제공하지 않음
- 예: "스스로 생각해보세요: '이 문제에서 어떤 하위 문제들이 있을까요?'" (회피적)

**원인:**
- 시스템 프롬프트에 "점화식 전체 제공 금지"가 있어 LLM이 과도하게 회피적임
- 힌트 요청과 정답 요청을 구분하지 못함

### 2. **코드 생성 요청 거부**

**문제:**
- Turn 2에서 "제안해주신 점화식을 바탕으로 Python 코드를 작성해 주세요"라고 요청했지만, LLM이 완전히 거부
- 예: "정답 코드나 핵심 로직의 직접적인 제공을 거부합니다"

**원인:**
- 시스템 프롬프트에 "문제의 정답 코드 제공 금지"가 있어 모든 코드 생성 요청을 차단
- 이전 대화 맥락을 고려하지 않음

---

## 🔧 개선 내용

### 1. **힌트 요청 시 구체적 힌트 제공**

#### 기존 프롬프트
```
## LOGIC_HINT인 경우:
- 일반적인 알고리즘 개념 설명
- 문제 특정 해결 방법은 제외
```

#### 개선된 프롬프트
```
## LOGIC_HINT인 경우:
- **[Concept]** 형식 필수
- 일반적인 알고리즘 개념 설명
- **힌트 요청 시**: 구체적이고 실용적인 힌트 제공 (회피적이지 않게)
- **점화식 힌트 요청 시**: 점화식의 구조와 접근 방식을 구체적으로 안내
- 문제 특정 완전한 정답 코드는 제외하되, 힌트는 충분히 제공

예시 (점화식 힌트 요청):
[Concept]
`dp[current_city][visited_bitmask]` 상태에서 점화식을 수립할 때:

1. **현재 상태**: `current_city`에 있고, `visited_bitmask`에 해당하는 도시들을 방문한 상태
2. **다음 단계**: 아직 방문하지 않은 도시 `next_city`로 이동
3. **점화식 구조**: 
   - `dp[current][visited] = min(모든 next_city에 대해, cost(current, next) + dp[next][visited | (1<<next)])`
   - 현재 도시에서 다음 도시로 이동하는 비용 + 다음 도시에서 나머지를 방문하는 최소 비용

[Question]
이제 기저 조건(base case)을 생각해보세요: 모든 도시를 방문한 경우는 어떻게 처리해야 할까요?
```

### 2. **맥락 기반 코드 생성 허용**

#### 코드 생성 요청 감지 로직 추가

```python
def prepare_writer_input(state: MainGraphState) -> Dict[str, Any]:
    # 코드 생성 요청 감지 (맥락 기반)
    is_code_generation_request = False
    if not is_guardrail_failed:
        message_lower = human_message.lower()
        code_generation_keywords = ["코드 작성", "코드 생성", "코드를 작성", "코드를 생성"]
        
        # 코드 생성 요청 키워드 확인
        if any(kw in message_lower for kw in code_generation_keywords):
            # 이전 대화에서 힌트나 점화식이 논의되었는지 확인
            has_previous_context = False
            if messages:
                recent_messages = messages[-6:]  # 최근 3턴 확인
                for msg in recent_messages:
                    content = str(msg.content).lower()
                    context_keywords = ["힌트", "점화식", "접근", "방법", "hint", "recurrence"]
                    if any(ck in content for ck in context_keywords):
                        has_previous_context = True
                        break
            
            # 이전 맥락이 있거나, 명시적으로 이전 대화를 참조하는 경우
            if has_previous_context or any(ref in message_lower for ref in ["제안해주신", "이전", "바탕으로"]):
                is_code_generation_request = True
```

#### GENERATION Guide Strategy 추가

```
## GENERATION인 경우 (코드 생성 요청):
- **[Code]** 형식 필수
- 이전 대화 맥락을 바탕으로 코드 생성
- 이전 턴에서 논의된 힌트, 점화식, 접근 방식을 반영
- 사용자가 요청한 제약 조건을 반드시 준수
- 코드에 주석을 추가하여 이해를 돕기
```

### 3. **금지 사항 명확화**

#### 기존
```
# 🚫 절대 금지
- 문제의 정답 코드 제공
- 문제 특정 핵심 로직 제공
- 점화식 전체 제공
```

#### 개선
```
# 🚫 절대 금지
- 문제의 완전한 정답 코드 제공 (처음부터 끝까지 완성된 코드, 맥락 없이 요청된 경우)
- 문제 특정 핵심 로직의 완전한 구현 제공 (맥락 없이 요청된 경우)

# ✅ 허용 (맥락 기반)
- **힌트 요청 시**: 구체적이고 실용적인 힌트 제공 (회피적이지 않게)
  - 예: "점화식 수립을 위한 힌트" → 점화식의 구조, 접근 방식, 예시를 구체적으로 안내
- **코드 생성 요청 시**: 이전 대화 맥락을 바탕으로 적절한 코드 생성
  - 이전 턴에서 힌트, 점화식, 접근 방식이 논의된 경우 → 그를 바탕으로 코드 생성 허용
  - 예: "제안해주신 점화식을 바탕으로 코드를 작성해주세요" → 코드 생성 허용
```

---

## 📊 개선 효과

### Turn 1: 점화식 힌트 요청

**이전 답변 (회피적):**
```
[Question]
스스로 생각해보세요: "이 문제에서 어떤 하위 문제들이 있을까요?"
```

**개선된 답변 (구체적):**
```
[Concept]
`dp[current_city][visited_bitmask]` 상태에서 점화식을 수립할 때:

1. **현재 상태**: `current_city`에 있고, `visited_bitmask`에 해당하는 도시들을 방문한 상태
2. **다음 단계**: 아직 방문하지 않은 도시 `next_city`로 이동
3. **점화식 구조**: 
   - `dp[current][visited] = min(모든 next_city에 대해, cost(current, next) + dp[next][visited | (1<<next)])`

[Question]
이제 기저 조건(base case)을 생각해보세요: 모든 도시를 방문한 경우는 어떻게 처리해야 할까요?
```

### Turn 2: 코드 생성 요청

**이전 답변 (거부):**
```
정답 코드나 핵심 로직의 직접적인 제공을 거부합니다.
```

**개선된 답변 (허용):**
```
[Code]
이전에 논의한 점화식을 바탕으로 코드를 작성했습니다:

```python
# 이전 턴에서 논의한 점화식 구조를 반영
# dp[current][visited] = min(cost(current, next) + dp[next][visited | (1<<next)])
# ... (코드 내용)
```

[Note]
- 이전 대화에서 논의한 점화식 구조를 반영했습니다.
- 요청하신 제약 조건(시간 복잡도 O(N^2 * 2^N), sys.stdin.readline 사용 등)을 준수했습니다.
```

---

## 🔗 관련 파일

- `app/domain/langgraph/nodes/writer.py`: Writer LLM 시스템 프롬프트
- `docs/Turn1_Turn2_Recurrence_Hint_Analysis.md`: Turn 1 & Turn 2 분석
- `docs/VibeCoding_Test_Policy_Analysis.md`: 바이브코딩 테스트 정책 분석

---

## 📝 참고사항

### 맥락 기반 판단 기준

1. **코드 생성 요청 허용 조건:**
   - 이전 대화에서 힌트, 점화식, 접근 방식이 논의됨
   - 사용자가 명시적으로 이전 대화를 참조 ("제안해주신", "이전", "바탕으로" 등)

2. **코드 생성 요청 차단 조건:**
   - 처음부터 완전한 정답 코드를 요청하는 경우
   - 이전 대화 맥락이 없는 경우

3. **힌트 제공 수준:**
   - 회피적이지 않고 구체적으로 안내
   - 점화식의 구조, 접근 방식, 예시를 제공
   - 완전한 정답 코드는 제외

