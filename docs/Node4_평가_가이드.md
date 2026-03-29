# Node4 평가 가이드

> **최종 통합일**: 2026-03-27 | **원본**: Node4_Evaluation_Flow_Scenario.md, Node4_Evaluation_Input_Output_Guide.md, Node4_Intent_Analysis_vs_Evaluation.md

---

## 1. 의도 분석 vs 평가 역할

Node4(Turn Evaluator)에서 **의도 분석**과 **평가**는 서로 다른 역할을 수행합니다. 의도 분석은 메트릭 없이 분류만 하고, 실제 프롬프트 품질 평가는 공통 턴 평가에서 메트릭과 루브릭을 사용합니다.

### 1.1 의도 분석 — `intent_analysis()`

| 항목 | 내용 |
|------|------|
| **역할** | 의도 **분류(Classification)** — 평가가 아님 |
| **위치** | `app/domain/langgraph/nodes/turn_evaluator/analysis.py` |
| **기능** | 사용자 프롬프트를 8가지 의도 중에서 분류 |
| **메트릭** | 사용하지 않음 (`calculate_all_metrics` 호출 없음, 문제·메트릭 정보 미포함) |

**프롬프트 성격**: 코딩 대화 의도 분류 전문가 역할, 8가지 의도 중 단일 선택, 의도 우선순위(예: GENERATION 최우선 → OPTIMIZATION → DEBUGGING …).

**출력 예시**:

```python
{
    "intent_types": ["GENERATION"],
    "intent_confidence": 0.95,
}
```

### 1.2 공통 턴 평가 — `_evaluate_turn()`

| 항목 | 내용 |
|------|------|
| **역할** | 사용자 프롬프트 **품질 평가(Evaluation)** |
| **위치** | `app/domain/langgraph/nodes/turn_evaluator/evaluators.py` |
| **기능** | 5개 루브릭 기준으로 점수·근거 산출 |
| **메트릭** | 사용함 — `prepare_evaluation_input_internal()` 내부에서 `calculate_all_metrics` 등으로 계산 후 프롬프트에 포함 |

**프롬프트 성격**: 프롬프트 엔지니어링 전문가, `eval_type` 관점에서 사용자 프롬프트 평가, 문제 정보·정량 메트릭·5개 루브릭 포함.

**출력 예시**:

```python
{
    "intent": "코드 생성 요청 (Generation)",
    "score": 85.0,
    "rubrics": [...],
    "final_reasoning": "...",
}
```

### 1.3 한눈에 보는 비교

| 구분 | 의도 분석 | 공통 턴 평가 |
|------|-----------|--------------|
| **함수** | `intent_analysis()` | `_evaluate_turn()` |
| **역할** | 의도 분류 | 프롬프트 품질 평가 |
| **메트릭** | 없음 | 있음 |
| **문제 정보** | 포함하지 않음 | 포함 |
| **기준** | 의도 우선순위 규칙 | 5개 루브릭 |
| **출력** | `intent_types`, `intent_confidence` | `score`, `rubrics`, `final_reasoning` |
| **평가 대상** | 전처리(분류만) | 사용자 프롬프트 품질 |

### 1.4 관계도 (분류 → 라우팅 → 평가)

```
┌─────────────────────────────────────┐
│  intent_analysis()                   │
│  - 의도 분류 (Classification)        │
│  - 메트릭: ❌  / 평가: ❌            │
│  - 출력: {intent_types, confidence}  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  intent_router()                     │
│  - 의도별 평가 함수 선택              │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  eval_generation() / … (개별 평가)    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  _evaluate_turn()                    │
│  - 공통 턴 평가 (Evaluation)         │
│  - 메트릭: ✅  / 평가: ✅            │
│  - 출력: {score, rubrics, …}         │
└─────────────────────────────────────┘
```

### 1.5 자주 묻는 질문

**Q1. 메트릭으로 의도 분석을 평가하는 구조인가?**  
**아닙니다.** 의도 분석은 메트릭을 쓰지 않습니다. 메트릭은 `prepare_evaluation_input_internal()` → `_evaluate_turn()` 경로에서만 프롬프트 품질 평가용으로 사용됩니다.

**Q2. “의도 분석에 대한 평가”는 공통 턴 평가에서만 이루어지나?**  
**의도 분석 자체는 평가가 아닙니다.** 분류 결과로 어떤 `eval_*` 함수를 탈지만 정하고, 실제 점수·루브릭 평가는 모두 `_evaluate_turn()`에서 수행됩니다. 의도 분석 단계를 따로 채점하는 단계는 없습니다.

### 1.6 핵심 정리

1. 의도 분석 = 분류 전처리, 메트릭·문제 정보 없음.  
2. 메트릭은 평가 프롬프트 준비(`prepare_evaluation_input_internal`) 및 `_evaluate_turn()`에서만 사용.  
3. 파이프라인: 의도 분석 → 라우터 → 개별 `eval_*` → `_evaluate_turn()`.

---

## 2. 평가 플로우 및 시나리오

### 2.1 전체 평가 플로우

```
1. Intent Analysis
   └─ intent_analysis()
       └─ LLM으로 8가지 의도 중 분류
          (SYSTEM_PROMPT, RULE_SETTING, GENERATION,
           OPTIMIZATION, DEBUGGING, TEST_CASE,
           HINT_OR_QUERY, FOLLOW_UP)
       └─ 이 단계에서는 메트릭 미사용, 평가(점수) 없음

2. Intent Router
   └─ intent_router()
       └─ 의도에 따라 평가 노드 선택
       └─ 다중 의도 시 병렬 실행 가능

3. 개별 평가 함수
   └─ eval_system_prompt() / eval_generation() / …
       └─ _evaluate_turn() 호출
           └─ prepare_evaluation_input_internal() → 프롬프트 생성
           └─ LLM 호출 → TurnEvaluation 파싱
           └─ 반환: {score, rubrics, final_reasoning}

4. Turn Log Aggregation
   └─ aggregate_turn_log()
       └─ 평가 결과 수집, 평균 점수, turn_log 생성
```

### 2.2 핵심 함수 역할

**`prepare_evaluation_input_internal`** (`evaluators.py` 49–111줄 근처)

- 평가용 system/user 프롬프트 생성.
- 문제 정보 추출·포맷, `calculate_all_metrics`로 정량 메트릭, 5개 루브릭·`criteria` 반영.
- 호출: `_evaluate_turn()` 내부, (레거시) `create_evaluation_chain()` 내부.

**`_evaluate_turn`** (`evaluators.py` 232–244줄 근처)

- 공통 턴 평가 실행: 위 프롬프트 생성 → LLM(토큰 추적) → `TurnEvaluation` 파싱 → `score`, `rubrics`, `final_reasoning` 반환.
- 호출: `eval_system_prompt`, `eval_rule_setting`, `eval_generation`, `eval_optimization`, `eval_debugging`, `eval_test_case`, `eval_hint_query`, `eval_follow_up` 등 모든 개별 평가 함수.

### 2.3 함수 호출 관계도

```
┌─────────────────────────────────────────┐
│  개별 평가 함수들                        │
│  (eval_system_prompt, eval_generation,  │
│   eval_optimization, …)                 │
└──────────────┬──────────────────────────┘
               │ 호출
               ▼
┌─────────────────────────────────────────┐
│  _evaluate_turn()                         │
│  - LLM 호출 및 파싱                      │
└──────────────┬──────────────────────────┘
               │ 호출
               ▼
┌─────────────────────────────────────────┐
│  prepare_evaluation_input_internal()    │
│  - 문제 정보 + 메트릭 + 평가 기준         │
└─────────────────────────────────────────┘
```

### 2.4 시나리오: 단일 의도 (예: GENERATION)

```
1. Intent Analysis → 의도: ["GENERATION"]
2. Intent Router → ["eval_generation"]
3. eval_generation()
   └─ _evaluate_turn()
       ├─ eval_type: "코드 생성 요청 (Generation)"
       ├─ criteria: "원하는 기능의 입출력 예시를 제공하고, 구현 조건을 상세히 기술했는가?"
       └─ prepare_evaluation_input_internal → LLM → 파싱
       └─ 반환: {score: 85, rubrics: [...], final_reasoning: "..."}
4. aggregate_turn_log() → turn_score: 85
```

### 2.5 시나리오: 다중 의도 (예: GENERATION + OPTIMIZATION)

```
1. Intent Analysis → 의도: ["GENERATION", "OPTIMIZATION"]
2. Intent Router → ["eval_generation", "eval_optimization"]
3. LangGraph 병렬 실행
   ├─ eval_generation → _evaluate_turn (eval_type: Generation) → 예: score 85
   └─ eval_optimization → _evaluate_turn (eval_type: Optimization) → 예: score 70
4. aggregate_turn_log() → turn_score: (85 + 70) / 2 = 77.5
```

### 2.6 프롬프트 구조 (`prepare_evaluation_input_internal`)

**System 프롬프트**

1. Role: 프롬프트 엔지니어링 전문가  
2. 문제 정보(있을 때): 제목, 필수 알고리즘  
3. 정량 메트릭(참고): 텍스트 길이, 단어·문장 수, 구체적 값/예시/규칙/문맥·문제 적절성·코드 블록 관련 지표 등  
4. 평가 기준 5 루브릭 — 4번 Rules는 `criteria`로 의도별 동적 삽입  

**User 프롬프트**

```
[사용자 프롬프트]
{human_message}

[AI 응답 (참고용)]
{ai_message}

위 사용자 프롬프트를 '{eval_type}' 관점에서 평가하세요.
```

### 2.7 평가 기준 — 5개 루브릭

1. **명확성 (Clarity)** — 단어·문장 수, 구체적 값 개수 등 메트릭과 90–100 / 70–89 / 50–69 / 0–49 구간 기준.  
2. **문제 적절성 (Problem Relevance)** — 기술 용어 개수, 알고리즘 명시 여부.  
3. **예시 (Examples)** — 예시 유무·개수, 입출력·엣지 케이스.  
4. **규칙 (Rules)** — XML 태그·제약·구조화·출력 형식; **criteria**는 유형별로 다름 (예: System Prompt는 역할·범위·스타일 정의, Generation은 입출력 예시·구현 조건, Optimization은 문제 지적·목표 성능·최적화 전략 등).  
5. **문맥 (Context)** — 이전 대화 참조 횟수·구체성.

### 2.8 구현 시 참고

- **`create_evaluation_chain()`** 은 현재 사용되지 않는 레거시로 이해하면 됩니다. 실제 평가는 `_evaluate_turn()` 직접 호출.  
- 모든 `eval_*`는 동일한 프롬프트 뼈대를 쓰고 **`eval_type`과 `criteria`** 만 바뀝니다.

---

## 3. 입력·출력 및 저장 스키마

Node4는 사용자 프롬프트와 AI 응답을 평가한 뒤 `prompt_evaluations` 테이블의 `details`(JSONB)에 저장합니다.

### 3.1 데이터베이스 — `prompt_evaluations`

```sql
CREATE TABLE prompt_evaluations (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES prompt_sessions(id) ON DELETE CASCADE,
    turn INTEGER,  -- TURN_EVAL: NOT NULL, HOLISTIC_FLOW: NULL
    evaluation_type evaluation_type_enum NOT NULL,  -- 'TURN_EVAL' | 'HOLISTIC_FLOW'
    details JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT check_valid_turn_logic CHECK (
        (evaluation_type::text = 'HOLISTIC_FLOW' AND turn IS NULL) OR
        (evaluation_type::text = 'TURN_EVAL' AND turn IS NOT NULL)
    ),
    UNIQUE(session_id, turn, evaluation_type) WHERE evaluation_type = 'TURN_EVAL',
    UNIQUE(session_id) WHERE evaluation_type = 'HOLISTIC_FLOW'
);
```

### 3.2 노드 입력 — `EvalTurnState` (TypedDict 요약)

```python
{
    "session_id": str,
    "turn": int,
    "human_message": str,
    "ai_message": str,
    "problem_context": Optional[Dict[str, Any]],
    "is_guardrail_failed": bool,
    "guardrail_message": Optional[str],
    "intent_types": Optional[List[str]],
    "intent_confidence": float,  # 0.0–1.0
    # … 기타 필드
}
```

**입력 예시**

```python
state = {
    "session_id": "session_1",
    "turn": 1,
    "human_message": "외판원 순회 문제를 풀기 위해 비트마스킹 DP 코드를 작성해주세요.",
    "ai_message": "네, 비트마스킹 DP를 사용한 외판원 순회 코드를 작성해드리겠습니다.",
    "problem_context": {
        "basic_info": {"title": "외판원 순회 (TSP)", "problem_id": "2098"},
        "ai_guide": {"key_algorithms": ["DP", "Bitmasking"]},
    },
    "is_guardrail_failed": False,
    "guardrail_message": None,
    "intent_types": ["generation"],
    "intent_confidence": 0.95,
}
```

### 3.3 평가 함수 반환 형식

각 `eval_generation`, `eval_optimization` 등은 키 이름이 의도별로 다르지만 구조는 동일합니다.

```python
{
    "generation_eval": {  # 또는 optimization_eval, debugging_eval 등
        "intent": str,
        "score": float,      # 0–100
        "average": float,    # 보통 score와 동일
        "rubrics": [
            {
                "criterion": str,
                "score": float,
                "reasoning": str,
            },
            # 5개: 명확성, 문제 적절성, 예시, 규칙, 문맥
        ],
        "final_reasoning": str,
        "eval_tokens": {     # 선택
            "prompt_tokens": int,
            "completion_tokens": int,
            "total_tokens": int,
        },
    }
}
```

### 3.4 저장 형식 — `prompt_evaluations.details`

`evaluation_storage_service.save_turn_evaluation` 등이 쓰는 JSONB 구조:

```python
{
    "score": float,
    "analysis": str,  # comprehensive_reasoning 또는 final_reasoning
    "intent": str,
    "intent_types": List[str],
    "rubrics": List[Dict],
    "evaluations": Dict[str, Any],
    "detailed_feedback": List[Dict],
    "turn_score": float,
    "is_guardrail_failed": bool,
    "guardrail_message": Optional[str],
}
```

`details`에 넣기 전 단계에서의 `turn_log` 집계 흐름은 `aggregate_turn_log` 이후 `prompt_evaluation_details`, `evaluations`, `detailed_feedback` 등으로 묶입니다.

### 3.5 데이터 흐름

```
Node 4 호출
  → EvalTurnState
  → eval_*(state) → {"*_eval": {...}}
  → aggregate_turn_log → turn_log (prompt_evaluation_details, evaluations, …)
  → evaluation_storage_service
  → prompt_evaluations.details (JSONB)
```

### 3.6 필수 필드 체크리스트

**평가 함수 반환**

- `intent`, `score`, `rubrics`(5개), 각 rubric의 `criterion`·`score`·`reasoning`, `final_reasoning`

**저장 `details`**

- `score`, `analysis`, `intent`, `intent_types`, `rubrics`, `evaluations`, `detailed_feedback`, `turn_score`, `is_guardrail_failed`

### 3.7 주의사항

1. 각 rubric의 **`reasoning`** 과 전체 **`final_reasoning`** 은 필수.  
2. 점수는 **0–100**.  
3. 루브릭은 항상 **5개**.  
4. LLM JSON 파싱 시 필드명은 **`reasoning`** (`reason` 아님).

### 3.8 테스트 참고

- 예시 메시지: `tests/test_messages_examples.json`  
- 단위 테스트 참고: `tests/test_node4_unit.py`  

```python
with open("tests/test_messages_examples.json", "r", encoding="utf-8") as f:
    examples = json.load(f)
test_case = examples["test_cases"][0]
problem_context = examples["problem_context_example"]
state = {
    "session_id": "test_session",
    "turn": 1,
    "human_message": test_case["human_message"],
    "ai_message": test_case["ai_message"],
    "problem_context": problem_context,
    "is_guardrail_failed": False,
    "guardrail_message": None,
    "intent_types": None,
    "intent_confidence": 0.0,
}
result = await eval_generation(state)
assert "generation_eval" in result
assert len(result["generation_eval"]["rubrics"]) == 5
```

직접 JSON으로 상태를 만들 때는 `EvalTurnState`와 동일한 키(`session_id`, `turn`, `human_message`, `ai_message`, `problem_context`, 가드레일·의도 필드 등)를 맞추면 됩니다.

---

*본 문서는 상기 세 원본을 통합·중복 제거하여 작성하였습니다.*
