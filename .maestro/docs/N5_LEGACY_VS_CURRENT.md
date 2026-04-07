# N5 노드: 레거지(통합 평가기) vs 현재(Judge0 코드 실행)

> **작성일**: 2026-04-05  
> **레거지 참조**: 저장소 루트 `n5_old.py` (구 `integrated_evaluator` 구현 스냅샷)  
> **현재 구현**: `app/domain/langgraph/nodes/eval/n5_integrated_evaluator.py`

파일명은 여전히 `n5_integrated_evaluator.py`이나, **역할은 “통합 평가”에서 “Judge0 기반 코드 실행 평가”로 전환**되었다. Phase 6E(2026-04-04) 설계에 따른 변경이다.

---

## 1. 한 줄 요약

| 구분 | 레거지 N5 | 현재 N5 |
|------|-----------|---------|
| **공개 심볼** | `integrated_evaluator` | `eval_code_execution` |
| **본질** | DB `turn_analysis` + 규칙 기반 통합 점수 + (선택) Radon/AST로 `code_quality_metrics` | **Judge0**로 Correctness → (통과 시) Performance |
| **LLM** | 없음 | 없음 (실행/측정 중심) |

---

## 2. 레거지 N5 (`integrated_evaluator`, `n5_old.py`)

### 목적

- 제출 시 **Spec·턴 분석(`turn_analysis`)**을 묶어 **규칙 기반 통합 점수** 산출.
- 철학: “불완전한 코드는 첫 프롬프트 Spec 불완전에서 비롯” — 첫 턴 55%, 후속 25%, 효율성 20% 가중.

### 주요 입력

- PostgreSQL `SessionRepository.get_all_turn_analyses(session_id)` 등으로 **턴 분석 배열**.
- `state`의 `code_content` / `v1_code` 등이 있으면 **v1 vs v2 Radon CC**, AST 패턴 등으로 `code_quality_metrics`, `rubric_breakdown` 보강.

### 주요 출력 (State)

- `integrated_score` (float)
- `integrated_evaluation` (dict: 분석 텍스트, 제안, `rubric_breakdown`, `code_quality_metrics` 등)
- `updated_at`

### 한계 (재설계 사유, maestro 기록과 일치)

- **spec_extractor / turn_analysis 파이프라인이 그래프와 제대로 연결되지 않은 상태**에서 `integrated_score`가 사실상 비어 있거나 의미 없는 경우가 있었음.
- 프롬프트 품질의 상당 부분은 이미 **N4(턴별 서브그래프)**에서 LLM으로 평가하는 구조로 이전됨.

---

## 3. 현재 N5 (`eval_code_execution`, `n5_integrated_evaluator.py`)

### 목적

- 제출 코드에 대해 **실제 실행 기반** 평가:
  1. **Correctness**: 테스트 케이스 통과율 (Judge0)
  2. 통과 시 **Performance**: 실행 시간, 메모리 (Judge0)

### 주요 입력

- `state["code_content"]`, `submission_id` 등
- 코드 정리(`clean_code`) 후 Judge0 큐/Worker 연동

### 주요 출력 (State)

- `code_correctness_score`, `code_performance_score`
- `test_cases_passed` / `test_cases_total`, `execution_time`, `memory_used_mb`, `correctness_reasoning` 등 (구현부 전체 필드는 소스 참고)
- LangSmith: `wrap_node_with_tracing`, trace 이름 `eval_code_execution`

### 그래프 상 위치

- `graph.py`: 노드명 `eval_code_execution`, 라우터 레거시 키 `eval_holistic_flow` → 여전히 이 노드로 매핑(이름만 유지).

---

## 4. 역할 이동 (옛 N5가 하던 일의 귀속)

| 레거지 N5 영역 | 현재 담당 (대략) |
|----------------|------------------|
| 턴별 프롬프트 품질·의도 | **N4** `eval_turn_guard` + Eval Turn SubGraph |
| 코드 정적 복잡도·메트릭 | **N6** `eval_static_analysis` (Radon CC 등) |
| 코드 정성 리뷰 | **N7** `eval_code_agent` (LLM) |
| 세션 전체·홀리스틱·R4 글로벌 | **N8** `holistic_debate_flow` (다중 에이전트) |
| 최종 점수·DB `scores.rubric_json` | **N9** `aggregate_final_scores` |
| `integrated_score` / `integrated_evaluation` | N9에서 여전히 state 키로 **병합·전달**될 수 있으나, **옛 통합기에서 채우지 않음** (없으면 None/미사용) |

---

## 5. 패키지 import 정리 (2026-04-05)

`integrated_evaluator` 심볼 제거 후 **`nodes/__init__.py`, `nodes/eval/__init__.py`**는 `eval_code_execution` 등 실제 노드만 re-export하도록 수정함.  
자세한 트레이스: `ImportError: cannot import name 'integrated_evaluator'` 수정 커밋과 동일 시기.

---

## 6. 참고 파일

- 현재 N5: `app/domain/langgraph/nodes/eval/n5_integrated_evaluator.py`
- 레거지 참고: `n5_old.py` (저장소 루트, 아카이브 성격)
- 그래프: `app/domain/langgraph/graph.py`
- 재설계 배경: `.maestro/RUBRIC_V3_CHANGE_PLAN.md`, `.maestro/reports/daily/2026-04-04/plan_changes.md`
