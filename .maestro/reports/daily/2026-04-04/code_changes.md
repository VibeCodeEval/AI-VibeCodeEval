# Code Changes Request & Log

> **추적 날짜**: 2026-04-04
> **작성자**: Antigravity (AI Agent)
> **관련 Phase**: Phase 6E - 평가 파이프라인 전면 재설계 (N5~N8)

---

## 1. 개요
기존 제출 과정의 평가 로직에서, 의존성이 끊기거나 역할이 모호했던 N5~N8 노드들을 명확한 역할별로 재할당하여 완전히 개편함. 

## 2. 주요 변경 사항

### [MODIFY] `states.py`
- `MainGraphState`에 신규 평가 결과를 저장하기 위한 2개의 필드 추가.
  - `code_quality_metrics`: N6 정적 분석(Radon CC) 결과 저장용.
  - `code_eval_report`: N7 코드 리뷰 LLM (정성 리뷰 JSON) 결과 저장용.

### [MODIFY] `n5_integrated_evaluator.py` (이전 통합 평가기 -> Judge0)
- 의미 잃은 `turn_analysis` 기반 규칙 평가를 제거.
- 기존 N8(`n8_code_execution.py`)의 Judge0 실행 (Correctness, Performance) 로직을 **전면 이식**.
- 노드 명칭 `eval_code_execution`으로 변경.

### [MODIFY] `n6_holistic_flow.py` (이전 전략 LLM -> 정적 분석)
- `eval_static_analysis`로 기능 전면 개편.
- `app.domain.langgraph.utils.code_quality`의 함수(`compute_radon_cc`, `check_ast_patterns`, `compute_delta_cc`)를 직접 선언하고 실행.
- 실행 결과를 `code_quality_metrics`로 State에 반환.

### [MODIFY] `n7_aggregate_turn_scores.py` (이전 단순 집계 -> 리뷰 LLM)
- `eval_code_agent`로 노드 개편.
- `ChatGoogleGenerativeAI` / `ChatVertexAI`를 통해 제출된 문제설명, 코드, Judge0 지표, Radon 지표를 컨텍스트로 LLM 단일 호출.
- 효율성, 가독성, 예외 처리 등 심층 리뷰를 담은 `CodeEvalReport` 구조화 JSON을 반환.

### [MODIFY] `n8_code_execution.py` (이전 Judge0 -> 다중 에이전트 Stub)
- 노드 명칭 `holistic_debate_stub`으로 변경.
- 다중 에이전트 (Pro 3기) 시스템은 추후 구현을 위해 일단 빈 결과를 반환하는 패스스루 형태로 처리 (`{}`).

### [MODIFY] `graph.py`
- 노드 import 및 명칭 업데이트.
- 메인 라우터(`eval_turn_guard` 및 `handle_failure`)에서 기존 `eval_holistic_flow`를 향하던 엣지를 `eval_code_execution`으로 교체.
- 순차 워크플로우 엣지 업데이트: 
  `N5(code eval) → N6(static analysis) → N7(code agent) → N8(debate stub) → N9(final score)`.

### [MODIFY] `n9_final_scores.py`
- `aggregate_turn_score`가 없을 경우 `turn_scores` 딕셔너리에서 단순 평균을 직접 계산하는 로직 추가.
- State에 새로 편입된 `code_quality_metrics`를 직접 추출하여 지원(하위 호환 유지).
- `code_eval_report` 데이터를 결과 `rubric_json`에 포함시켜 Postgres DB `SCORE` 형태로 영구 저장되도록 보강.

---

## 3. N8 다중 에이전트 토론 SubGraph 구현 (Phase 6E 이어서)

### [NEW] `app/domain/langgraph/subgraph_debate.py`
- `create_debate_subgraph()` 함수 신규 작성.
- 8개 노드 구성: `r1_strict`, `r1_advocate`, `r1_neutral`, `sync_opinions`, `r2_strict`, `r2_advocate`, `r2_neutral`, `final_verdict`.
- **Round 1 병렬**: `Send()` API로 3개 에이전트 동시 실행 → `initial_opinions: Annotated[List, operator.add]` 팬인.
- **Round 2 순차**: 각 에이전트가 다른 두 에이전트의 R1 의견을 컨텍스트로 받아 입장 재검토.
- **final_verdict**: Gemini 2.5 Pro (temp=0.0)가 6개 의견 취합 → `holistic_flow_score` + `holistic_flow_analysis` 도출.
- 시스템 프롬프트는 `debate_agents.yaml`에서 로드 (인라인 상수 없음).

### [NEW] `app/domain/langgraph/prompts/debate_agents.yaml`
- 4개 역할(strict/advocate/neutral/verdict)의 시스템 프롬프트를 섹션별 분리.
- 각 섹션 상단에 사용 노드명(`nodes: [r1_strict, r2_strict]` 등) 명시.
- 모델명(model)과 temperature도 YAML에서 관리.

### [MODIFY] `states.py`
- `DebateState` TypedDict 신규 추가 (`initial_opinions`, `rebuttals` 필드에 `operator.add` reducer 적용).
- `MainGraphState`에 `debate_log: Optional[List[Dict]]` 필드 추가.

### [MODIFY] `n8_code_execution.py`
- stub 제거, `holistic_debate_flow()` 실구현.
- `MainGraphState → DebateState` 매핑 후 `create_debate_subgraph().ainvoke()` 호출.
- 출력: `holistic_flow_score`, `holistic_flow_analysis`, `debate_log`.

### [MODIFY] `graph.py`
- import `holistic_debate_stub` → `holistic_debate_flow` 교체.
- `get_initial_state()`에 `debate_log=None` 초기값 추가.
- docstring 현행화 (N5~N9 역할 설명 업데이트).

---

## 4. 아키텍처 검토 메모 (결정 보류)

현재 구현된 **법정형(Courtroom / Chief Judge)** 방식 외에,
원래 기획했던 **P2P 합의형(Peer-to-Peer Consensus)** 아키텍처와의 비교 검토 중.
→ `plan_changes.md` 참조.
