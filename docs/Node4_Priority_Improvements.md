# Node 4번 우선순위 높은 개선 사항 구현

## 📋 개요

Node 4번(Turn Evaluator)의 우선순위 높은 개선 사항을 구현했습니다:
1. 의도 분류 일관성 향상 (우선순위 기반 단일 선택)
2. 평가 기준 구체화 (정량적 메트릭 통합)

---

## ✅ 구현 완료 사항

### 1. 의도 분류 일관성 향상

#### 문제점
- 하나의 프롬프트가 여러 의도(RULE_SETTING, HINT_OR_QUERY)로 분류됨
- 평가 일관성 저하 및 점수 왜곡 가능성

#### 해결 방안
- **우선순위 기반 단일 선택** 구현
- 복수 의도 선택 시 우선순위가 가장 높은 의도만 선택

#### 구현 내용

**의도 우선순위 정의:**
```python
intent_priority = {
    CodeIntentType.GENERATION.value: 1,  # 최우선
    CodeIntentType.OPTIMIZATION.value: 2,
    CodeIntentType.DEBUGGING.value: 3,
    CodeIntentType.TEST_CASE.value: 4,
    CodeIntentType.RULE_SETTING.value: 5,
    CodeIntentType.SYSTEM_PROMPT.value: 6,
    CodeIntentType.HINT_OR_QUERY.value: 7,
    CodeIntentType.FOLLOW_UP.value: 8,  # 최하위
}
```

**선택 로직:**
```python
# 복수 의도 선택 시 우선순위가 가장 높은 의도만 선택
if len(intent_values) > 1:
    selected_intent = min(intent_values, key=lambda x: intent_priority.get(x, 999))
    intent_values = [selected_intent]
```

**시스템 프롬프트 개선:**
- "모두 선택하세요 (복수 선택 가능)" → "가장 적절한 의도를 **단일 선택**하세요"
- 우선순위 규칙 명시
- 예시 추가: "코드를 작성하고 최적화해주세요" → GENERATION 선택

---

### 2. 평가 기준 구체화 (정량적 메트릭 통합)

#### 문제점
- LLM 평가만으로는 주관적이고 일관성 부족
- 점수 범위별 구체적 기준 부재

#### 해결 방안
- **정량적 메트릭 계산 유틸리티** 구현
- 평가 프롬프트에 메트릭 정보 통합
- 점수 범위별 구체적 기준 명시

#### 구현 내용

**정량적 메트릭 유틸리티** (`app/domain/langgraph/utils/prompt_metrics.py`):

1. **명확성 메트릭**
   - 단어 수, 문장 수, 평균 단어/문장
   - 구체적 값 포함 여부 및 개수 (숫자, 복잡도 표기 등)

2. **예시 메트릭**
   - 예시 포함 여부
   - 예시 개수 (입력/출력 쌍, 예시 키워드 기준)

3. **규칙 메트릭**
   - XML 태그 사용 여부 및 개수
   - 제약 조건 명시 여부 및 개수
   - 구조화된 형식 사용 여부 (리스트, 번호 매기기 등)

4. **문맥 메트릭**
   - 이전 대화 참조 여부
   - 참조 횟수

5. **문제 적절성 메트릭**
   - 기술 용어 사용 개수
   - 문제별 알고리즘 언급 여부

**평가 프롬프트 개선:**

기존:
```
평가 기준 (Claude Prompt Engineering):
1. 명확성 (Clarity): 요청이 모호하지 않고 구체적인가?
2. 문제 적절성 (Problem Relevance): ...
```

개선:
```
[정량적 메트릭 (참고용)]
- 텍스트 길이: 150자, 단어 수: 25개, 문장 수: 3개
- 명확성 메트릭: 구체적 값 포함 True, 값 개수 2개
- 예시 메트릭: 예시 포함 True, 예시 개수 1개
- 규칙 메트릭: XML 태그 False (0개), 제약조건 True (1개), 구조화 형식 True
- 문맥 메트릭: 이전 대화 참조 True (1회)
- 문제 적절성 메트릭: 기술 용어 2개

평가 기준 (Claude Prompt Engineering):
1. **명확성 (Clarity)**: 요청이 모호하지 않고 구체적인가?
   - 메트릭 참고: 단어 수 25개, 문장 수 3개, 구체적 값 2개
   - 점수 범위별 기준:
     * 90-100점: 단어 수 20-200개, 문장 수 2-10개, 구체적 값 1개 이상 포함
     * 70-89점: 단어 수 10-20개 또는 200-300개, 문장 수 1-2개 또는 10-15개
     * 50-69점: 단어 수 5-10개 또는 300개 이상, 문장 수 1개 또는 15개 이상
     * 0-49점: 단어 수 5개 미만, 문장 수 1개 미만, 매우 모호한 표현
```

---

## 📊 메트릭 계산 예시

### 예시 1: "점화식 수립을 위한 힌트를 주세요"

```python
metrics = calculate_all_metrics(
    "외판원 순회(TSP) 문제를 풀려고 합니다. N이 16 이하로 작다는 점에 착안하여, 완전 탐색 대신 비트마스킹을 활용한 DP로 접근하고 싶습니다. 상태를 dp[current_city][visited_bitmask]로 정의할 때, 점화식 수립을 위한 힌트를 주세요. (코드는 주지 마세요.)",
    problem_algorithms=["Dynamic Programming", "Bitmasking", "TSP"]
)

# 결과:
{
    "text_length": 120,
    "word_count": 25,
    "sentence_count": 3,
    "clarity": {
        "has_specific_values": True,  # "N이 16 이하", "dp[current_city][visited_bitmask]"
        "specific_value_count": 2
    },
    "examples": {
        "has_examples": False,
        "example_count": 0
    },
    "rules": {
        "has_xml_tags": False,
        "has_constraints": True,  # "N이 16 이하", "코드는 주지 마세요"
        "constraint_count": 2
    },
    "context": {
        "has_context_reference": False,
        "context_reference_count": 0
    },
    "problem_relevance": {
        "technical_term_count": 3  # "TSP", "비트마스킹", "DP"
    }
}
```

### 예시 2: "제안해주신 점화식을 바탕으로 Python 코드를 작성해 주세요"

```python
metrics = calculate_all_metrics(
    "힌트 감사합니다. 제안해주신 점화식을 바탕으로 Python 코드를 작성해 주세요.\n\n[제약 조건]\n1. 시간 복잡도는 O(N^2 * 2^N)을 넘지 않아야 합니다.\n2. sys.stdin.readline을 사용하여 입력 속도를 최적화해 주세요.",
    problem_algorithms=["Dynamic Programming", "Bitmasking"]
)

# 결과:
{
    "text_length": 150,
    "word_count": 30,
    "sentence_count": 4,
    "clarity": {
        "has_specific_values": True,  # "O(N^2 * 2^N)", "sys.stdin.readline"
        "specific_value_count": 2
    },
    "examples": {
        "has_examples": False,
        "example_count": 0
    },
    "rules": {
        "has_xml_tags": False,
        "has_constraints": True,  # "시간 복잡도", "입력 속도"
        "constraint_count": 2,
        "has_structured_format": True  # 번호 매기기
    },
    "context": {
        "has_context_reference": True,  # "제안해주신 점화식"
        "context_reference_count": 1
    },
    "problem_relevance": {
        "technical_term_count": 2  # "Python", "시간 복잡도"
    }
}
```

---

## 🎯 개선 효과

### 1. 의도 분류 일관성 향상

**이전:**
- "점화식 수립을 위한 힌트를 주세요" → `[RULE_SETTING, HINT_OR_QUERY]` (복수 선택)
- 평가 노드 2개 실행 → 점수 평균 계산

**개선 후:**
- "점화식 수립을 위한 힌트를 주세요" → `[HINT_OR_QUERY]` (단일 선택, 우선순위 기반)
- 평가 노드 1개 실행 → 일관된 평가

### 2. 평가 기준 구체화

**이전:**
- LLM이 주관적으로 평가
- 점수 범위별 기준 불명확

**개선 후:**
- 정량적 메트릭 제공으로 객관성 향상
- 점수 범위별 구체적 기준 명시
- LLM이 메트릭을 참고하여 일관된 평가

---

## 🔗 관련 파일

- `app/domain/langgraph/nodes/turn_evaluator/analysis.py`: 의도 분류 (우선순위 기반 단일 선택)
- `app/domain/langgraph/nodes/turn_evaluator/evaluators.py`: 평가 기준 (정량적 메트릭 통합)
- `app/domain/langgraph/utils/prompt_metrics.py`: 정량적 메트릭 계산 유틸리티

---

## 📝 참고사항

### 메트릭의 역할

1. **객관적 측정값 제공**: 텍스트 분석 기반 정량적 지표
2. **LLM 평가 보조**: 메트릭을 참고하여 일관된 평가
3. **점수 범위별 기준**: 메트릭 값에 따른 점수 범위 가이드

### 메트릭 한계

- 메트릭은 객관적 측정값이지만, 맥락과 의미는 LLM이 종합적으로 판단
- 예: 단어 수가 적어도 맥락상 명확한 경우 높은 점수 가능
- 메트릭은 "참고용"이며, 최종 평가는 LLM이 종합적으로 수행

### 우선순위 규칙

- 코드 생성이 목적이면 항상 GENERATION 우선
- 여러 의도가 섞여 있어도 가장 명확한 목적의 의도 선택
- 예: "코드를 작성하고 최적화해주세요" → GENERATION (코드 생성이 최우선 목적)

