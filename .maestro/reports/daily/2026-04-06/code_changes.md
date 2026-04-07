# Code Changes Log

> **추적 날짜**: 2026-04-06
> **작성자**: Cursor AI Agent
> **관련 Branch**: `feat/15-eval-change`
> **관련 Phase**: Eval Pipeline 개선 — 코드 품질·안정성 리팩토링

---

## 1. 개요

평가 파이프라인(N5~N8)의 운영 안정성 및 코드 품질 이슈 5건을 처리함.
작업은 파일 단위로 3개 영역으로 나눠 진행:

- **A영역** `subgraph_debate.py` — LLM 인스턴스 낭비 제거, `sync_opinions` 검증 강화, grade 불일치 보정
- **B영역** `n5_integrated_evaluator.py` + `config.py` — spec_id 하드코딩 제거
- **C영역** 노드 재편 후 의존성 정리 — 테스트 파일 import 오류, graph.py 주석, n6 docstring

추가로 대화 중 발견된 SQLAlchemy ForeignKey 안전성 이슈 1건을 즉시 수정함.

---

## 2. 상세 변경 내역

---

### [MODIFY] `app/domain/langgraph/subgraph_debate.py`

#### 작업 1 — LLM 인스턴스 캐싱 (`_LLM_REGISTRY`)

**문제:** `_make_llm(role)` 이 `_run_round1_agent` × 3, `_run_round2_agent` × 3, `final_verdict` × 1 호출 시마다 `get_llm_for_model()`을 새로 호출하여 매 평가마다 최대 7개의 LLM 인스턴스를 생성하고 있었음.

**수정:**
- `_AGENT_CONFIG` 로드 직후 모듈 레벨에 `_LLM_REGISTRY: Dict[str, Any]` dict를 추가.
  - 4개 역할(`strict`, `advocate`, `neutral`, `verdict`) LLM을 모듈 import 시 1회만 생성.
- `_make_llm(role)` 함수가 registry에서 캐시된 인스턴스를 반환하도록 단순화.

```python
# 추가된 코드 (모듈 레벨)
_LLM_REGISTRY: Dict[str, Any] = {
    role: get_llm_for_model(cfg["model"], float(cfg["temperature"]))
    for role, cfg in _AGENT_CONFIG.items()
}

def _make_llm(role: str):
    return _LLM_REGISTRY[role]
```

---

#### 작업 2 — `sync_opinions` 검증 강화

**문제:** `sync_opinions` 노드가 로그 출력 후 `return {}`만 반환하는 실질적 empty pass-through였음.

**수정:** 다음 검증 로직을 추가하되 `return {}`는 유지 (LangGraph 팬인 동기화 역할 보존):
- Round 1 에이전트 응답이 3개 미만이면 `logger.warning` (에이전트 실패 감지)
- 점수 표준편차(std_dev) 계산 후 `> 20` 이면 `logger.warning` (편차 과다 신호)

---

#### 작업 3 — `grade` vs `holistic_flow_score` 불일치 보정

**문제:** `final_verdict` 노드에서 LLM이 `FinalVerdict` 구조체를 반환할 때 `holistic_flow_score=88`, `grade="A"` 같은 모순이 발생할 수 있었음.

**수정:**
- 모듈 레벨에 `_GRADE_THRESHOLDS` 상수와 `_derive_grade(score)` 헬퍼 추가.
- `final_verdict` 함수에서 LLM 응답 수신 직후 코드로 grade를 재계산하여 불일치 시 `model_copy()`로 보정.
- 보정 발생 시 `logger.warning`으로 LLM 원본값과 보정값을 함께 기록.

```python
_GRADE_THRESHOLDS = [(90.0, "A"), (80.0, "B"), (70.0, "C"), (60.0, "D")]

def _derive_grade(score: float) -> str:
    for threshold, grade in _GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"

# final_verdict 내부 — LLM 응답 직후
derived_grade = _derive_grade(result.holistic_flow_score)
if result.grade != derived_grade:
    logger.warning(f"[Debate Verdict] grade 불일치 보정: LLM={result.grade} → {derived_grade} ...")
    result = result.model_copy(update={"grade": derived_grade})
```

---

### [MODIFY] `app/core/config.py`

**문제:** N5의 스마트 게이트 대상 spec_id가 코드에 하드코딩되어 있어 새로운 문제 spec 추가 시 코드 배포가 필요했음.

**수정:**
- `SMART_GATE_SPEC_IDS: List[int] = Field(default=[11, 20])` 필드 추가.
- 환경 변수 `SMART_GATE_SPEC_IDS=11,20` 형태로 오버라이드 가능.
- `from typing import List` 및 `from pydantic import Field` import 추가.

---

### [MODIFY] `app/domain/langgraph/nodes/eval/n5_integrated_evaluator.py`

**수정:**
- `from app.core.config import settings` import 추가.
- 하드코딩 조건 교체:
  ```python
  # 변경 전
  use_smart_gate_suite = bool(test_suite_code and (spec_id == 20 or spec_id == 11))
  # 변경 후
  use_smart_gate_suite = bool(test_suite_code and spec_id in settings.SMART_GATE_SPEC_IDS)
  ```
- 주석도 "스마트 게이트 2026(spec_id=20 또는 ...)" 고정 문구에서 settings 기반 설명으로 업데이트.

---

### [MODIFY] `app/domain/langgraph/nodes/eval/n6_holistic_flow.py`

**수정:**
- 모듈 docstring을 현재 역할(정적 분석)에 맞게 전면 교체.
- 구 `eval_holistic_flow`, `create_holistic_system_prompt` 함수가 제거됐다는 사실을 명시.
- LLM 기반 holistic 평가는 N8 `subgraph_debate.py`에서 수행함을 안내.

---

### [MODIFY] `app/domain/langgraph/graph.py`

**수정:**
- `eval_turn_guard` → `main_router` 조건부 엣지의 `"eval_holistic_flow"` 키 주석을 명확히 업데이트.
  - 이 키는 `main_router`가 반환하는 레거시 문자열이며, 실제 노드는 `eval_code_execution(N5)`에 매핑됨을 명시.

---

### [MODIFY] `tests/test_langsmith_tracing.py`

**수정:**
- 존재하지 않는 함수 `from app.domain.langgraph.nodes.eval.n6_holistic_flow import eval_holistic_flow` import 제거 (ImportError 방지).
- `test_eval_holistic_flow_with_langsmith` 테스트에 `@pytest.mark.skip` 추가 (N6 교체 사유 명시).

---

### [MODIFY] `tests/test_problem_context.py`

**수정:**
- 존재하지 않는 함수 `from app.domain.langgraph.nodes.eval.n6_holistic_flow import create_holistic_system_prompt` import 제거.
- `test_holistic_prompt_with_problem_context`, `test_holistic_prompt_without_problem_context` 테스트에 `@pytest.mark.skip` 추가 (N6 교체 사유 명시).

---

### [MODIFY] `app/infrastructure/persistence/models/submissions.py`

**문제:** `ForeignKey(Participant.id)` 사용 — `Participant.id`는 `InstrumentedAttribute`이며, `@declared_attr`으로 동적 결정되는 `__tablename__`과 조합 시 환경에 따라 `ArgumentError` 발생 가능.

**수정:**
- `ForeignKey(Participant.id)` → `ForeignKey(f"{settings.VIBECODE_PARTICIPANT_TABLE}.id")` 로 교체.
- `Participant` import 제거, `from app.core.config import settings` 추가.

---

### [MODIFY] `app/infrastructure/persistence/models/sessions.py`

**수정:** `submissions.py`와 동일한 ForeignKey 안전성 수정 적용.

---

### [MODIFY] `app/infrastructure/persistence/models/exams.py`

**수정:**
- `submissions.py`와 동일한 ForeignKey 안전성 수정 적용 (`ExamParticipant.participant_id`).
- `Participant` import는 `relationship("Participant")` 해석을 위한 SQLAlchemy mapper registry 등록 목적으로 **유지** (`# noqa: F401` 명시).

---

## 3. 아키텍처 현황 메모

### N6 holistic_flow 역할 변경 요약

| 구분 | 이전 (구 N6) | 현재 |
|---|---|---|
| 노드 | `n6_holistic_flow.py` — LLM 단일 에이전트 | `n6_holistic_flow.py` — Radon CC 정적 분석 |
| holistic_flow_score 산출 | N6 단독 LLM 호출 | **N8 다중 에이전트 토론** (`subgraph_debate.py`) |
| State 키 이름 | `holistic_flow_score` | 동일 (N9 호환 유지) |

### SMART_GATE_SPEC_IDS 관리 방식

```
이전: if spec_id == 20 or spec_id == 11  (하드코딩)
이후: if spec_id in settings.SMART_GATE_SPEC_IDS  (config/env)

환경 변수 예시:
  SMART_GATE_SPEC_IDS=11,20,30  ← 새 spec 추가 시 코드 배포 불필요
```

### grade 결정론적 기준

```
score >= 90 → A
score >= 80 → B
score >= 70 → C
score >= 60 → D
score < 60  → F
```
LLM이 프롬프트 기준을 무시하더라도 `final_verdict` 내 후처리가 자동 보정.
