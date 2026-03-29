# 계획 수정 사항 (2026-03-27)

> 1월 29일(마지막 maestro_state 갱신) 이후 ~ 3월 27일까지의 계획 변경을 정리합니다.

---

## 1. V2.1 Step 체크리스트 상태 변경

### Step 03 (Writer)
- **변경 전**: 체크리스트 미완료 상태
- **변경 후**: 전체 완료 (구조적 용어 감지, 클린/스파게티 분기, spec_id 분기, 가드레일 호환). Writer 레거시 제거(Phase 6 Spec 기반 코드 생성) 추가 완료.
- **사유**: V2.1 Writer 구현 작업 완료

### Step 04 (Integrated Evaluator)
- **변경 전**: 체크리스트 미완료 상태
- **변경 후**: 전체 완료 (Radon CC, AST 패턴, 5대 루브릭, v1 vs v2 DeltaCC, AST 문제별 패턴 확장)
- **사유**: V2.1 Integrated Evaluator 구현 완료

### Step 05 (Graph & Scores)
- **변경 전**: 체크리스트 미완료 상태
- **변경 후**: 전체 완료 (integrated_score 블렌딩, v21_summary, State 일관 반영, graph docstring)
- **사유**: V2.1 최종 점수 통합 완료

### Step 06 (Finetuning Data)
- **변경 전**: 체크리스트 미완료 상태
- **변경 후**: 부분 완료 (합성 데이터/Evol-Instruct/스크립트 준비). 파인튜닝 증강은 다른 AI에서 진행 예정으로 명시.
- **사유**: Seed 데이터 및 스크립트 구현 완료, 증강은 별도 작업

---

## 2. 평가 체계 방향 변경 (계획 외 추가 작업)

### Hybrid Likert 모델 도입
- **변경 전**: 0~100 가중치 합산 방식
- **변경 후**: 1~5 Likert 척도 + 진단 태그 Hybrid 모델. Legacy Adapter로 점진적 전환 지원 (Tier 1/2/3)
- **영향**: 모든 평가 노드, 프롬프트 YAML, 집계 로직에 영향
- **문서**: `V2.1_Change_Log.md`에 기록

### V2.1.1 Strict Scoring
- **변경 전**: 관대한 채점 (90점 과다 부여)
- **변경 후**: Strict Scoring Gates 도입 (추상적 형용사 남용 등 → 최대 2점)
- **영향**: eval_turn.yaml, 턴별 평가 결과

### V2.2 이전 턴 대화 요약
- **변경 전**: 턴별 독립 평가
- **변경 후**: 이전 턴 요약을 다음 턴 평가 입력에 포함. "진행해줘" 같은 연속 요청도 맥락 내에서 공정 평가
- **영향**: EvalTurnState, eval_turn_guard, evaluators, eval_turn.yaml

### V2.2 의도 분류 5-way
- **변경 전**: 8가지 세부 의도 → 4/5대 그룹 매핑
- **변경 후**: 처음부터 5대 의도(SETTING/CREATION/REFINEMENT/VALIDATION/FOLLOW_UP)로만 분류
- **영향**: 의도 분석 YAML, analysis.py, routers.py, weights.py, states.py

### V2.3 eval_holistic_flow
- **변경 전**: LLM이 0~100 점수 출력
- **변경 후**: LLM은 정수 1~5만 출력, Python에서 환산. 위임 전략도 고득점 인정
- **영향**: eval_holistic_flow.yaml, HolisticFlowEvaluation, flow.py

---

## 3. Phase 상태 갱신 필요

| Phase | maestro_state 기록 | 실제 상태 | 갭 |
|-------|-------------------|-----------|-----|
| Phase 4 (YAML 분리) | ready_for_handoff, progress 0% | 실제로 YAML 분리 작업은 이미 진행됨 (prompts/ 디렉토리에 YAML 파일 존재) | state 갱신 필요 |
| Phase 5a/5b/5c | ready_for_handoff | 데이터 추출 스크립트/예시 파일은 .maestro/data/finetuning/ 에 존재 | state 갱신 필요 |
| Phase 6B | progress 50% | 6b-1~6b-6 전부 완료. Node4+Node6 통합만 미완 | state 갱신 필요 |
| Phase 6C | pending | 미착수 | 정확 |
| Phase 6D | partial | 6d-1 완료, 6d-2 미완 | 정확 |

---

## 4. 기록 관리 체계 수립 (신규)

- **변경 전**: 일일 보고서가 JSON 형식으로 `.maestro/reports/daily/` 에 저장 (2건: 2026-01-18, 2026-01-29)
- **변경 후**: 날짜별 폴더(`YYYY-MM-DD/`) 구조로 전환. 각 폴더 내 `code_changes.md`, `plan_changes.md`, `api_changes.md` 분리 저장
- **사유**: 코드 변경 / 계획 변경 / API 변경을 구분하여 추적성 향상
- **가이드**: `.maestro/REPORTING_GUIDE.md`로 규칙 명문화

---

## 5. 향후 계획 우선순위

1. **maestro_state.json 갱신**: 현재 2026-01-29에서 멈춘 상태 → 최신화
2. **Node4+Node6 통합 평가기**: Phase 6B의 핵심 미완료 항목
3. **Phase 6C**: 파인튜닝 데이터 자동 생성 파이프라인
4. **Phase 6D-2**: Graph 노드 연결 변경
5. **할일 체크리스트 소화**: 데이터/스크립트 검증, JSONL 스키마 정리

---

## 6. 프로젝트 파일 구조 정리 (2026-03-27)

### 변경 전
- 루트에 36개 파일 산재 (테스트, 데이터, 스크립트, 문서 혼재)
- archive 디렉토리 2곳에 미사용 코드 15개 방치

### 변경 후
- 루트 13개 파일만 유지 (설정/Docker/의존성/README만)
- JSONL 데이터 → `data/`, 테스트 → `test_scripts/`, 스크립트 → `scripts/`, 문서 → `docs/`
- archive 디렉토리 완전 삭제

### 정리 규칙 수립
- **데이터 파일**: `data/` 하위에만 배치
- **테스트 스크립트**: pytest → `tests/`, 수동 → `test_scripts/`
- **실행/유틸 스크립트**: `scripts/`
- **문서**: `docs/` (README.md만 루트에 유지)
- **MD 파일**: 작성/수정 시 날짜 기록 필수

---

## 7. docs/ 문서 통합 정리 (2026-03-27)

### 변경 전
- 38개 MD 파일, 영문 파일명, 주제별 2~4개씩 분산

### 변경 후
- 21개 MD 파일, 한국어 파일명, 주제별 1개로 통합
- 모든 파일에 날짜(2026-03-27) 기록
- 문서_인덱스.md에 전체 목록 및 빠른 참조 갱신

### 문서 관리 규칙 수립
- **파일명**: 한국어 사용 (한번에 내용 파악 가능)
- **날짜**: 모든 MD 파일 상단에 최종 정리일/통합일 기록
- **인덱스**: docs/문서_인덱스.md에서 전체 문서 현황 관리
- **통합 원칙**: 같은 주제 문서는 하나로 통합, 내용은 섹션으로 편입

---

## 8. docs/ 참조 가이드 신규 작성 (2026-03-27)

- **신규 파일**: `.maestro/DOCS_REFERENCE.md`
- **목적**: 작업 시 어떤 docs/ 파일을 참조해야 하는지 빠르게 찾기
- **구성**: 문서별 4줄 설명(내용, 참조 시점, 관련 코드, 함께 볼 문서) + 작업 시나리오별 빠른 참조표
- **maestro_state.json**: `reporting.docs_reference` 경로 추가

---

## 9. 에이전트 시스템 프롬프트 체계 수립 (2026-03-27)

### 신규 디렉토리/파일
```
.maestro/agents/
├── AGENT_OVERVIEW.md          # 전체 에이전트 구조/운영 가이드
├── graph_orchestrator.md      # 그래프 오케스트레이터 (State/Graph 총괄)
├── chat_loop_agent.md         # 채팅 루프 (요청→의도→응답)
├── eval_orchestrator.md       # 평가 오케스트레이터 (전략/조율)
├── turn_eval_agent.md         # 턴 평가 (서브그래프 8종)
└── holistic_score_agent.md    # Holistic/점수 (통합평가→최종등급)
```

### 에이전트 계층 구조
- **그래프 오케스트레이터**: states.py, graph.py 총괄, 하위 에이전트 조율
- **채팅 루프 에이전트**: handle_request → intent → writer → system_nodes
- **평가 오케스트레이터**: 평가 전략/점수 병합, 평가 Agent 관리
  - **턴 평가 에이전트**: eval_turn_guard + 서브그래프 (8+파일)
  - **Holistic/점수 에이전트**: integrated + holistic + scores (7+파일)

### 운영 방식
- 각 에이전트 = 별도 Cursor 채팅 세션
- 에이전트 간 소통: .maestro/commands/ 파일 시스템 기반
- 모든 에이전트: 수정 → .maestro 기록 → 사용자 컨펌

### maestro_state.json 변경
- `agents` 섹션에 5개 신규 에이전트 등록 (system_prompt 경로 포함)

---

## 10. 프로젝트 마에스트로 에이전트 프롬프트 추가 (2026-03-27)

### 변경 전
- 에이전트 계층 구조에 최상위 총괄 관리자가 없음
- 그래프 오케스트레이터가 사실상 최상위 역할이었으나, 프로젝트 레벨(파일 구조, 문서 관리, 리포트 등)은 명시적 담당자 부재

### 변경 후
- `project_maestro.md` 신규 생성 — 에이전트 계층 최상위에 배치
- 프로젝트 전체 파일 구조, .maestro 관리, 문서, 리포트, 에이전트 조율 총괄
- 새 세션 시작 시 컨텍스트 복원 절차 명시 (maestro_state.json → 최신 리포트 → 중단 작업)
- AGENT_OVERVIEW.md 계층도 갱신 (프로젝트 마에스트로 → 하위 5개 에이전트)

### 에이전트 구조 (최종)
```
사용자
└── 프로젝트 마에스트로 (project_maestro.md)  ← 신규
    ├── 그래프 오케스트레이터 (graph_orchestrator.md)
    ├── 채팅 루프 에이전트 (chat_loop_agent.md)
    └── 평가 오케스트레이터 (eval_orchestrator.md)
        ├── 턴 평가 에이전트 (turn_eval_agent.md)
        └── Holistic/점수 에이전트 (holistic_score_agent.md)
```

---

## 11. LangGraph 노드 디렉토리 구조 리팩토링 (2026-03-27)

### 변경 전
- `nodes/` 아래 파일이 평면적으로 혼재 (채팅, 평가, 시스템 구분 없음)
- 파일명으로 노드 실행 순서를 알 수 없음
- `holistic_evaluator/`와 `turn_evaluator/`만 하위 폴더로 분리

### 변경 후
- 4개 역할별 폴더: `chat/`, `eval/`, `eval_turn/`, `system/`
- 노드 번호 `n1_` ~ `n9_` 부여 (실제 실행 순서 기준)
- `scores.py`를 `n7_aggregate_turn_scores.py` + `n9_final_scores.py`로 분리
- deprecated 파일 (`correctness.py`, `performance.py`) 삭제
- `holistic_evaluator/`, `turn_evaluator/` 디렉토리 삭제

### 노드 실행 순서 (최종)
```
[채팅 루프]
START → N1(handle_request) → N2(intent_analyzer) → N3(writer) → END

[제출 플로우]
N2 → N4(eval_turn_guard) → N5(integrated_evaluator) → N6(holistic_flow)
   → N7(aggregate_turn_scores) → N8(code_execution) → N9(final_scores) → END
```

### 영향 범위
- 25+ 파일의 import 경로 업데이트
- 에이전트 시스템 프롬프트 7개의 파일 경로 참조 갱신
- `git mv` 사용으로 히스토리 보존
