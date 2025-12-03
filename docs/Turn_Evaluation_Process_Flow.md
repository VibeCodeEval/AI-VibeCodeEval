# Turn Evaluation 평가 과정 흐름

## 📋 개요

의도 분석 후 5가지 평가 기준(명확성, 문제 적절성, 예시, 규칙, 문맥)이 어떻게 평가되는지 설명합니다.

---

## 🔄 전체 평가 흐름

```
START
  ↓
[4.0] Intent Analysis (의도 분석)
  - 8가지 의도 중 복수 선택 가능
  - 예: ["HINT_OR_QUERY", "GENERATION"]
  ↓
[4.0.1] Intent Router (의도별 라우팅)
  - 선택된 의도에 따라 평가 노드로 분기
  - 예: ["eval_hint_query", "eval_generation"]
  ↓
[4.1~4.8] 개별 평가 노드 (병렬 실행 가능)
  - 각 의도별 평가 노드 실행
  - 예: eval_hint_query, eval_generation
  ↓
[4.3] Summarize Answer (AI 답변 요약)
  ↓
[4.4] Aggregate Turn Log (턴 로그 집계)
  ↓
END
```

---

## 📊 5가지 평가 기준이 적용되는 과정

### 1. 의도 분석 (Intent Analysis)

**위치**: `app/domain/langgraph/nodes/turn_evaluator/analysis.py`

```python
async def intent_analysis(state: EvalTurnState) -> Dict[str, Any]:
    """
    8가지 의도 중 복수 선택
    - SYSTEM_PROMPT
    - RULE_SETTING
    - GENERATION
    - OPTIMIZATION
    - DEBUGGING
    - TEST_CASE
    - HINT_OR_QUERY
    - FOLLOW_UP
    """
```

**결과**: `intent_types` 리스트 반환
- 예: `["HINT_OR_QUERY"]`

---

### 2. 의도별 라우팅 (Intent Router)

**위치**: `app/domain/langgraph/nodes/turn_evaluator/routers.py`

```python
def intent_router(state: EvalTurnState) -> list[str]:
    """
    의도에 따라 평가 노드로 분기
    - HINT_OR_QUERY → eval_hint_query
    - GENERATION → eval_generation
    - ...
    """
```

**결과**: 평가할 노드 리스트 반환
- 예: `["eval_hint_query"]`

---

### 3. 개별 평가 노드 실행

**위치**: `app/domain/langgraph/nodes/turn_evaluator/evaluators.py`

각 의도별 평가 노드가 `_evaluate_turn()` 함수를 호출합니다:

```python
async def eval_hint_query(state: EvalTurnState) -> Dict[str, Any]:
    """4.H: Hint/Query 평가"""
    result = await _evaluate_turn(
        state,
        "힌트/질의 요청 (Hint/Query)",
        "자신의 사고 과정(Chain of Thought)을 공유하고 막힌 부분을 구체적으로 질문했는가?"
    )
    return {"hint_query_eval": result}
```

---

### 4. `_evaluate_turn()` 함수 내부

**핵심 평가 로직**:

```python
async def _evaluate_turn(state: EvalTurnState, eval_type: str, criteria: str):
    """
    1. 평가 Chain 생성 (create_evaluation_chain)
    2. 프롬프트 준비 (prepare_evaluation_input_internal)
       - 5가지 평가 기준 포함
    3. LLM 호출
    4. TurnEvaluation 객체 반환
    """
```

---

### 5. 프롬프트 생성 (`prepare_evaluation_input_internal`)

**위치**: `app/domain/langgraph/nodes/turn_evaluator/evaluators.py:14`

**5가지 평가 기준이 포함된 시스템 프롬프트 생성**:

```python
system_prompt = f"""당신은 '프롬프트 엔지니어링' 전문가입니다.
사용자가 작성한 프롬프트가 '{eval_type}' 의도를 얼마나 잘 전달하고 있는지 평가하세요.

평가 기준 (Claude Prompt Engineering):
1. **명확성 (Clarity)**: 요청이 모호하지 않고 구체적인가?
2. **문제 적절성 (Problem Relevance)**: 
   - 요청이 문제 특성({algorithms_display})에 적합한가?
   - 필수 개념을 언급했는가?
3. **예시 (Examples)**: 원하는 입출력 예시나 상황을 제공했는가?
4. **규칙 (Rules)**: {criteria} (XML 태그 사용, 제약조건 명시 등)
5. **문맥 (Context)**: 이전 대화나 배경 지식을 적절히 활용했는가?

위 기준을 바탕으로 0-100점 사이의 점수를 부여하고, 상세한 루브릭과 추론을 제공하세요."""
```

---

### 6. LLM 평가 및 결과 반환

**LLM이 한 번에 5가지 기준을 모두 평가**:

```python
# TurnEvaluation 모델 구조
class TurnEvaluation(BaseModel):
    intent: str  # 의도
    score: float  # 전체 점수 (0-100)
    rubrics: list[Rubric]  # 5가지 기준별 점수 및 근거
    final_reasoning: str  # 종합 평가 근거

class Rubric(BaseModel):
    criterion: str  # 평가 기준 (명확성, 문제 적절성, 예시, 규칙, 문맥)
    score: float  # 해당 기준의 점수 (0-100)
    reasoning: str  # 평가 근거
```

**반환 예시**:
```json
{
  "intent": "hint_query_eval",
  "score": 85.5,
  "rubrics": [
    {
      "criterion": "명확성 (Clarity)",
      "score": 90,
      "reasoning": "요청이 명확합니다."
    },
    {
      "criterion": "문제 적절성 (Problem Relevance)",
      "score": 80,
      "reasoning": "문제와 관련이 있습니다."
    },
    {
      "criterion": "예시 (Examples)",
      "score": 0,
      "reasoning": "예시가 없습니다."
    },
    {
      "criterion": "규칙 (Rules)",
      "score": 0,
      "reasoning": "규칙이 없습니다."
    },
    {
      "criterion": "문맥 (Context)",
      "score": 0,
      "reasoning": "문맥이 없습니다."
    }
  ],
  "final_reasoning": "전체 평가 근거..."
}
```

---

## 🔍 핵심 포인트

### 1. **5가지 기준은 한 번에 평가됩니다**
- 각 의도별 평가 노드에서 **한 번의 LLM 호출**로 5가지 기준을 모두 평가
- 각 기준을 개별적으로 평가하는 것이 아님

### 2. **의도별로 다른 평가 노드 실행**
- Intent Router가 선택된 의도에 따라 해당 평가 노드만 실행
- 예: `HINT_OR_QUERY` 의도 → `eval_hint_query` 노드만 실행

### 3. **복수 의도 시 병렬 실행**
- 여러 의도가 선택되면 해당 평가 노드들이 병렬로 실행
- 예: `["HINT_OR_QUERY", "GENERATION"]` → `eval_hint_query`와 `eval_generation` 병렬 실행

### 4. **각 평가 노드는 동일한 5가지 기준 사용**
- 모든 의도별 평가 노드가 동일한 5가지 기준(명확성, 문제 적절성, 예시, 규칙, 문맥)을 사용
- 다만 `criteria` 파라미터로 의도별 특화 설명 추가

### 5. **점수 계산**
- 각 Rubric의 점수는 0-100점
- 전체 `score`는 LLM이 5가지 기준을 종합하여 계산 (0-100점)

---

## 📝 예시: "DP에 대해 알려줘" 평가 과정

1. **Intent Analysis**
   - 의도: `["HINT_OR_QUERY"]`

2. **Intent Router**
   - 평가 노드: `["eval_hint_query"]`

3. **eval_hint_query 실행**
   - `_evaluate_turn()` 호출
   - 프롬프트에 5가지 기준 포함
   - LLM이 한 번에 5가지 기준 평가

4. **결과 반환**
   ```json
   {
     "score": 4,
     "rubrics": [
       {"criterion": "명확성", "score": 10},
       {"criterion": "문제 적절성", "score": 10},
       {"criterion": "예시", "score": 0},
       {"criterion": "규칙", "score": 0},
       {"criterion": "문맥", "score": 0}
     ]
   }
   ```

5. **Aggregate Turn Log**
   - 모든 평가 결과 집계
   - 최종 턴 점수 계산

---

## 🔗 관련 파일

- `app/domain/langgraph/nodes/turn_evaluator/analysis.py`: Intent Analysis
- `app/domain/langgraph/nodes/turn_evaluator/routers.py`: Intent Router
- `app/domain/langgraph/nodes/turn_evaluator/evaluators.py`: 개별 평가 노드 및 평가 로직
- `app/domain/langgraph/nodes/turn_evaluator/aggregation.py`: 턴 로그 집계
- `app/domain/langgraph/subgraph_eval_turn.py`: 전체 평가 서브그래프 구조


