# 코드 수정 사항 (2026-03-27)

> V2.1 브랜치(YSH) 기준, 마지막 커밋(`e4c11dc V2.1 Writer 교체`) 이후 누적된 미커밋 변경 사항 전체를 기록합니다.
> 이 보고서는 1월 29일 이후부터 3월 27일까지의 변경을 한꺼번에 정리한 것입니다.

---

## 1. 평가 시스템 핵심 변경

### 1.1 Hybrid Likert 평가 모델 도입

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `app/domain/langgraph/nodes/turn_evaluator/grading.py` **(신규)** | `SCORE_MAPPING`(1~5 → 0~100), `likert_to_final()`, `final_to_likert()`, `EvaluationResult`, `DiagnosisProfile` 정의 | 기존 0~100 가중치 합산 방식 폐기, 1~5 Likert 기반 Hybrid 평가로 전환 |
| `app/domain/langgraph/nodes/turn_evaluator/weights.py` | `INTENT_WEIGHTS`/`calculate_weighted_score` 삭제, `RUBRIC_DISPLAY_ORDER` 추가, Legacy Adapter(`LEGACY_INTENT_WEIGHTS`, `legacy_turn_score_from_rubrics`) 격리 | Likert 전환에 따른 가중치 로직 분리. 5대 의도 키 추가 |
| `app/domain/langgraph/nodes/turn_evaluator/aggregation.py` | Tier 1(final_score/likert) → Tier 2(score/average) → Tier 3(Legacy Adapter) 우선순위 큐 방식으로 전환 | YAML Legacy(0~100)와 New(1~5) 혼용 지원 |
| `tests/test_turn_evaluator_hybrid.py` **(신규)** | Legacy 85→85, New likert 4→90, Tier 3 rubrics→Adapter 검증 | Hybrid 모델 동작 검증 |

### 1.2 V2.1.1 Strict 프롬프트 (착한 AI 증후군 방지)

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `app/domain/langgraph/prompts/eval_turn.yaml` | version 2.1→2.1.1→**2.2**. Strict Scoring Gates(추상적 형용사 남용/에러 로그 미첨부/대상 미지정 시 최대 2점). 깐깐한 시니어 프롬프트 감사관 페르소나. 이전 턴 요약 섹션 추가 | 90점 과다 부여 방지. 맥락 기반 공정 평가 지원 |

### 1.3 이전 턴 대화 요약 반영 (V2.2)

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `app/domain/langgraph/states.py` | `EvalTurnState`에 `previous_turns_summary: Optional[str]` 추가 | Eval Turn 입력에 이전 맥락 전달 |
| `app/domain/langgraph/nodes/eval_turn_guard.py` | 턴 루프에서 이전 턴 요약 누적, `_evaluate_turn_sync`에 `previous_turns_summary` 전달 | "진행해줘" 같은 연속 요청을 맥락과 함께 평가 |
| `app/domain/langgraph/nodes/turn_evaluator/evaluators.py` | `prepare_evaluation_input_internal`에서 `previous_turns_summary` 읽어 프롬프트에 삽입 | 이전 대화 요약을 LLM 입력에 반영 |
| `app/application/services/eval_service.py` | 실시간 단일 턴 평가용 `previous_turns_summary: None` 설정 | 단일 턴 평가 시 이전 요약 없음 처리 |

### 1.4 의도 분류 5-way 리팩토링 (V2.2)

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `app/domain/langgraph/prompts/eval_intent_analysis.yaml` | 8가지→5대 의도(SETTING/CREATION/REFINEMENT/VALIDATION/FOLLOW_UP)만 출력하도록 전면 수정 | FOLLOW_UP 쏠림 완화, 유지보수 단순화 |
| `app/domain/langgraph/states.py` | `IntentClassification.intent_types`: `list[CodeIntentType]`→`list[UnifiedIntentType]` | 5-way 타입 통일 |
| `app/domain/langgraph/nodes/turn_evaluator/analysis.py` | 8→5 매핑 로직(`_CODE_TO_UNIFIED_INTENT`) 제거, 5-way 파싱만 수행. 첫 턴 FOLLOW_UP→SETTING/CREATION 재분류 | 매핑 레이어 불필요 |
| `app/domain/langgraph/nodes/turn_evaluator/routers.py` | 8-way 라우팅 맵 제거. `UNIFIED_TO_NODE`(5→단일 노드) 추가 | 5대 의도 기반 라우팅 |
| `app/domain/langgraph/nodes/eval_turn_guard.py` | `intent_to_eval_key`에 5대 의도 추가, detailed_feedback 5-way 매칭 | 5-way 호환 |

### 1.5 eval_holistic_flow V2.3 (Strict Integer 1-5)

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `app/domain/langgraph/prompts/eval_holistic_flow.yaml` | version 2.3. 평가 항목 A/B/C/D, 1~5 정수만 출력. 위임 전략 가이드 | LLM 연산 오류 방지, Python에서 환산 |
| `app/domain/langgraph/states.py` | `HolisticFlowEvaluation` 점수 필드 `int` 1~5 (`ge=1, le=5`) | 정수 제한 적용 |
| `app/domain/langgraph/nodes/holistic_evaluator/flow.py` | `likert_to_final` import, 1~5→0~100 환산 | 하위 호환 유지 |

---

## 2. Writer 변경

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `app/domain/langgraph/nodes/writer.py` | 구조적 용어 감지(`has_structural_intent`, `STRUCTURAL_TERMS`), spec_id==20일 때 클린/스파게티 분기. `create_spec_based_system_prompt()` 및 Spec 기반 코드 생성 분기 제거 | V2.1 조건부 응답(클린 vs 스파게티) + Phase 6 레거시 제거 |
| `app/domain/langgraph/prompts/writer_normal_v1.yaml` | V1 백업 | 변경 전 프롬프트 보존 |
| `app/domain/langgraph/prompts/writer_guardrail.yaml` | 가드레일 업데이트 | Writer 동작 변경에 따른 조정 |
| `app/domain/langgraph/prompts/intent_analyzer.yaml` | 의도 분석 프롬프트 갱신 | 5-way 의도 대응 |

---

## 3. Integrated Evaluator (Radon CC, AST, 5대 루브릭)

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `app/domain/langgraph/utils/code_quality.py` **(신규)** | `compute_radon_cc(code)`, `check_ast_patterns(code, spec_id, required_patterns)`, `compute_delta_cc()` | Radon CC 계산, AST 상속/전략 패턴 검사, v1 vs v2 DeltaCC |
| `app/domain/langgraph/nodes/integrated_evaluator.py` | Radon CC + AST 패턴 → `code_quality_metrics`, 5대 루브릭 `rubric_breakdown`, v1 vs v2 DeltaCC 비교 | Step 04 구현 |
| `app/infrastructure/repositories/session_repository.py` | `get_v1_checkpoint_code(session_id)` 추가 | v1 스냅샷 조회 (meta에서 is_v1_checkpoint=true) |
| `pyproject.toml` | `radon>=6.0.0` 의존성 추가 | Radon CC 분석 |
| `requirements.txt` | 의존성 갱신 | uv lock 동기화 |

---

## 4. Graph / Scores / State 변경

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `app/domain/langgraph/nodes/holistic_evaluator/scores.py` | `aggregate_final_scores`: integrated_score 50% 블렌딩, DeltaCC/AST 학점 보정, `v21_summary` 포함 | Step 05: 최종 점수에 V2.1 반영 |
| `app/domain/langgraph/nodes/holistic_evaluator/execution.py` | 실행 로직 갱신 | 통합 평가 플로우 반영 |
| `app/domain/langgraph/graph.py` | docstring 갱신, 노드 순서 확인 | V2.1 노드 동작 문서화 |
| `app/domain/langgraph/states.py` | `v1_code`, `v2_code`, `v1_metrics`, `v2_metrics`, `unified_intent`, `HolisticFlowEvaluation` int 필드 등 추가 | Step 01/05: State 확장 |
| `app/infrastructure/persistence/models/enums.py` | `GradeType`, `UnifiedIntentType`, `RubricType` Enum 추가 | Step 01: Enum 정의 |
| `app/domain/langgraph/utils/problem_info.py` | 스마트 게이트 2026 (spec_id=20) 추가 | Step 01: 문제 정의 |
| `app/domain/langgraph/nodes/intent_analyzer.py` | 5-way 의도 대응 | V2.2 의도 분류 |

---

## 5. 합성 데이터 / 파인튜닝 스크립트 (신규)

| 파일 | 설명 |
|------|------|
| `scripts/generate_synthetic_v21_data.py` **(신규)** | 등급별(A~F) 변형 프롬프트 60건 생성 |
| `scripts/evol_instruction_v21.py` **(신규)** | Evol-Instruct 5단계 진화 + Eval Turn reasoning 추출 |
| `scripts/run_synthetic_session_eval.py` **(신규)** | 가상 세션 전체 플로우 평가 |
| `scripts/extract_v21_finetuning.py` **(신규)** | 파인튜닝 데이터 추출 |
| `scripts/generate_synthetic_v21_data_paraphrase.py` **(신규)** | 패러프레이즈 변형 생성 |
| `scripts/eval_three_turn_conversation.py` **(신규)** | 3턴 대화 평가 스크립트 |

---

## 6. 문서 정리

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `docs/Backend_DB_Configuration_Guide.md` | **삭제** | 통합 문서로 병합 |
| `docs/Backend_Docker_Compose_DB_Setup.md` | **삭제** | 통합 문서로 병합 |
| `docs/Backend_Docker_Quick_Reference.md` | **삭제** | 통합 문서로 병합 |
| `docs/Backend_Docker_Setup_Guide.md` | **삭제** | 통합 문서로 병합 |
| `docs/Docker_PostgreSQL_Setup_Guide.md` | **삭제** | 통합 문서로 병합 |
| `docs/Backend_Docker_And_DB_Guide.md` **(신규)** | Docker/DB 통합 가이드 | 5개 문서를 1개로 통합 |
| `docs/Judge0_Complete_Guide.md` | Judge0 가이드 보강 | Judge0 설정 내용 추가 |

---

## 7. 테스트

| 파일 | 변경 내용 |
|------|-----------|
| `tests/test_node4_unit.py` | 5-way 의도 대응 수정 |
| `tests/test_problem_context.py` | 스마트 게이트 2026 추가 대응 |
| `tests/test_turn_evaluator_hybrid.py` **(신규)** | Hybrid Likert 모델 검증 |

---

## 8. 데이터 파일 (신규)

| 파일 | 설명 |
|------|------|
| `v21_rubric_60.jsonl` | 루브릭 60건 합성 데이터 |
| `v21_evol.jsonl` | Evol-Instruct 진화 데이터 |
| `v21_evol_with_eval.jsonl` | 진화 + 평가 reasoning 포함 |
| `v21_final_synthetic_dataset.jsonl` | 최종 합성 데이터셋 |
| `v21_finetuning_dataset.jsonl` | 파인튜닝 데이터셋 |
| `data/v21_finetuning_dataset.jsonl` | 파인튜닝 데이터셋 (data 디렉토리) |
| `data/v21_finetuning_dataset_paraphrased.jsonl` | 패러프레이즈 변형 |

---

## 9. 프로젝트 파일 구조 정리 (2026-03-27)

> 루트 디렉토리에 산재한 파일들을 적절한 하위 디렉토리로 이동/삭제하여 구조 정돈.
> 루트: **36개 → 13개** 파일로 축소.

### 9.1 JSONL 데이터 파일 → `data/` 이동

| 파일 | 액션 | 사유 |
|------|------|------|
| `v21_rubric_60.jsonl` | `data/`로 이동 | 데이터 파일은 data/ 하위에 보관 |
| `v21_evol.jsonl` | `data/`로 이동 | 동일 |
| `v21_evol_with_eval.jsonl` | `data/`로 이동 | 동일 |
| `v21_final_synthetic_dataset.jsonl` | `data/`로 이동 | 동일 |
| `v21_finetuning_dataset.jsonl` | **삭제** | `data/v21_finetuning_dataset.jsonl`과 중복 |

### 9.2 테스트 Python → `test_scripts/` 이동

| 파일 | 액션 |
|------|------|
| `test_submit_tsp.py` | `test_scripts/`로 이동 |
| `test_single_turn_submit.py` | `test_scripts/`로 이동 |
| `test_full_flow_tsp.py` | `test_scripts/`로 이동 |
| `test_api_chat_messages.py` | `test_scripts/`로 이동 |

### 9.3 PowerShell → `scripts/` 이동

| 파일 | 액션 |
|------|------|
| `test_api.ps1`, `run_test.ps1`, `run_test_all.ps1`, `run_test_with_constraints.ps1` | `scripts/`로 이동 |

### 9.4 테스트 JSON → `test_scripts/` 이동

| 파일 | 액션 |
|------|------|
| `test_ids.json`, `test_chat_session.json`, `test_chat_sessions.json`, `test_tsp_ids.json` | `test_scripts/`로 이동 |
| `test_cases.json` | **삭제** (test_scripts/ 중복) |

### 9.5 문서 → `docs/` 이동 + 날짜 기록

| 파일 | 액션 |
|------|------|
| `README_ENVIRONMENT.md`, `QUICK_TEST.md`, `테이블명세서.md` | `docs/`로 이동, 날짜 헤더 추가 |

### 9.6 삭제

| 파일/디렉토리 | 사유 |
|---------------|------|
| `solution.py` | 임시 예제 코드 |
| `chat_diff.txt` | 임시 diff 파일 |
| `tests/archive/` (6개) | 미사용 아카이브 |
| `test_scripts/archive/` (9개) | 미사용 아카이브 |

### 9.8 정리 후 루트 디렉토리 (13개)

```
AI-VibeCodeEval/
├── .env, .gitignore, .python-version
├── pyproject.toml, requirements.txt, uv.lock
├── Dockerfile, docker-compose.yml, docker-compose.dev.yml, docker-compose.prod.yml
├── env.example, env.prod.example
└── README.md
```

---

## 10. docs/ 문서 통합 정리 (2026-03-27)

> 38개 → 21개로 통합. 파일명 한국어로 변환. 모든 MD 파일에 날짜(2026-03-27) 기록.

### 10.1 통합 (26개 → 9개 결과)

| 원본 파일 | 통합 결과 |
|----------|-----------|
| `API_Changes_2024-12-07.md` + `Endpoint_Change_History.md` | **`API_변경_이력.md`** |
| `Current_Data_Flow.md` + `LangGraph_State_Flow.md` + `State_Flow_and_DB_Storage.md` | **`State_흐름_및_DB_저장.md`** |
| `Node4_Evaluation_Flow_Scenario.md` + `Node4_Evaluation_Input_Output_Guide.md` + `Node4_Intent_Analysis_vs_Evaluation.md` | **`Node4_평가_가이드.md`** |
| `Prompt_Evaluation_Storage_Location.md` + `Node4_Node6_Database_Access.md` | **`노드별_DB_접근_가이드.md`** |
| `Complete_DB_Setup_Guide.md` + `Local_DB_Setup_Guide.md` + `Local_DB_Migration_Guide.md` + `Quick_DB_Guide.md` | **`DB_설정_가이드.md`** |
| `Database_Changes_Summary.md` + `DB_Schema_Changes.md` | **`DB_변경_이력.md`** |
| `Test_Execution_Guide.md` + `API_Test_Guide.md` + `Full_Flow_Test_Scenario.md` + `Test_Scripts_Guide.md` | **`테스트_가이드.md`** |
| `Judge0_Complete_Guide.md` + `Judge0_Test_Case_Flow.md` + `QUICK_TEST.md` | **`Judge0_가이드.md`** |
| `README_ENVIRONMENT.md` + `Quick_Start_Commands.md` | **`환경_설정_가이드.md`** |

### 10.2 이름 변경 (12개)

| 원본 | 변경 후 |
|------|---------|
| `API_Specification.md` | `API_전체_명세.md` |
| `API_Current_Implementation.md` | `API_현재_구현.md` |
| `API_DB_Mapping_Analysis.md` | `API_DB_매핑.md` |
| `Backend_Docker_And_DB_Guide.md` | `Docker_백엔드_가이드.md` |
| `Prompt_Specification.md` | `프롬프트_명세.md` |
| `Score_Calculation_Logic.md` | `점수_계산_로직.md` |
| `UV_Setup_Guide.md` | `UV_설정_가이드.md` |
| `Rubric_Refactoring_Proposal.md` | `루브릭_리팩토링_제안.md` |
| `Performance_Optimization_LLM_Duplicate_Calls.md` | `LLM_성능_최적화.md` |
| `Turn_Logs_Data_Extraction.md` | `턴_로그_추출.md` |
| `Schema_Reference_Index.md` | `문서_인덱스.md` |
| `테이블명세서.md` | (이름 유지) |

### 10.3 삭제 (1개)

| 파일 | 사유 |
|------|------|
| `docs/README.md` | 구형 인덱스 (2025-11-28), 문서_인덱스.md로 대체 |

---

## 11. 프로젝트 마에스트로 에이전트 프롬프트 추가 (2026-03-27)

### 11.1 신규 생성

| 파일 | 내용 |
|------|------|
| `.maestro/agents/project_maestro.md` | 프로젝트 전체 총괄 관리자 시스템 프롬프트. 에이전트 계층 최상위, .maestro 관리, 파일/문서 구조, 리포트 규칙, 하위 에이전트 위임 절차, 세션 복원 가이드 포함 |

### 11.2 수정

| 파일 | 변경 내용 |
|------|-----------|
| `.maestro/agents/AGENT_OVERVIEW.md` | 계층 구조도에 프로젝트 마에스트로를 최상위로 추가, 에이전트 요약 테이블에 행 추가 |
| `.maestro/maestro_state.json` | `agents` 섹션에 `project_maestro` 등록, `last_updated` 갱신, `notes` 추가 |

---

## 12. LangGraph 노드 디렉토리 구조 리팩토링 (2026-03-27)

### 12.1 구조 변경: 평면 → 역할별 폴더 + 노드 번호

```
nodes/ (변경 전: 평면)              →  nodes/ (변경 후: 역할별)
├── handle_request.py                   ├── chat/n1_handle_request.py
├── intent_analyzer.py                  ├── chat/n2_intent_analyzer.py
├── writer.py                           ├── chat/n3_writer.py
├── writer_router.py                    ├── chat/routers.py
├── system_nodes.py                     ├── system/system_nodes.py
├── eval_turn_guard.py                  ├── eval/n4_eval_turn_guard.py
├── integrated_evaluator.py             ├── eval/n5_integrated_evaluator.py
├── spec_extractor.py                   ├── eval/spec_extractor.py
├── holistic_evaluator/flow.py          ├── eval/n6_holistic_flow.py
├── holistic_evaluator/scores.py        ├── eval/n7_aggregate_turn_scores.py (분리)
│                                       ├── eval/n9_final_scores.py (분리)
├── holistic_evaluator/execution.py     ├── eval/n8_code_execution.py
├── holistic_evaluator/utils.py         ├── eval/utils.py
├── holistic_evaluator/langsmith_utils  ├── eval/langsmith_utils.py
├── holistic_evaluator/correctness.py   │ (삭제 - deprecated)
├── holistic_evaluator/performance.py   │ (삭제 - deprecated)
└── turn_evaluator/*                    └── eval_turn/* (폴더명 변경)
```

### 12.2 Import 업데이트 (25+ 파일)

- `graph.py`, `subgraph_eval_turn.py`, `eval_service.py`
- `__init__.py` 5개 (nodes, chat, eval, eval_turn, system)
- 노드 내부 상호 참조 6개
- 테스트 11개, middleware 1개
- `.maestro/agents/` 시스템 프롬프트 7개
