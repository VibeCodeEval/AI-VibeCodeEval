# 계획·관리 문서 변경 및 Maestro 폴더 감사

> **기록일**: 2026-03-30  
> **유형**: `.maestro` 관리 허브 상태 점검, Git 작업 트리 대비 추적

---

## 1. 목적

프로젝트 마에스트로 관점에서 `.maestro/` 전체 구성을 확인하고, **추적되지 않은 신규 파일**과 **수정된 기존 파일**을 Git 기준으로 정리해 이후 커밋·정리 시 참고한다.

---

## 2. 상위 디렉터리 구성 (요약)

| 경로 | 용도 |
|------|------|
| `.maestro/maestro_state.json` | 전체 Phase·V2.1·에이전트 상태 |
| `.maestro/REPORTING_GUIDE.md` | 일일 보고·기록 규칙 |
| `.maestro/DOCS_REFERENCE.md` | `docs/` 참조 가이드 |
| `.maestro/PHASE6_PLAN.md` | Phase 6 계획 |
| `.maestro/README.md` | Maestro 허브 설명 |
| `.maestro/agents/` | 에이전트 시스템 프롬프트 (graph/chat/eval 등 + `project_maestro`, `AGENT_OVERVIEW`) |
| `.maestro/commands/` | `pending/`, `completed/`, 템플릿·지침 |
| `.maestro/docs/` | V2.1 Step 문서, 변경 이력, 평가·합성 데이터 요약 등 |
| `.maestro/reports/` | `daily/{YYYY-MM-DD}/`, 루트 `test_failure_analysis.md`(추적됨) |
| `.maestro/data/finetuning/` | Phase5/6 예시 JSONL 등 |
| `.maestro/shared/` | `project_context.json` |
| `.maestro/tasks/` | Phase별 태스크 JSON |

---

## 3. Git 작업 트리 (브랜치 `YSH`, 감사 시점)

### 3.1 수정됨 (tracked, not staged)

| 파일 | 비고 |
|------|------|
| `.maestro/docs/V2.1_Step_03_Writer.md` | Step 문서 갱신 |
| `.maestro/docs/V2.1_Step_04_Integrated_Evaluator.md` | 동일 |
| `.maestro/docs/V2.1_Step_05_Graph_And_Scores.md` | 동일 |
| `.maestro/docs/V2.1_Step_06_Finetuning_Data.md` | 동일 |
| `.maestro/docs/V2.1_Work_Instructions_Index.md` | 인덱스 보강 |
| `.maestro/maestro_state.json` | 진행 상태·노트 갱신 |

### 3.2 미추적 (untracked) — 커밋 시 `git add` 필요

| 경로 |
|------|
| `.maestro/DOCS_REFERENCE.md` |
| `.maestro/REPORTING_GUIDE.md` |
| `.maestro/agents/AGENT_OVERVIEW.md` |
| `.maestro/agents/chat_loop_agent.md` |
| `.maestro/agents/eval_orchestrator.md` |
| `.maestro/agents/graph_orchestrator.md` |
| `.maestro/agents/holistic_score_agent.md` |
| `.maestro/agents/project_maestro.md` |
| `.maestro/agents/turn_eval_agent.md` |
| `.maestro/docs/V2.1_Change_Log.md` |
| `.maestro/docs/V2.1_Evaluation_And_Score_Structure.md` |
| `.maestro/docs/V2.1_Synthetic_Data_And_Evol_Summary.md` |
| `.maestro/docs/V2.1_할일_체크리스트.md` |
| `.maestro/reports/daily/2026-03-27/api_changes.md` |
| `.maestro/reports/daily/2026-03-27/code_changes.md` |
| `.maestro/reports/daily/2026-03-27/plan_changes.md` |
| `.maestro/reports/daily/2026-03-30/code_changes.md` |
| `.maestro/reports/daily/2026-03-30/exam15_participant5_failure_analysis.md` |

**참고**: 본 파일(`plan_changes.md`)은 감사 직후 생성되므로, 다음 커밋에 포함하려면 동일하게 추가한다.

### 3.3 기타

- `.maestro/reports/test_failure_analysis.md` — **이미 Git 추적됨**, 감사 시점에 워킹 트리 변경 없음.
- `commands/completed/*.json`, `data/finetuning/**` 등은 기존에 저장소에 포함된 항목이며, 위 목록은 **감사 시점 `git status` 기준**이다.

---

## 4. 권장 후속 조치

1. `.maestro` 관련 신규·수정 파일을 한 번에 스테이징해 커밋하면 원격/협업 시 `.maestro` 허브 상태가 재현 가능해진다.
2. `maestro_state.json`의 `last_updated`는 감사 반영 시점으로 조정됨.

---

## 5. 관련 기록

- `maestro_state.json` → `notes` 타임스탬프 항목
- 동일 날짜 코드 변경: `code_changes.md` (2026-03-30)
