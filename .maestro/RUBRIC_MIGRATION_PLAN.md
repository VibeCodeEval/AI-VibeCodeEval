# 4대 핵심 통합 루브릭 이식 계획 (V1 — 구버전)

> **작성일**: 2026-04-04  
> **상태**: ⚠️ **이 문서는 구버전입니다. `.maestro/RUBRIC_V3_CHANGE_PLAN.md`로 대체되었습니다.**  
> **배경**: N8 다중 에이전트 토론 구현 과정에서 설계된 4대 루브릭을 각 노드에 최적 위치로 이식

> **주요 변경점 (구버전 vs 신버전)**:
> - R1을 N7에 넣으려던 계획 → **취소** (N4로 변경)
> - R4를 N8 단독 → **N4(로컬) + N8(글로벌)** 두 레벨로 분리
> - N7은 루브릭 미도입 확정
> - 의도별 루브릭 적용 행렬(Intent-Rubric Matrix) 신규 정의

---

## 루브릭 정의 (논문 기반)

| ID | 이름 | 가중치 | 논문 근거 계열 |
|----|------|--------|---------------|
| R1 | 논리적 완결성 및 효율성 (Logical Soundness & Efficiency) | 30% | Code Quality, Cyclomatic Complexity, Algorithm Complexity |
| R2 | 문제 정의의 명확성과 완전성 (Problem Clarity & Completeness) | 30% | Prompt Engineering (Specification Completeness) |
| R3 | 구조적 통제 및 예시 활용 (Structure & Constraints) | 20% | Few-shot Learning, Chain-of-Thought (Wei et al.), XML Tag 구조화 |
| R4 | 대화 맥락 유지 (Context Maintenance) | 20% | Multi-turn Conversation, Context Grounding |

---

## 루브릭별 이식 위치 및 이유

### R1 — 논리적 완결성 및 효율성 → **N7 (eval_code_agent)**

**현재 N7 역할**: 코드 리뷰 LLM (efficiency_review, readability_review, error_handling_review)

**이식 방향**:
- N7의 `CodeEvalReport` Pydantic 모델에 R1 루브릭 점수 필드 추가
- 기존 정성 리뷰(텍스트)를 R1 기준으로 재구성
- Judge0 correctness/performance + Radon CC avg_cc를 R1 산정 근거로 명시

**이식 후 N7 출력 구조**:
```python
class CodeEvalReport(BaseModel):
    efficiency_review: str        # 기존 유지
    readability_review: str       # 기존 유지
    error_handling_review: str    # 기존 유지
    overall_summary: str          # 기존 유지
    score_adjustment_note: str    # 기존 유지
    r1_logical_soundness_score: float   # 신규: R1 루브릭 점수 (0-100)
    r1_reasoning: str                   # 신규: R1 산정 근거
```

**N7 시스템 프롬프트 변경**: `eval_code_agent` 섹션에 R1 루브릭 기준 추가

---

### R2 + R3 — 명확성·완전성 / 구조적 통제·예시 → **N4 (eval_turn 서브그래프)**

**현재 N4 역할**: 8가지 의도별 턴 평가 (generation, debugging, optimization 등)

**이식 방향**:
- 기존 의도별 평가 유지 + R2/R3를 **공통 추가 축**으로 편입
- `EvalTurnState`에 `r2_problem_clarity_score`, `r3_structure_constraints_score` 필드 추가
- `aggregate_turn_log` 노드에서 의도 점수와 함께 R2/R3 점수를 `turn_log`에 기록
- `turn_scores` 딕셔너리에 루브릭 점수 포함

**이식 후 turn_log 구조** (예시):
```json
{
  "turn": 2,
  "intent": "GENERATION",
  "turn_score": 78.0,
  "r2_problem_clarity": { "score": 72.0, "reasoning": "..." },
  "r3_structure_constraints": { "score": 65.0, "reasoning": "..." }
}
```

**평가 시점**: 턴 단위 — R2는 해당 턴 프롬프트의 명세 완전성, R3는 해당 턴 프롬프트의 구조·예시 활용

**주의사항**:
- 첫 번째 턴(Phase 1)에서 R2/R3 비중이 가장 높음
- 후속 턴에서는 이전 턴 피드백 반영 여부를 맥락으로 고려
- `eval_turn.yaml` 프롬프트 템플릿에 R2/R3 루브릭 기준 섹션 추가 필요

---

### R4 — 대화 맥락 유지 → **N8 (holistic_debate_flow) 전담**

**현재 N8 역할**: 다중 에이전트 토론 (검사/변호인/중재자 × 2라운드 → 최종 판결)

**이식 방향**:
- R4는 **단일 턴이 아닌 세션 전체 궤적**을 봐야 하므로 N8이 유일한 적합 위치
- N8 에이전트들이 `turn_scores` 전체 딕셔너리를 보고 R4 판단
- `FinalVerdict` 모델에 `r4_context_maintenance_score` 필드 추가
- R4 점수는 N9 `prompt_score` 계산에 반영

**R4 평가 기준 (N8 debate_agents.yaml에 추가 예정)**:
- 이전 턴 오류·피드백을 다음 프롬프트에 반영했는가?
- 문제 해결의 궤적(Trajectory)이 목표를 향해 논리적으로 이어지는가?
- 턴이 진행될수록 프롬프트의 명확성이 개선되는가?

---

## 루브릭 통합 후 점수 흐름

```
N4 (턴별)     → turn_log에 turn_score + R2 + R3 기록
N7 (코드리뷰) → code_eval_report에 R1 점수 기록
N8 (토론)     → R4 판단 + N4/N7 결과 종합 → holistic_flow_score
N9 (집계)     → prompt_score = holistic_flow_score × 0.60 + aggregate_turn_score × 0.40
```

---

## 구현 우선순위 및 순서

| 순서 | 작업 | 파일 | 난이도 | 비고 |
|------|------|------|--------|------|
| 1 | R4를 N8 FinalVerdict에 추가 | `subgraph_debate.py`, `debate_agents.yaml` | 낮음 | N8 현재 작업 중 — 가장 먼저 |
| 2 | R1을 N7 CodeEvalReport에 추가 | `n7_aggregate_turn_scores.py` | 낮음 | 기존 리뷰 구조에 필드만 추가 |
| 3 | R2/R3를 N4 eval_turn에 추가 | `eval_turn/`, `eval_turn.yaml`, `EvalTurnState` | 높음 | 서브그래프 전반 수정 필요 |

---

## 현재 상태

- **N8**: 다중 에이전트 토론 구현 완료 (루브릭 미적용 상태 유지 중)
- **R4 이식**: 다음 작업 예정 (N8 안정화 후)
- **R1 이식**: R4 이후 진행
- **R2/R3 이식**: 마지막 — N4 변경 범위가 가장 넓음

---

## 관련 파일

- `app/domain/langgraph/prompts/debate_agents.yaml` — N8 에이전트 시스템 프롬프트
- `app/domain/langgraph/subgraph_debate.py` — N8 토론 서브그래프
- `app/domain/langgraph/nodes/eval/n7_aggregate_turn_scores.py` — N7 코드 리뷰
- `app/domain/langgraph/nodes/eval_turn/` — N4 턴 평가 서브그래프
- `app/domain/langgraph/prompts/eval_turn.yaml` — N4 프롬프트 템플릿
