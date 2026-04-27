# Node4 평가 가이드

> **최종 통합일**: 2026-03-27 | **최종 갱신**: 2026-04-05 (V3.0 Intent-Rubric Gate 도입, 의도 체계 재정의)  
> **원본**: Node4_Evaluation_Flow_Scenario.md, Node4_Evaluation_Input_Output_Guide.md, Node4_Intent_Analysis_vs_Evaluation.md

---

## 1. 의도 분석 vs 평가 역할

Node4(Turn Evaluator)에서 **의도 분석**과 **평가**는 서로 다른 역할을 수행합니다. 의도 분석은 메트릭 없이 분류만 하고, 실제 프롬프트 품질 평가는 V3.0 Intent-Rubric Gate 기반으로 루브릭을 동적으로 선택하여 수행합니다.

### 1.1 의도 분류 체계 (V3.0 기준)

| 의도 | 설명 |
|------|------|
| **CREATION** | 새 코드/함수/클래스 생성 요청 |
| **SETTING** | 시스템 설정, 제약 조건, 환경 구성 |
| **REFINEMENT** | 기존 코드 개선·최적화 |
| **DEBUGGING** | 오류 수정, 버그 추적 |
| **EXPLORATION** | 개념 이해, 설명 요청, 탐색 |
| **FOLLOW_UP** | 이전 대화 이어받기, 추가 질문 |

> ⚠️ V3.0 이전 8개 의도 (SYSTEM_PROMPT, RULE_SETTING, GENERATION, OPTIMIZATION, TEST_CASE, HINT_OR_QUERY 등)에서 6개로 통합됨.

### 1.2 의도 분석 — `intent_analysis()`

| 항목 | 내용 |
|------|------|
| **역할** | 의도 **분류(Classification)** — 평가가 아님 |
| **위치** | `app/domain/langgraph/nodes/eval_turn/analysis.py` |
| **기능** | 사용자 프롬프트를 6가지 의도 중에서 분류 |
| **메트릭** | 사용하지 않음 |

**출력 예시**:

```python
{
    "intent_types": ["CREATION"],
    "intent_confidence": 0.95,
}
```

### 1.3 공통 턴 평가 — `_evaluate_turn()` (V3.0)

| 항목 | 내용 |
|------|------|
| **역할** | 사용자 프롬프트 **품질 평가(Evaluation)** |
| **위치** | `app/domain/langgraph/nodes/eval_turn/evaluators.py` |
| **기능** | Intent-Rubric Gate로 의도별 적용 루브릭 선택 후 채점 |
| **메트릭** | 사용함 — `prepare_evaluation_input_internal()` 내부에서 `calculate_all_metrics` 등 계산 |
| **출력 모델** | `EvalTurnV30Output` (Pydantic) |

**출력 예시 (V3.0)**:

```python
{
    "turn_score": 4,          # 1~5 정수
    "rubric_breakdown": {
        "R1_logic_efficiency": 4,
        "R2_clarity_completeness": 5,
        "R3_structure_examples": 3,
    },
    "applied_rubrics": ["R1_logic_efficiency", "R2_clarity_completeness", "R3_structure_examples"],
    "feedback_summary": "알고리즘 제약(R1)과 명확한 요건(R2)이 잘 작성됨. 예시 추가 권장.",
}
```

### 1.4 한눈에 보는 비교

| 구분 | 의도 분석 | 공통 턴 평가 (V3.0) |
|------|-----------|---------------------|
| **함수** | `intent_analysis()` | `_evaluate_turn()` |
| **역할** | 의도 분류 | 프롬프트 품질 평가 |
| **메트릭** | 없음 | 있음 |
| **기준** | 의도 우선순위 규칙 | 4개 루브릭 (의도별 Gate) |
| **출력** | `intent_types`, `intent_confidence` | `turn_score`, `rubric_breakdown`, `applied_rubrics`, `feedback_summary` |

### 1.5 관계도 (분류 → 루브릭 게이팅 → 평가)

```
┌─────────────────────────────────────┐
│  intent_analysis()                   │
│  - 의도 분류 (6개 중 1개 선택)        │
│  - 메트릭: ❌  / 평가: ❌            │
│  - 출력: {intent_types, confidence}  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Intent-Rubric Gate                  │
│  - 의도 → 적용 루브릭 결정           │
│  - turn_score 산식 결정              │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  _evaluate_turn() (V3.0)             │
│  - 공통 턴 평가 (Evaluation)         │
│  - 메트릭: ✅  / 평가: ✅            │
│  - 출력: {turn_score, rubric_breakdown, applied_rubrics, feedback_summary} │
└─────────────────────────────────────┘
```

### 1.6 자주 묻는 질문

**Q1. 메트릭으로 의도 분석을 평가하는 구조인가?**  
**아닙니다.** 의도 분석은 메트릭을 쓰지 않습니다. 메트릭은 `_evaluate_turn()` 경로에서만 프롬프트 품질 평가용으로 사용됩니다.

**Q2. V3.0에서 루브릭이 의도별로 다르게 적용되는가?**  
**예.** `eval_turn.yaml`의 `intent_rubric_gates` 섹션에 의도별 적용 루브릭과 `turn_score` 산식이 정의되어 있습니다. FOLLOW_UP은 R4만, DEBUGGING은 R2에 2배 가중치 등.

### 1.7 핵심 정리

1. 의도 분석 = 분류 전처리, 메트릭·문제 정보 없음.  
2. V3.0: 의도 → 루브릭 게이트 → `turn_score`(1~5) + `rubric_breakdown` + `applied_rubrics`.  
3. N8 다중 에이전트 토론이 N4의 `rubric_breakdown`을 핵심 증거로 활용.

---

## 2. V3.0 Intent-Rubric Gate

### 2.1 4대 핵심 루브릭

| ID | 이름 | 설명 | 핵심 감점 포인트 |
|----|------|------|-----------------|
| **R1** | Logic & Efficiency | 논리적 완결성 및 효율성 | 단순 변경 요청 (이유·제약 없음) |
| **R2** | Clarity & Completeness | 문제 정의의 명확성과 완전성 | 에러 로그 없이 "고쳐줘", 추상적 형용사 |
| **R3** | Structure & Examples | 구조적 통제 및 예시 활용 | XML 태그·Few-shot 없음, 출력 형식 미지정 |
| **R4-local** | Context Maintenance (로컬) | 직전 턴 맥락 유지 및 피드백 반영 | 같은 오류 반복, 이전 지시 무시 |

> R4는 **로컬(N4)**과 **글로벌(N8)** 두 층위로 평가됨.  
> N4의 R4는 직전 1~2 턴 참조, N8의 R4는 전체 세션 궤적 분석.

### 2.2 의도별 루브릭 적용 매트릭스

| 의도 | R1 | R2 | R3 | R4 | turn_score 산식 |
|------|:--:|:--:|:--:|:--:|-----------------|
| CREATION | ✅ | ✅ | ✅ | ✅ | `avg(R1, R2, R3, R4)` |
| SETTING | ✅ | ✅ | ✅ | ✅ | `avg(R1, R2, R3, R4)` |
| REFINEMENT | ✅ | ✅ | ✅ | ✅ | `avg(R1, R2, R3, R4)` |
| DEBUGGING | ✅ | ✅×2 | ✅ | ✅ | `(R1 + R2×2 + R3 + R4) / 5` |
| EXPLORATION | ✅ | ✅ | ❌ | ✅ | `avg(R1, R2, R4)` |
| FOLLOW_UP | ❌ | ❌ | ❌ | ✅ | `R4` |

### 2.3 점수 등급 기준 (1~5)

| 점수 | 등급 | 기준 |
|------|------|------|
| 5 | S | 이유·효율성(R1), 명확한 로그·조건(R2), 포맷·예시(R3)로 AI를 완벽 통제 |
| 4 | A | 지시가 명확하고 대상이 분명함 |
| 3 | B | 안전하지만 수동적. 단순 기능/수정 지시. 예시·통제(R3) 부재 |
| 2 | C | 의도는 있으나 명확성(R2)이나 맥락(R4)이 심각하게 누락 |
| 1 | F | 무의미, 정보 0%, 맥락 이탈 |

---

## 3. 평가 플로우 및 시나리오

### 3.1 전체 평가 플로우 (V3.0)

```
1. Intent Analysis
   └─ intent_analysis()
       └─ LLM으로 6가지 의도 중 분류
          (CREATION, SETTING, REFINEMENT, DEBUGGING, EXPLORATION, FOLLOW_UP)
       └─ 이 단계에서는 메트릭 미사용, 평가(점수) 없음

2. Intent-Rubric Gate
   └─ eval_turn.yaml의 intent_rubric_gates 참조
       └─ 적용 루브릭 목록 결정
       └─ turn_score 산식 결정

3. _evaluate_turn() (V3.0)
   └─ prepare_evaluation_input_internal() → eval_turn.yaml 템플릿 렌더링
       └─ previous_turns_summary 주입 (이전 턴 요약)
       └─ 메트릭: word_count, has_examples, xml_tag_count 등
   └─ LLM 호출 (EvalTurnV30Output 파싱)
   └─ 반환: {turn_score, rubric_breakdown, applied_rubrics, feedback_summary}

4. Turn Log Aggregation (n4_eval_turn_guard.py)
   └─ Redis 저장: turn_logs:{session_id}:{turn}
       └─ prompt_evaluation_details.rubric_breakdown (dict)
       └─ prompt_evaluation_details.applied_rubrics (list)
   └─ PostgreSQL: prompt_evaluations (evaluation_type='TURN_EVAL')
```

### 3.2 핵심 함수 역할

**`prepare_evaluation_input_internal`** (`evaluators.py`)

- `eval_turn.yaml` 템플릿 렌더링: `eval_type`, `problem_info_section`, `metrics_section`, `word_count`, `has_examples`, `xml_tag_count`, `previous_turns_summary` 주입.
- `calculate_all_metrics`로 정량 메트릭 계산.

**`_evaluate_turn`** (`evaluators.py`)

- V3.0: `EvalTurnV30Output` 모델로 LLM 응답 파싱.
- `turn_score`, `rubric_breakdown`, `applied_rubrics`, `feedback_summary` 추출.

### 3.3 시나리오: CREATION 의도

```
1. Intent Analysis → 의도: ["CREATION"]
2. Gate → R1 + R2 + R3 + R4 적용, avg(R1,R2,R3,R4)
3. _evaluate_turn()
   └─ eval_type: "CREATION"
   └─ 루브릭 4개 모두 평가
   └─ 반환: {turn_score: 4, rubric_breakdown: {R1:4, R2:5, R3:3, R4:4}, ...}
4. aggregate_turn_log → turn_score: 4
```

### 3.4 시나리오: DEBUGGING 의도 (R2 가중치 2배)

```
1. Intent Analysis → 의도: ["DEBUGGING"]
2. Gate → R2 ×2 가중치, (R1 + R2×2 + R3 + R4) / 5
3. _evaluate_turn()
   └─ eval_type: "DEBUGGING"
   └─ R2 (에러 로그 누락 시 최하점)
   └─ 반환: {turn_score: 2, rubric_breakdown: {R1:3, R2:1, R3:2, R4:3}, ...}
   └─ score = (3 + 1×2 + 2 + 3) / 5 = 2.0
4. feedback_summary: "에러 로그·명확한 지시(R2) 누락 — 불성실한 프롬프트"
```

### 3.5 시나리오: FOLLOW_UP 의도 (R4만)

```
1. Intent Analysis → 의도: ["FOLLOW_UP"]
2. Gate → R4만 적용, turn_score = R4
3. _evaluate_turn()
   └─ eval_type: "FOLLOW_UP"
   └─ 오직 이전 맥락 반영 여부만 평가
   └─ 반환: {turn_score: 5, rubric_breakdown: {R4:5}, applied_rubrics: ["R4"], ...}
```

---

## 4. 입력·출력 및 저장 스키마

Node4는 사용자 프롬프트와 AI 응답을 평가한 뒤 Redis와 `prompt_evaluations` 테이블에 저장합니다.

### 4.1 데이터베이스 — `prompt_evaluations`

```sql
CREATE TABLE prompt_evaluations (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES prompt_sessions(id) ON DELETE CASCADE,
    turn INTEGER,  -- TURN_EVAL: NOT NULL
    evaluation_type evaluation_type_enum NOT NULL,  -- 'TURN_EVAL'
    details JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(session_id, turn, evaluation_type) WHERE evaluation_type = 'TURN_EVAL'
);
```

### 4.2 Redis 저장 스키마 (V3.0)

```json
{
  "turn": 3,
  "session_id": "session_1000",
  "prompt_evaluation_details": {
    "intent": "DEBUGGING",
    "turn_score": 2,
    "rubric_breakdown": {
      "R1_logic_efficiency": 3,
      "R2_clarity_completeness": 1,
      "R3_structure_examples": 2,
      "R4_context_maintenance": 3
    },
    "applied_rubrics": ["R1_logic_efficiency", "R2_clarity_completeness", "R3_structure_examples", "R4_context_maintenance"],
    "feedback_summary": "에러 로그 없이 '고쳐줘'만 작성 — R2 심각 결함"
  }
}
```

### 4.3 노드 입력 — `EvalTurnState` 주요 필드

```python
{
    "session_id": str,
    "turn": int,
    "human_message": str,
    "ai_message": str,
    "problem_context": Optional[Dict[str, Any]],
    "is_guardrail_failed": bool,
    "previous_turns_summary": Optional[str],  # N4에서 자동 생성
}
```

### 4.4 V3.0 Pydantic 모델 — `EvalTurnV30Output`

```python
class EvalTurnV30Output(BaseModel):
    turn_score: int                      # 1~5
    rubric_breakdown: Dict[str, int]     # {"R1_...": 1~5, ...}
    applied_rubrics: List[str]           # ["R1_...", "R2_..."]
    feedback_summary: str
```

### 4.5 데이터 흐름

```
Node 4 호출
  → EvalTurnState
  → intent_analysis() → intent_types
  → Intent-Rubric Gate → 적용 루브릭 결정
  → _evaluate_turn() → EvalTurnV30Output
  → aggregate_turn_log → turn_log
  → Redis: turn_logs:{session_id}:{turn}
  → PostgreSQL: prompt_evaluations.details (JSONB)
  → N8 Holistic Debate에서 Redis turn_logs 직접 재조회하여 토론 컨텍스트로 활용
```

### 4.6 주의사항

1. **V3.0 출력 스키마**: `turn_score`(1~5 정수), `rubric_breakdown`(dict), `applied_rubrics`(list) — 구버전 `score`(0~100), `rubrics`(list) 형식 아님.  
2. **previous_turns_summary**: N4에서 자동으로 이전 턴 요약을 생성하여 YAML 템플릿에 주입.  
3. **N8 연동**: `rubric_breakdown` 키가 V3.0 증거 자료로 N8 토론 컨텍스트에서 최우선 참조됨 (`subgraph_debate.py`의 `_build_base_context`).
4. **`EvalTurnV21Output`** 은 하위 호환성을 위해 보존; 실제 평가는 V30 사용.

---

*본 문서는 상기 세 원본을 통합·중복 제거하여 작성하고, 2026-04-05 V3.0 루브릭 시스템으로 전면 갱신하였습니다.*
