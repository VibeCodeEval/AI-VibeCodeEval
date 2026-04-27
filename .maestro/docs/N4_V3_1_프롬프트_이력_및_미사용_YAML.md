# N4 Eval Turn — 프롬프트 변경 이력 및 미사용 YAML (Maestro 기록)

> **기록일**: 2026-04-19  
> **목적**: 최근 N4 턴 평가·의도 파이프라인 개편 내용을 Maestro 쪽에 고정해 두고, `app/domain/langgraph/prompts/*.yaml` 중 **런타임에서 로드되지 않는 파일**을 명시한다.  
> **검증 방법**: 저장소 전체에서 `load_prompt("…")`, `render_prompt("…")`, `get_prompt_template("…")` 호출 문자열을 기준으로 대조 (에이전트 문서·주석의 파일명 언급은 제외).

---

## 1. 이번 작업에서 정리된 동작 요약

| 영역 | 내용 |
|------|------|
| **의도 (4.0)** | 규칙 + 1단계 특성 LLM 제거 → **`eval_intent_disambiguation.yaml`** 단일 LLM. 출력: `IntentTurnLLMOutput` (`predicted_intent`, `intent_cot`). 구현: `nodes/eval_turn/analysis.py`. |
| **턴 채점 (4.x)** | **`eval_turn.yaml` v3.1**: 단일 `template`, `${previous_turns_summary}` 등. LLM은 **`scoring_cot` + `rubric_breakdown`(R1~R4)** 만. **`turn_score`**는 LLM이 내지 않고 **`grading.compute_turn_score_v31`**(의도별 가중식)으로 서버 계산. |
| **라우팅** | `intent_router`(`routers.py`)가 6대 통합 의도에 맞춰 **`eval_rule_setting` ~ `eval_follow_up` 중 하나**만 실행. 각 노드는 동일하게 `_evaluate_turn` → `render_prompt("eval_turn", …)`. |
| **저장** | `scoring_cot`(및 필요 시 `rubric_breakdown`, `applied_rubrics`)를 **`n4_eval_turn_guard`** 집계·**`evaluation_storage_service`** DB `details`, **`eval_service`** 백그라운드 턴 로그의 `prompt_evaluation_details`에 반영. |
| **테스트** | `tests/test_node4_unit.py` — V3 루브릭·6대 의도·스키마 검증 갱신. |

---

## 2. 프롬프트(YAML) 변경 이력 (N4 관련)

아래는 **시간 순 고정 기록이 아니라**, 코드·YAML 주석과 대화 맥락을 바탕으로 한 **논리적 이력**이다. 세부 날짜는 Git 히스토리로 확인한다.

### 2.1 `eval_turn.yaml` (턴 품질)

| 단계 | version (대략) | LLM 출력 / 점수 |
|------|------------------|-----------------|
| V2.2 | Context summary, Strict gates | 레거시 루브릭 리스트·점수 혼재 가능 |
| V3.0 | Intent-Rubric Gate | 구조화 출력에 루브릭 매트릭스 반영 (`EvalTurnV30Output` 등, `grading.py` 참고) |
| **V3.1 (현재)** | `3.1` | **`scoring_cot` + `rubric_breakdown`만**. `intent_rubric_gates` 표는 **문서·백엔드 산식과 동기** (`compute_turn_score_v31`). |

구현 앵커: `nodes/eval_turn/evaluators.py` (`render_prompt("eval_turn")`), `nodes/eval_turn/grading.py`.

### 2.2 의도 분류 프롬프트

| 단계 | 파일 / 방식 |
|------|-------------|
| 구버전 | `(Legacy)_eval_intent_analysis.yaml`, `(Legacy)_eval_prompt_characteristics.yaml` 등 다단계·다중 YAML 구상 (일부는 코드에서 제거됨) |
| **현재** | **`eval_intent_disambiguation.yaml`** 하나로 6대 통합 의도 (`render_prompt("eval_intent_disambiguation", …)` in `analysis.py`). |

### 2.3 서브그래프 내 기타 프롬프트

- **`summary.yaml`**: `summarize_answer`에서 `get_prompt_template("summary")`로 로드 (AI 응답 요약).
- **`debate_agents.yaml`**: N8 토론 서브그래프 (`load_prompt("debate_agents", section=role)`). N4와는 별도.

---

## 3. 현재 런타임에서 **사용 중**인 `prompts/*.yaml`

`load_prompt` / `render_prompt` / `get_prompt_template`에 **이름으로 등장**하는 파일:

| YAML | 호출 위치(대표) |
|------|-----------------|
| `eval_intent_analysis.yaml` | `nodes/chat/n2_intent_analyzer.py` |
| `writer_normal.yaml`, `writer_guardrail.yaml` | `nodes/chat/n3_writer.py` |
| `eval_turn.yaml` | `nodes/eval_turn/evaluators.py` |
| `eval_intent_disambiguation.yaml` | `nodes/eval_turn/analysis.py` |
| `summary.yaml` | `nodes/eval_turn/summary.py` |
| `debate_agents.yaml` | `subgraph_debate.py` |
| `spec_extractor.yaml` | `nodes/eval/spec_extractor.py` |

---

## 4. **사용하지 않게 된**(미참조) `.yaml` 파일

아래 파일은 **앱 런타임 코드 경로에서 위 API로 로드되지 않는다**. 보관·참고용이거나 문서/히스토리용으로 남겨 둔 상태이며, 삭제 여부는 팀 정책에 따른다.

| 파일 | 비고 |
|------|------|
| **`(Legacy)_eval_intent_analysis.yaml`** | 기존 N4 의도 분석용 레거시 파일을 접두로 분리. 현재 의도 분석은 **`eval_intent_disambiguation`** 사용. |
| **`(Legacy)_eval_prompt_characteristics.yaml`** | 1단계 “특성만” LLM 제거에 따라 **파이프라인 미사용**. |
| **`(Legacy)_eval_holistic_flow.yaml`** | 구 N6 Holistic Flow **LLM 프롬프트**. `n6_holistic_flow.py`는 정적 분석 전용으로 바뀌었고, Holistic 점수는 N8 토론 등으로 이관. **`load_prompt("eval_holistic_flow")` 없음**. |
| **`writer_normal_v1.yaml`** | `writer_normal.yaml` 주석에 따른 **V1 백업**. 코드는 `writer_normal`만 로드. |

---

## 5. 관련 소스 파일 (빠른 점프)

- 서브그래프: `app/domain/langgraph/subgraph_eval_turn.py`
- 의도 라우터: `app/domain/langgraph/nodes/eval_turn/routers.py`
- 점수식: `app/domain/langgraph/nodes/eval_turn/grading.py` — `compute_turn_score_v31`
- 제출 N4: `app/domain/langgraph/nodes/eval/n4_eval_turn_guard.py`
- 프롬프트 로더: `app/domain/langgraph/prompts/__init__.py`

---

## 6. 문서 동기화 권장

루트 `docs/Node4_평가_가이드.md`, `docs/프롬프트_명세.md`, `.maestro/DOCS_REFERENCE.md` 등에 **V3.0 전용** 문구가 남아 있으면 **V3.1 + 단일 의도 YAML + `scoring_cot` 저장** 기준으로 점검·갱신하는 것이 좋다.
