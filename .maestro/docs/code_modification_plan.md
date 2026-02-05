# 코드 수정 계획안 (Task 기준)

> Phase 6 / CMD_005 태스크에 맞춘 **실행 순서별** 코드 수정 계획.  
> 체크리스트는 진행 시 `[x]`로 갱신.

**기준 문서**: `.maestro/tasks/phase6_system_refactoring.json`, `.maestro/commands/pending/CMD_005_phase6_refactoring.json`

---

## 0. 현재 상태 요약

| 구분 | 상태 | 비고 |
|------|------|------|
| Phase 6A (AST·Spec·Writer) | 구현 완료, **그래프 미연결** | spec_extractor, error_injector 노드 없음 |
| Phase 6B (통합 평가) | integrated_evaluator 존재, **Node4+Node6 통합 미완** | 규칙 기반만, 분리 실행 |
| Phase 6C (파인튜닝 데이터) | 미진행 | scripts/finetuning 없음 |
| Phase 6D (Graph) | 부분 반영 | integrated_evaluator만 연결됨 |

---

## 1. Phase 6A: AST·Spec·Writer 그래프 연결 (선택)

> 6A 코드는 이미 있음. **그래프에 붙여서** Spec 기반 코드 생성이 동작하도록 할 때만 수행.

### 1.1 그래프에 노드 추가

| 순서 | 작업 | 파일 | 수정 내용 |
|------|------|------|-----------|
| 1 | spec_extractor 노드 등록 | `app/domain/langgraph/graph.py` | `from ...nodes.spec_extractor import spec_extractor` 후 `builder.add_node("spec_extractor", spec_extractor)` |
| 2 | error_injector 노드 등록 | `app/domain/langgraph/graph.py` | `from ...ast_injector import error_injector` 후 `builder.add_node("error_injector", error_injector)` |

### 1.2 엣지 연결 (Intent → Spec 경로)

| 순서 | 작업 | 파일 | 수정 내용 |
|------|------|------|-----------|
| 3 | intent_analyzer 후 writer 대신 spec 경로 분기 | `app/domain/langgraph/graph.py` | intent_router에서 "writer" 일부를 "spec_extractor"로 보내거나, writer 직전에 spec_extractor → error_injector → writer 직렬 연결. (선택: 채팅 시 항상 spec 경로 vs 코드 생성 요청 시만 spec 경로) |
| 4 | spec_extractor → error_injector → writer 순서 고정 | `app/domain/langgraph/graph.py` | `add_edge("spec_extractor", "error_injector")`, `add_edge("error_injector", "writer")` 추가. 단, **기존 채팅 플로우 유지**하려면 intent_analyzer → writer 엣지는 유지하고, "코드 생성 요청"일 때만 spec_extractor로 진입하도록 조건부 엣지 필요. |

### 1.3 Writer 진입 조건

| 순서 | 작업 | 파일 | 수정 내용 |
|------|------|------|-----------|
| 5 | Writer가 spec_result/modified_code 없을 때 동작 | `app/domain/langgraph/nodes/writer.py` | 이미 분기 있음. spec_extractor/error_injector가 state를 채우면 Writer가 Spec 기반 분기 사용. |

- **체크리스트 (6A 그래프 연결)**  
  - [ ] 6A-1: graph.py에 spec_extractor 노드 추가  
  - [ ] 6A-2: graph.py에 error_injector 노드 추가  
  - [ ] 6A-3: intent_analyzer → spec_extractor 또는 writer 조건부 엣지  
  - [ ] 6A-4: spec_extractor → error_injector → writer 엣지  
  - [ ] 6A-5: handle_request 또는 spec_extractor에서 solution_code를 state에 넣는지 확인 (error_injector는 state에서 spec_result, solution_code 사용)  

---

## 2. Phase 6B: 통합 평가 보완 (Task 6b-1 ~ 6b-6)

> integrated_evaluator는 이미 graph에 연결됨. TurnAnalysis 저장·scores 반영·(선택) Node4+Node6 통합까지 정리.

### 2.1 TurnAnalysis 모델 및 저장 (6b-1, 6b-2, 6b-3)

| Task ID | 작업 | 파일 | 수정 내용 |
|---------|------|------|-----------|
| 6b-1 | TurnAnalysis/SessionAnalysis 모델 | `app/domain/langgraph/states.py` | `TurnAnalysis`, `SessionAnalysis` TypedDict 또는 Pydantic 추가. 필드: turn, is_first_prompt, spec_completeness, clarity_score, has_structure, has_examples, spec_recovery_count, references_previous, summary 등 (task 정의 참고) |
| 6b-2 | Spec Extractor에서 TurnAnalysis 생성 | `app/domain/langgraph/nodes/spec_extractor.py` | spec_result 기반으로 TurnAnalysis 객체 생성해 state 또는 반환 dict에 포함. 필요 시 `create_turn_analysis()` 등 함수 추가. |
| 6b-3 | TurnAnalysis를 DB에 저장 | `app/application/services/eval_service.py` | 채팅 턴 종료 후(Writer 응답 반환 후) 해당 턴의 turn_analysis를 SessionRepository.update_message_meta(session_id, turn, meta_update={"turn_analysis": ...}) 로 저장. 호출 위치: process_message 반환 전 또는 콜백. (handle_request에서 저장할 경우 `app/domain/langgraph/nodes/handle_request.py` 수정) |

- **체크리스트**  
  - [ ] 6b-1: states.py에 TurnAnalysis/SessionAnalysis 정의  
  - [ ] 6b-2: spec_extractor.py에서 TurnAnalysis 생성 및 반환  
  - [ ] 6b-3: eval_service.py(또는 handle_request)에서 prompt_messages.meta['turn_analysis'] 저장  

### 2.2 Integrated Evaluator 및 Graph (6b-4, 6b-5)

| Task ID | 작업 | 파일 | 수정 내용 |
|---------|------|------|-----------|
| 6b-4 | Integrated Evaluator 로직 점검 | `app/domain/langgraph/nodes/integrated_evaluator.py` | load_turn_analyses_from_db(session_id) 호출, first_prompt / follow_up / efficiency 점수 계산 후 state에 integrated_score, integrated_evaluation 반영. (이미 구현되어 있으면 SessionRepository.get_all_turn_analyses 존재 여부만 확인) |
| 6b-5 | Graph 연결 확인 | `app/domain/langgraph/graph.py` | eval_turn_guard → integrated_evaluator → eval_holistic_flow → aggregate_turn_scores → ... 이미 되어 있으면 변경 없음. |

- **체크리스트**  
  - [ ] 6b-4: integrated_evaluator가 DB turn_analysis 로드 후 규칙 기반 점수 계산  
  - [ ] 6b-5: graph.py 엣지 순서 확인  

### 2.3 최종 점수 통합 (6b-6)

| Task ID | 작업 | 파일 | 수정 내용 |
|---------|------|------|-----------|
| 6b-6 | integrated_score 반영 및 rubric_json 상세화 | `app/domain/langgraph/nodes/holistic_evaluator/scores.py` | aggregate_final_scores() 내부에서 state.get("integrated_score"), state.get("integrated_evaluation") 사용. prompt_score 계산 시 integrated_score 반영(가중치 적용). rubric_json에 integrated_evaluation 요약 포함. |

- **체크리스트**  
  - [ ] 6b-6: scores.py에서 integrated_score·integrated_evaluation 반영 및 rubric_json 확장  

### 2.4 (선택) Node4 + Node6 통합 평가기

| 작업 | 파일 | 수정 내용 |
|------|------|-----------|
| 통합 평가 노드 설계 | 신규 또는 `integrated_evaluator.py` 확장 | 제출 시 **한 번의 LLM 호출**로 턴별 8요소 + Chaining 평가. 입력: Redis state messages 또는 DB get_session_messages + turn_analyses. 출력: 턴별 점수 + holistic 점수. 기존 eval_turn_guard(SubGraph)와 eval_holistic_flow를 **호출하지 않고** 대체하는 단일 노드로 구현 가능. |
| Graph에서 기존 Node4/Node6 대체 | `app/domain/langgraph/graph.py` | eval_turn_guard 제출 시 턴별 SubGraph 대신 통합 평가 노드만 호출하도록 분기 변경. 또는 eval_turn_guard 내부에서 “통합 모드”일 때만 통합 LLM 호출하고, 나머지는 기존대로. |

- **체크리스트**  
  - [ ] Node4+Node6 통합 평가기 설계 (입력/출력/프롬프트)  
  - [ ] 통합 평가 노드 구현 및 graph 연결  

---

## 3. Phase 6C: 파인튜닝 데이터 자동 생성 (6c-1 ~ 6c-4)

### 3.1 스크립트 디렉터리 및 의존성

| 순서 | 작업 | 파일 | 수정 내용 |
|------|------|------|-----------|
| 0 | 디렉터리 생성 | `scripts/finetuning/` | 없으면 생성. `__init__.py` 또는 README 추가 가능. |

### 3.2 User Simulator (6c-1)

| Task ID | 작업 | 파일 | 수정 내용 |
|---------|------|------|-----------|
| 6c-1 | User Simulator 구현 | `scripts/finetuning/user_simulator.py` | 품질(bad/medium/good)별 초기 프롬프트 생성 함수. 품질별 후속 질문 생성. LLM 호출 (Gemini 등). 입력: problem_context, quality, conversation_history. 출력: prompt 문자열. |

- **체크리스트**  
  - [ ] 6c-1: user_simulator.py 작성, bad/medium/good 템플릿 또는 LLM 프롬프트 |

### 3.3 Simulation Controller (6c-2)

| Task ID | 작업 | 파일 | 수정 내용 |
|---------|------|------|-----------|
| 6c-2 | Simulation Controller 구현 | `scripts/finetuning/simulation_controller.py` | 4~5턴 시뮬레이션. 1) 초기 프롬프트 생성 2) EvalService 또는 API 호출(process_message) 3) 후속 질문 생성 4) 반복 5) 제출(submit_code) 및 평가 결과 수집. 세션 생성/재사용 정책 명시. |

- **체크리스트**  
  - [ ] 6c-2: simulation_controller.py 작성, API URL 설정 가능하도록 |

### 3.4 데이터셋 생성 파이프라인 (6c-3)

| Task ID | 작업 | 파일 | 수정 내용 |
|---------|------|------|-----------|
| 6c-3 | 데이터셋 생성 스크립트 | `scripts/finetuning/generate_dataset.py` | User Simulator + Simulation Controller 조합. 품질별 40~50개씩 생성. 출력: JSONL (input: 문제+프롬프트, output: label, score, reasoning, missing_specs, feedback). 저장 경로: `.maestro/data/finetuning/phase6_gemma/`. |

- **체크리스트**  
  - [ ] 6c-3: generate_dataset.py 작성, JSONL 출력 및 라벨 분포 로그 |

### 3.5 데이터 검수 도구 (6c-4)

| Task ID | 작업 | 파일 | 수정 내용 |
|---------|------|------|-----------|
| 6c-4 | 검수 CLI | `scripts/finetuning/review_dataset.py` | JSONL 로드, 라벨 분포 출력, 샘플별 확인 후 라벨 수정·덮어쓰기 옵션. |

- **체크리스트**  
  - [ ] 6c-4: review_dataset.py 작성 |

---

## 4. Phase 6D: Graph·State 정리 (6d-1, 6d-2)

### 4.1 MainGraphState 확장 (6d-1)

| Task ID | 작업 | 파일 | 수정 내용 |
|---------|------|------|-----------|
| 6d-1 | State 필드 추가 | `app/domain/langgraph/states.py` | spec_result, ast_analysis, modification_plan, modified_code, integrated_score, integrated_evaluation 등 이미 있으면 유지. 없으면 Optional 필드로 추가. |

- **체크리스트**  
  - [ ] 6d-1: states.py 필드 확인·추가  

### 4.2 Graph 노드·엣지 정리 (6d-2)

| Task ID | 작업 | 파일 | 수정 내용 |
|---------|------|------|-----------|
| 6d-2 | docstring 및 엣지 일치 여부 확인 | `app/domain/langgraph/graph.py` | 상단 docstring에 현재 플로우(integrated_evaluator 포함) 반영. intent_router → writer / eval_turn_guard, eval_turn_guard → integrated_evaluator → eval_holistic_flow → aggregate_turn_scores → eval_code_execution → aggregate_final_scores → END 와 실제 add_edge/add_conditional_edges 일치 확인. |

- **체크리스트**  
  - [ ] 6d-2: graph.py docstring 및 엣지 검증  

---

## 5. 실행 순서 권장 (의존성 기준)

1. **6b-1** → 6b-2 → 6b-3 (TurnAnalysis 정의 → 생성 → 저장)  
2. **6b-4** (integrated_evaluator 동작 확인), **6b-5** (graph 확인), **6b-6** (scores 반영)  
3. **6d-1**, **6d-2** (State·Graph 정리)  
4. **(선택)** 6A 그래프 연결: spec_extractor, error_injector 노드 추가 및 엣지  
5. **6c-1** → 6c-2 → 6c-3 → 6c-4 (파인튜닝 스크립트)  
6. **(선택)** Node4+Node6 통합 평가기 설계·구현  

---

## 6. 수정 시 공통 확인 사항

- **테스트**: `test_full_flow_tsp.py`, `test_submit_tsp.py` 등 기존 테스트 한 번 실행.  
- **문서**: `docs/Current_Data_Flow.md`, `docs/LangGraph_State_Flow.md`, `.maestro/docs/current_eval_flow_db_to_llm.md` 에서 변경된 노드·데이터 경로 반영.  
- **진행 반영**: `.maestro/maestro_state.json`, `.maestro/tasks/phase6_system_refactoring.json` 의 progress·status 갱신.

---

*작성: .maestro task 및 CMD_005 기준. 수정 시 이 문서와 task JSON을 함께 갱신할 것.*
