# 4대 루브릭 V3.0 변경 계획

> **작성일**: 2026-04-05  
> **상태**: 계획 확정 / 하위 에이전트 전담 예정  
> **연계 문서**: `.maestro/RUBRIC_MIGRATION_PLAN.md` (구버전 계획 — 아래 내용으로 대체됨)

---

## 1. 배경 — 무엇이 왜 바뀌었나

### 구버전 계획 (RUBRIC_MIGRATION_PLAN.md) 요약

```
R1 (논리 효율성)   → N7 (코드 리뷰 LLM에 추가)
R2/R3 (명확성/구조) → N4 (턴별 평가에 추가)
R4 (맥락 유지)     → N8 (홀리스틱 토론에서 단독 채점)
```

### 변경 이유 및 새로운 결정

| 항목 | 구버전 | 변경 후 | 변경 이유 |
|------|--------|---------|----------|
| **R1 위치** | N7 | **N4** | R1은 "프롬프트에 알고리즘 제약을 담았는가"이므로 코드 리뷰(N7)가 아닌 프롬프트 평가(N4)가 적합. N7은 코드 자체만 심층 분석 |
| **R2/R3 위치** | N4 | **N4 (유지)** | 동일 |
| **R4 위치** | N8 단독 | **N4(로컬) + N8(글로벌)** | R4의 의미가 두 레벨로 분리됨 (아래 설명) |
| **N7 루브릭** | R1 추가 예정 | **루브릭 없음** | N7은 이미 효율성/가독성/예외처리/종합 리뷰를 하고 있음. 여기에 R1 점수를 추가하면 N4와 이중 채점 발생 |

### R4 두 레벨 분리 (핵심 결정)

```
N4 R4 (로컬 · 턴 단위)
  ── "이번 턴이 직전 턴의 맥락을 올바르게 참조했는가?"
  ── 팩트 체크 용도 (이전 대화 요약 vs 현재 지시 일치 여부)
  ── FOLLOW_UP, REFINEMENT, DEBUGGING 의도에서 필수

N8 R4 (글로벌 · 세션 전체)
  ── "세션 전체에서 학습자가 오류를 인지하고 점진적으로 향상했는가?"
  ── 7개 이상 턴의 궤적, 개선 패턴, 전략적 연속성 분석
  ── 이미 FinalVerdict.r4_context_maintenance_score로 구현됨 ✅
```

---

## 2. 확정된 아키텍처

### N4 — 의도별 루브릭 적용 행렬 (Intent-Rubric Applicability Matrix)

| 의도 | R1 논리·효율 | R2 명확성·완전성 | R3 구조·예시 | R4 맥락 유지 | turn_score 산출 |
|------|:---:|:---:|:---:|:---:|------|
| CREATION | ✅ | ✅ | ✅ | ❌ | `(R1 + R2 + R3) / 3` |
| SETTING | ❌ | ✅ | ✅ | ❌ | `(R2 + R3) / 2` |
| REFINEMENT | ✅ | ✅ | ✅ | ✅ | `(R1 + R2 + R3 + R4) / 4` |
| DEBUGGING | ✅ | ✅✅ | ❌ | ✅ | `(R1 + R2×2 + R4) / 4` |
| EXPLORATION | ✅ | ✅ | ❌ | ❌ | `(R1 + R2) / 2` |
| FOLLOW_UP | ❌ | ❌ | ❌ | ✅ | `R4 단독` |

**각 루브릭 정의**
- **R1 (논리 효율성)**: 프롬프트에 알고리즘 제약·최적화 이유를 포함했는가? (O(N), Stack 사용 이유 등)
- **R2 (명확성·완전성)**: 에러 로그·수치·구체적 조건이 있는가? 두루뭉술한 지시를 지양했는가?
- **R3 (구조·예시)**: 출력 형식(XML/JSON)을 통제하거나 Few-shot 예시를 제공했는가?
- **R4 (맥락 유지 로컬)**: 이전 대화를 올바르게 참조하고 있는가? 문맥에 없는 대상을 지칭하지 않았는가?

### N7 — 변경 없음 (루브릭 미도입)

N7은 현재 구조 유지. 코드에 대한 정성 리뷰(효율성, 가독성, 예외처리, 종합 요약)만 제공.
N8 토론 에이전트에게 "증거 자료"로 전달하는 역할.

### N8 — 현재 구현 완료 (R4 글로벌 + 홀리스틱 종합)

- `FinalVerdict.r4_context_maintenance_score` 필드: 세션 전체 궤적 기반 R4 채점 ✅
- `FinalVerdict.holistic_flow_score`: R1~R3 분포 + 코드 품질 + R4 종합 ✅
- N4 turn_logs (Redis), N5 Judge0 상세, N7 코드 리뷰를 모두 수신하는 구조 ✅

### 최종 점수 흐름

```
N4 (턴별)     → turn_score + rubric_breakdown(R1~R4) → Redis 저장 + turn_scores
N5 (Judge0)   → correctness/performance + 실행 상세 → MainGraphState
N6 (Radon CC) → code_quality_metrics → MainGraphState
N7 (코드리뷰) → code_eval_report (정성 리뷰) → MainGraphState
N8 (토론)     → N4 turn_logs(Redis) + N5/N7 상세 수신
               → R4 글로벌 채점 + holistic 종합
               → holistic_flow_score, r4_context_maintenance_score
N9 (집계)     → prompt_score = holistic_flow_score × 0.60 + aggregate_turn_score × 0.40
```

---

## 3. 완료된 작업 ✅

### Phase A: N8 컨텍스트 완전화 (2026-04-05 완료)

| 파일 | 변경 내용 | 상태 |
|------|----------|------|
| `app/domain/langgraph/states.py` | `DebateState`에 `turn_logs`, `execution_time`, `memory_used_mb`, `test_cases_passed/total`, `correctness_reasoning` 추가 | ✅ 완료 |
| `app/domain/langgraph/nodes/eval/n8_code_execution.py` | `redis_client.get_all_turn_logs(session_id)` 호출, N5 상세 필드 전달 | ✅ 완료 |
| `app/domain/langgraph/subgraph_debate.py` | `_build_base_context` 전면 개선: 턴별 대화 원문 + 평가 내용 + N5 실행 상세 포함 | ✅ 완료 |

**결과**: N8 에이전트는 이제 숫자 점수만이 아닌 전체 대화 내용, 의도, 루브릭 점수와 근거, 코드 실행 상세 등 **모든 정보**를 받아 토론 가능.

---

## 4. 미완료 작업 — 하위 에이전트 전담

### Phase B: N4 V3.0 루브릭 도입 (미완료)

---

#### B-1. `eval_turn.yaml` V3.0 작성
**파일**: `app/domain/langgraph/prompts/eval_turn.yaml`  
**현재 버전**: V2.2 (`likert_score`, `diagnosis_profile` 출력)  
**목표 버전**: V3.0 (R1~R4 의도별 게이팅, `turn_score`, `rubric_breakdown` 출력)

변경 사항:
- `variables`에서 `criteria` 제거 (코드에서 넘기더라도 템플릿 미사용으로 무해)
- 출력 JSON 형식 변경:
  ```json
  // 기존
  {"likert_score": 3, "diagnosis_profile": {...}, "feedback_summary": "..."}
  
  // V3.0
  {
    "turn_score": 3,
    "rubric_breakdown": {
      "R1_logic_efficiency": 4,
      "R2_clarity_completeness": 2,
      "R3_structure_examples": 3,
      "R4_context_maintenance": 5
    },
    "applied_rubrics": ["R1", "R2", "R3"],
    "feedback_summary": "..."
  }
  ```
- Intent-Rubric Applicability Matrix를 YAML 안에 `intent_rubric_gates` 섹션으로 명시
- FOLLOW_UP → R4만 채점, EXPLORATION → R3 면제 등 명시
- R2 가중치 (DEBUGGING: 2배) 명시

---

#### B-2. `grading.py` 새 Pydantic 모델 추가
**파일**: `app/domain/langgraph/nodes/eval_turn/grading.py`

추가 사항:
```python
class EvalTurnV30Output(BaseModel):
    turn_score: int = Field(..., ge=1, le=5)
    rubric_breakdown: Dict[str, int] = Field(
        ..., description="적용된 루브릭별 1~5 점수"
    )
    applied_rubrics: List[str] = Field(
        ..., description="실제 적용된 루브릭 목록 (의도에 따라 가변)"
    )
    feedback_summary: str = Field(...)
```

- 기존 `EvalTurnV21Output` 삭제하지 말고 유지 (레거시 폴백용)
- `likert_to_final()` 함수는 재사용 가능 (`turn_score`가 동일한 1~5 스케일)

---

#### B-3. `evaluators.py` 파싱 코드 교체
**파일**: `app/domain/langgraph/nodes/eval_turn/evaluators.py`

변경 위치: `_evaluate_turn` 함수 내 (약 5줄)

```python
# 기존 (V2.1/V2.2)
structured_result = await parse_structured_output_async(
    raw_response=raw_response,
    model_class=EvalTurnV21Output,
    fallback_llm=structured_llm,
)
final_score = likert_to_final(structured_result.likert_score)
diagnosis = structured_result.diagnosis_profile

# 변경 (V3.0)
structured_result = await parse_structured_output_async(
    raw_response=raw_response,
    model_class=EvalTurnV30Output,
    fallback_llm=structured_llm,
)
final_score = likert_to_final(structured_result.turn_score)
rubric_breakdown = structured_result.rubric_breakdown
applied_rubrics = structured_result.applied_rubrics
```

반환값에 `rubric_breakdown`, `applied_rubrics` 추가.  
기존 `"likert_score"`, `"diagnosis_profile"` 키 제거.

---

#### B-4. `n4_eval_turn_guard.py` Redis 저장 구조 변경
**파일**: `app/domain/langgraph/nodes/eval/n4_eval_turn_guard.py`

변경 위치: `detailed_turn_log` 딕셔너리 구성 (line ~750)

```python
# 기존 prompt_evaluation_details 구조
"prompt_evaluation_details": {
    "intent": final_intent,
    "score": turn_score,
    "rubrics": detailed_rubrics,     # 기존 list 형태
    "weights": weights,
    "final_reasoning": ...,
}

# V3.0 변경 후
"prompt_evaluation_details": {
    "intent": final_intent,
    "score": turn_score,
    "rubric_breakdown": rubric_breakdown,   # dict: {"R1_logic": 4, "R2_clarity": 2, ...}
    "applied_rubrics": applied_rubrics,     # list: ["R1", "R2", "R3"]
    "final_reasoning": feedback_summary,
}
```

`diagnosis_profile` 관련 코드 제거.  
`weights` 딕셔너리 제거 (V3.0에서는 YAML 안에 명시).

---

#### B-5. `debate_agents.yaml` R4 글로벌 채점 기준 명시
**파일**: `app/domain/langgraph/prompts/debate_agents.yaml`

`verdict` 섹션 `system` 프롬프트에 R4 글로벌 채점 가이드라인 추가:

```yaml
verdict:
  node: final_verdict
  model: gemini-2.5-pro-preview-03-25
  temperature: 0.1
  system: |
    ... (기존 내용 유지) ...
    
    [R4 대화 맥락 유지 — 세션 전체 궤적 분석]
    r4_context_maintenance_score 산정 기준:
    - 이전 턴에서 발생한 오류·피드백을 다음 턴에 반영했는가?
    - 턴이 진행될수록 프롬프트가 더 명확해지고 구체화되었는가?
    - 문제 해결의 궤적이 목표를 향해 논리적으로 수렴하는가?
    - 맥락을 무시하고 동일한 실수를 반복하면 감점.
    - turn_logs 전체를 순서대로 읽고 궤적 패턴을 판단할 것.
```

---

### Phase C: 검증 (미완료)

| 항목 | 내용 |
|------|------|
| C-1 | V3.0 YAML 적용 후 단일 턴 테스트 (각 의도별 rubric_breakdown 정상 반환 확인) |
| C-2 | Redis 저장 구조 확인 (`rubric_breakdown` 키 정상 저장) |
| C-3 | N8 `_build_base_context` 출력 확인 (rubric_breakdown dict 파싱 정상 여부) |

---

## 5. 하위 에이전트에게 제공할 자료 목록

하위 에이전트가 Phase B 작업을 수행하려면 아래 파일을 참고해야 합니다.

### 반드시 읽어야 할 파일

| 파일 | 목적 |
|------|------|
| `.maestro/RUBRIC_V3_CHANGE_PLAN.md` | **이 문서** — 전체 변경 계획 |
| `app/domain/langgraph/prompts/eval_turn.yaml` | 교체 대상 YAML (현재 V2.2) |
| `app/domain/langgraph/nodes/eval_turn/grading.py` | Pydantic 모델 추가 위치 |
| `app/domain/langgraph/nodes/eval_turn/evaluators.py` | 파싱 코드 교체 위치 |
| `app/domain/langgraph/nodes/eval/n4_eval_turn_guard.py` | Redis 저장 구조 변경 위치 (line ~750) |
| `app/domain/langgraph/prompts/debate_agents.yaml` | N8 R4 글로벌 채점 기준 추가 위치 |

### 참고 파일 (읽으면 맥락 이해에 도움)

| 파일 | 이유 |
|------|------|
| `app/domain/langgraph/states.py` | `EvalTurnState`, `DebateState` 구조 확인 |
| `app/domain/langgraph/subgraph_debate.py` | N8 `_build_base_context` — `rubric_breakdown` 파싱 로직 확인 |
| `app/domain/langgraph/nodes/eval_turn/weights.py` | 기존 의도별 가중치 (V3.0에서 대체되지만 구조 참고) |
| `app/domain/langgraph/prompts/eval_intent_disambiguation.yaml` | 6대 의도 정의 확인 |

### 작업 불필요 파일

| 파일 | 이유 |
|------|------|
| `n7_aggregate_turn_scores.py` | V3.0에서 N7 루브릭 미도입 결정 — **수정 없음** |
| `subgraph_debate.py` `_build_base_context` | 이미 dict/list 모두 유연하게 파싱 — **수정 없음** |
| `n8_code_execution.py` | Redis 읽기 로직 완료 — **수정 없음** |

---

## 6. 작업 순서 (Phase B 실행 가이드)

```
B-2 grading.py         (EvalTurnV30Output 모델 정의)
    ↓
B-1 eval_turn.yaml     (V3.0 프롬프트 + intent_rubric_gates + 출력 스키마)
    ↓
B-3 evaluators.py      (파싱 모델 EvalTurnV30Output으로 교체)
    ↓
B-4 n4_eval_turn_guard.py  (Redis 저장 구조 rubric_breakdown으로 변경)
    ↓
B-5 debate_agents.yaml  (R4 글로벌 채점 기준 추가)
    ↓
C   검증
```

---

## 7. 주의사항

1. **`EvalTurnV21Output` 삭제 금지**: 레거시 폴백 경로에서 아직 사용 가능성 있음
2. **`criteria` 파라미터**: `evaluators.py`의 각 `eval_*` 함수에서 `_evaluate_turn(state, eval_type, criteria)` 형태로 `criteria` 문자열을 여전히 넘기지만, V3.0 YAML 템플릿에서 `${criteria}`를 쓰지 않으므로 무해. 추후 정리 대상.
3. **`previous_turns_summary`**: N4의 이전 대화 참조 메커니즘은 Python 코드 레벨에서 관리되므로 YAML 변경과 무관하게 그대로 작동. 건드리지 말 것.
4. **N8 `_build_base_context` 키 순서**: `rubric_breakdown` 키를 먼저 확인하도록 우선순위 조정 필요 (현재 `rubrics` 키를 먼저 찾음). B-4 완료 후 subgraph_debate.py를 가볍게 수정하면 됨.
