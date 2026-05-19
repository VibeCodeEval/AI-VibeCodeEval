# LangGraph 노드별 State 흐름 문서

> **작성일**: 2026-04-13  
> **목적**: 각 노드가 `MainGraphState`에서 무엇을 읽고, LLM에 무엇을 넘기며, 무엇을 State에 쓰는지 한 문서에서 파악  
> **연관 문서**: `docs/State_흐름_및_DB_저장.md`, `.maestro/docs/평가_파이프라인_플로우.md`

---

## LangGraph State 관리 원칙

LangGraph는 노드가 `Dict[str, Any]`를 반환하면 **현재 State에 얕은 병합(shallow merge)** 한다.  
`messages` 필드만 예외로 `Annotated[list, add_messages]`로 선언되어 **자동 append** 동작한다.  
`DebateState.initial_opinions`, `rebuttals`는 `operator.add`로 **병렬 팬인 시 자동 합산**된다.

---

## N1 — `handle_request` (`n1_handle_request.py`)

### State에서 읽는 값
| 필드 | 용도 |
|------|------|
| `session_id` | 로깅 |
| `current_turn` | 턴 번호 증가 기준 |
| `spec_id` | `problem_context` 없을 때 문제 정보 로드 |
| `problem_context` | 이미 있으면 로드 생략 |

### LLM 호출
없음. DB(PostgreSQL) 또는 하드코딩 딕셔너리에서 문제 정보 조회.

### State에 쓰는 값 (반환 dict)
| 필드 | 값 |
|------|----|
| `current_turn` | `current_turn + 1` |
| `is_guardrail_failed` | `False` (초기화) |
| `guardrail_message` | `None` (초기화) |
| `writer_status` | `None` (초기화) |
| `writer_error` | `None` (초기화) |
| `error_message` | `None` (초기화) |
| `updated_at` | 현재 시각 |
| `problem_context` | *(problem_context 없을 때만)* DB/하드코딩에서 로드한 전체 문제 정보 |
| `problem_id` | *(위와 같은 조건)* `basic_info.problem_id` |
| `problem_name` | `basic_info.title` |
| `problem_algorithm` | `ai_guide.key_algorithms[0]` |
| `problem_keywords` | `problem_context.keywords` |

---

## N2 — `intent_analyzer` (`n2_intent_analyzer.py`)

### State에서 읽는 값
| 필드 | 용도 |
|------|------|
| `human_message` | 분석 대상 사용자 메시지 |
| `problem_context` | 시스템 프롬프트 생성 + 문제별 키워드 가드레일 |
| `problem_id`, `problem_name`, `problem_keywords` | Layer 1 키워드 가드레일 |
| `messages` | 대화 히스토리 (Layer 1 맥락 판단) |
| `current_turn` | 턴 번호 (가드레일 맥락) |

### LLM 호출 (Layer 2)

**LLM에 넘기는 것**:
```
[SystemMessage]  intent_analyzer.yaml 템플릿 렌더링 결과
                 (problem_context → 문제 제목, 알고리즘, 입출력, 차단 기준 주입)

[HumanMessage]   human_message (사용자 원문)
```

**LLM 출력 (`IntentAnalysisResult` — Pydantic 구조화)**:
```
status           : "SAFE" | "BLOCKED"
block_reason     : "OFF_TOPIC" | "INAPPROPRIATE" | "JAILBREAK" | "DIRECT_ANSWER"(레거시) | None
request_type     : "CHAT" | "SUBMISSION"
guide_strategy   : "SYNTAX_GUIDE" | "LOGIC_HINT" | "ROADMAP" | "GENERATION" | "FULL_CODE_ALLOWED" | None
keywords         : List[str]
is_submission_request : bool
guardrail_passed : bool
violation_message: str | None
reasoning        : str
```

> Layer 1 (키워드 룰 기반)에서 차단되면 LLM 호출 없이 즉시 반환.

### State에 쓰는 값
| 필드 | 값 |
|------|----|
| `intent_status` | `"PASSED_HINT"` / `"PASSED_SUBMIT"` / `"FAILED_GUARDRAIL"` / `"FAILED_RATE_LIMIT"` |
| `is_guardrail_failed` | `not guardrail_passed` (현재 턴만; N1에서 다음 턴 시 False로 리셋) |
| `guardrail_message` | BLOCKED 시 통일 prefix + `violation_message` |
| `guardrail_flag_turns` | BLOCKED 시 `current_turn` 등록 (N1에서 **리셋하지 않음**) |
| `guardrail_turn_reasons` | `{ "1": "OFF_TOPIC", ... }` (export·DB meta용) |
| `block_reason` | BLOCKED 시 분류 코드 |
| `is_submitted` | `is_submission_request` |
| `guide_strategy` | LLM이 결정한 전략 |
| `keywords` | 핵심 키워드 리스트 |
| `intent_llm_ran` | LLM 실제 호출 여부 (Writer 이중 토큰 카운트 방지용) |
| `chat_tokens` | 토큰 사용량 누적 (`prompt_tokens`, `completion_tokens`) |
| `updated_at` | 현재 시각 |

---

## N3 — `writer` (`n3_writer.py`)

### State에서 읽는 값
| 필드 | 용도 |
|------|------|
| `human_message` | 현재 사용자 메시지 |
| `messages` | 대화 히스토리 (최대 20개 = 10턴) |
| `is_guardrail_failed` | 가드레일 위반 시 거절 응답 분기 |
| `guardrail_message` | 거절 응답 프롬프트 생성용 |
| `guide_strategy` | 응답 전략 결정 (`LOGIC_HINT` / `GENERATION` / `FULL_CODE_ALLOWED` 등) |->필요 없을듯듯
| `keywords` | 시스템 프롬프트에 핵심 키워드 주입 |
| `memory_summary` | 장기 메모리 요약 (시스템 프롬프트에 삽입) |
| `problem_context` | 문제 정보 (힌트 로드맵, 알고리즘 등) 시스템 프롬프트에 주입 |
| `spec_id` | 스마트 게이트 분기 여부 확인 (spec_id=20 → 클린/스파게티 분기) |->스마트 게이트 분기는 확인하지 않아도 됨 spec_id 자체는 남겨볼 듯
| `current_turn`, `session_id` | 메시지 turn 속성 태깅 + Redis 턴 매핑 저장 |
| `intent_llm_ran` | 사용자 프롬프트 토큰 이중 카운트 방지 |

### LLM에 넘기는 것

```
[SystemMessage]  writer_guardrail.yaml (가드레일 위반 시)
                 또는
                 writer_normal.yaml 렌더링 결과
                 (guide_strategy + problem_context + keywords + memory_summary + hint_roadmap 주입)

[이전 대화 메시지] messages[-20:] → HumanMessage / AIMessage 순서로 변환

[HumanMessage]   human_message (현재 사용자 메시지)
```

**LLM 출력**: 자유 텍스트 (구조화 출력 없음)

### State에 쓰는 값
| 필드 | 값 |
|------|----|
| `ai_message` | LLM이 생성한 응답 텍스트 |
| `messages` | `[HumanMessage(turn=N), AIMessage(turn=N)]` append (add_messages 자동 병합) |
| `writer_status` | `"SUCCESS"` / `"FAILED_RATE_LIMIT"` / `"FAILED_THRESHOLD"` / `"FAILED_TECHNICAL"` |
| `writer_error` | 에러 메시지 (정상 시 `None`) |
| `chat_tokens` | 토큰 사용량 누적 |
| `updated_at` | 현재 시각 |

---

## N4 — `eval_turn_guard` (`n4_eval_turn_guard.py`)

> 제출(PASSED_SUBMIT) 시에만 진입. 일반 채팅 플로우에서는 실행되지 않음.

### State에서 읽는 값
| 필드 | 용도 |
|------|------|
| `session_id` | Redis 저장 키, 로깅 |
| `current_turn` | 평가 대상 턴 범위 결정 (`1 ~ current_turn-1`) |
| `messages` | 전체 대화에서 턴별 (human, ai) 메시지 쌍 추출 |
| `problem_context` | 각 턴 평가 시 EvalTurnState에 전달 |
| `guardrail_flag_turns` | 채팅 N2에서 등록된 가드레일 **conversation turn** 목록 (제출 시 0점·eval 스킵 SoT) |
| `guardrail_turn_reasons` | 턴별 `block_reason` |

### 가드레일 턴 처리 (제출 시)

- `turn in guardrail_flag_turns` → eval_turn subgraph **미호출**, Redis에 0점·`GUARDRAIL_BLOCKED` 저장
- `previous_turns_summaries`·`prev_user_content`에 가드레일 턴 **미포함** (이후 턴 맥락 = **평가된 턴만**)
- 목록 없을 때만 assistant 거절 문구(prefix) **fallback**
- `spec_paste_guard`는 별도 트랙(기존 30점 로직), `guardrail_flag_turns`에 넣지 않음
- N9 추가 감점 없음; prompt 평균에는 0점 턴 **포함**

### LLM 호출

직접 호출 없음. **eval_turn_subgraph**를 가드레일이 아닌 턴에만 동기 순회 실행.  
각 턴별로 `EvalTurnState`를 구성하고 서브그래프 (8종 평가 노드) 실행:

```
EvalTurnState 입력:
  session_id, turn, human_message, ai_message
  problem_context
  previous_turns_summary (평가 완료된 이전 턴만 누적)
  intent_types, unified_intent (의도 분류)
```

서브그래프 내 LLM 호출 (eval_turn/ 노드들):
- `eval_intent_analysis.yaml` → 의도 분류
- `eval_turn.yaml` (의도별 루브릭 R1~R4) → 턴 점수 산정

### State에 쓰는 값
| 필드 | 값 |
|------|----|
| `turn_scores` | `{turn_1: {turn_score, rubrics, intent, ...}, turn_2: ...}` |
| `aggregate_turn_score` | 전체 턴 점수 평균 |
| `updated_at` | 현재 시각 |

**외부 저장**:
- Redis: `turn_logs:{session_id}:{turn}` — 턴별 상세 평가 내용 (user_prompt_summary, llm_answer_summary, rubric 상세)
- PostgreSQL: `prompt_evaluations` 테이블 (`TURN_EVAL` 타입)

---

## N5 — `eval_code_execution` (`n5_code_execution.py`)

### State에서 읽는 값
| 필드 | 용도 |
|------|------|
| `session_id`, `submission_id` | Judge0 작업 메타데이터 |
| `code_content` | 평가 대상 제출 코드 |
| `problem_context` | 테스트 케이스, 시간/메모리 제한, `test_suite_code` |
| `spec_id` | 스마트 게이트 대상 여부 (`settings.SMART_GATE_SPEC_IDS`) |
| `v2_code` | 스마트 게이트 모드 시 `v2_code + test_suite_code` 합성 |

### LLM 호출
없음. **Judge0 API** (비동기 큐) 호출:
```
JudgeTask 입력: code, language, test_cases, timeout, memory_limit
JudgeTask 출력: status, output, error, execution_time, memory_used
```

### State에 쓰는 값
| 필드 | 값 |
|------|----|
| `code_correctness_score` | 0~100 (테스트 케이스 통과 시 100, 실패 시 0) |
| `code_performance_score` | 0~100 (실행시간 + 메모리 구간별 점수) |
| `test_cases_passed` | 통과한 테스트 케이스 수 |
| `test_cases_total` | 전체 테스트 케이스 수 |
| `execution_time` | 실행 시간 (초) |
| `memory_used_mb` | 메모리 사용량 (MB) |
| `correctness_reasoning` | 스마트 게이트 실패 시 실패 원인 텍스트 |
| `updated_at` | 현재 시각 |

> Correctness 실패(0점) 시 Performance도 0점으로 즉시 반환하고 Judge0 2차 호출 생략.

---

## N6 — `eval_static_analysis` (`n6_static_analysis.py`)

### State에서 읽는 값
| 필드 | 용도 |
|------|------|
| `session_id` | 로깅 |
| `code_content` | v2 코드 (Radon CC 분석 대상) |
| `v1_code` | Phase 1 Baseline 코드 (Delta CC 계산용) |
| `spec_id` | AST 패턴 검사 적용 여부 결정 |

### LLM 호출
없음. 순수 정적 분석:
- **Radon**: `compute_radon_cc(code_content)` → avg_cc, max_cc, junior_grade
- **Delta CC**: `compute_delta_cc(v1_radon, v2_radon)` → delta_cc_pct
- **AST 패턴**: `check_ast_patterns(code_content, spec_id)` → ast_pattern_matched

### State에 쓰는 값
| 필드 | 값 |
|------|----|
| `code_quality_metrics` | `{radon_cc, v1_metrics, delta_cc, has_v1, ast_pattern_matched, ast_applicable, junior_grade}` |

---

## N7 — `eval_code_agent` (`n7_code_agent.py`)

### State에서 읽는 값
| 필드 | 용도 |
|------|------|
| `session_id` | 로깅 |
| `code_content` | 리뷰 대상 코드 원문 |
| `code_correctness_score` | N5 Judge0 점수 (프롬프트에 주입) |
| `code_performance_score` | N5 Judge0 점수 |
| `execution_time` | N5 실행 시간 |
| `memory_used_mb` | N5 메모리 사용량 |
| `code_quality_metrics` | N6 Radon CC 지표 (avg_cc, max_cc, delta_cc_pct, junior_grade) |
| `problem_context` | 문제 설명 (basic_info.description) |

### LLM에 넘기는 것

```
[SystemMessage]  SYSTEM_PROMPT (하드코딩 — 시니어 코드 리뷰 에이전트 역할,
                               효율성·가독성·예외처리·개선방향 지침)

[HumanMessage]   == 문제 설명 ==  (problem_context.basic_info.description)
                 == 제출 코드 ==  (code_content)
                 == Judge0 실행 지표 ==  (correctness/performance score, 실행시간, 메모리)
                 == Radon CC 정적 지표 ==  (avg_cc, max_cc, delta_cc_pct, junior_grade)
```

**LLM 출력 (`CodeEvalReport` — Pydantic 구조화)**:
```
efficiency_review     : 효율성 리뷰 (수치 연계)
readability_review    : 가독성 리뷰 (CC 연계)
error_handling_review : 예외처리 리뷰
overall_summary       : 종합 요약
score_adjustment_note : 학점 산정 시 정성적 패널티/가산점 의견
```

### State에 쓰는 값
| 필드 | 값 |
|------|----|
| `code_eval_report` | `CodeEvalReport.dict()` |

---

## N8 — `holistic_debate` (`n8_holistic_debate.py` + `subgraph_debate.py`)

### State에서 읽는 값 (MainGraphState)
| 필드 | 출처 |
|------|------|
| `session_id` | 세션 식별 |
| `problem_context` | 문제 정보 |
| `code_content` | 제출 코드 |
| `turn_scores`, `aggregate_turn_score` | N4 |
| `code_correctness_score`, `code_performance_score`, `test_cases_passed/total`, `execution_time`, `memory_used_mb`, `correctness_reasoning` | N5 |
| `code_quality_metrics` | N6 |
| `code_eval_report` | N7 |

**추가로 Redis에서 직접 읽음**:
```
redis_client.get_all_turn_logs(session_id)
  → filter_turn_logs_for_debate(logs, state)  # guardrail_flag_turns·GUARDRAIL_BLOCKED 제외
  → turn_logs: {turn_key: {user_prompt_summary, llm_answer_summary, prompt_evaluation_details}}
```
`turn_scores` 집계는 0점 가드레일 턴 **포함** (N9 prompt 평균과 동일).

### LLM에 넘기는 것 (subgraph_debate.py 내부, 총 7회)

**_build_base_context()** 로 컨텍스트 구성 후 각 에이전트에게 전달:
```
[컨텍스트 내용]
- 문제 정보 (problem_context)
- 제출 코드 (code_content)
- N4 Redis turn_logs (턴별 user_prompt_summary, llm_answer_summary, rubric 상세)
- N4 turn_scores (숫자 점수)
- N5 Judge0 결과 (correctness/performance, 실행시간, 메모리)
- N6 Radon CC 지표
- N7 코드 리뷰 전문
```

**Round 1 (병렬 3회)**:
```
r1_strict   : debate_agents.yaml strict 역할 프롬프트  → AgentOpinion(score, reasoning)
r1_advocate : debate_agents.yaml advocate 역할 프롬프트 → AgentOpinion(score, reasoning)
r1_neutral  : debate_agents.yaml neutral 역할 프롬프트  → AgentOpinion(score, reasoning)
```

**sync_opinions**: 3개 의견 팬인 → `initial_opinions` 누적

**Round 2 (순차 3회)**:
```
r2_strict   : R1 opinions + 컨텍스트 → rebuttal(score, stance_change, reasoning)
r2_advocate : 동일
r2_neutral  : 동일
```

**final_verdict (1회)**:
```
입력: initial_opinions + rebuttals + 컨텍스트
출력(FinalVerdict): holistic_flow_score, grade, r4_context_maintenance_score, analysis
```

### State에 쓰는 값
| 필드 | 값 |
|------|----|
| `holistic_flow_score` | 0~100 (토론 합의 기반 종합 점수) |
| `holistic_flow_analysis` | 토론 분석 요약 텍스트 |
| `r4_context_maintenance_score` | R4 대화 맥락 유지 점수 (N9 prompt_score에 반영) |
| `debate_log` | 전체 토론 기록 리스트 (rubric_json 저장용) |
| `debate_initial_opinions` | Round 1 의견 3개 |
| `debate_rebuttals` | Round 2 반박 3개 |

---

## N9 — `aggregate_final_scores` (`n9_final_scores.py`)

### State에서 읽는 값 (전 노드 누적 결과)
| 필드 | 출처 |
|------|------|
| `holistic_flow_score` | N8 |
| `r4_context_maintenance_score` | N8 |
| `aggregate_turn_score` | N4 |
| `turn_scores` | N4 (fallback 평균 계산용) |
| `code_performance_score` | N5 |
| `code_correctness_score` | N5 |
| `test_cases_passed`, `test_cases_total` | N5 |
| `execution_time`, `memory_used_mb` | N5 |
| `correctness_reasoning` | N5 |
| `code_quality_metrics` | N6 |
| `code_eval_report` | N7 |
| `holistic_flow_analysis` | N8 |
| `debate_log`, `debate_initial_opinions`, `debate_rebuttals` | N8 |
| `integrated_score`, `integrated_evaluation` | (미래 확장 대비) |
| `session_id`, `exam_id`, `participant_id`, `spec_id`, `submission_id`, `code_content` | 세션 메타데이터 |

### LLM 호출
없음. 순수 산술 집계:

```
prompt_base  = holistic_flow_score × 0.60 + aggregate_turn_score × 0.40
prompt_score = prompt_base × 0.80 + r4_context_maintenance_score × 0.20  (r4 있을 때)

perf_score  보정: Radon avg_cc ≤5 → ×1.0, ≤8 → ×0.92, >8 → ×0.84

total_score = prompt_score    × 0.40
            + correctness     × 0.40
            + performance     × 0.20

grade 결정:
  correctness < 100 → "F"(< 60점) or "D"
  correctness = 100 + code_quality_metrics 있을 때:
    delta_cc_pct ≤ 10 AND ast_ok  → "A"
    delta_cc_pct ≤ 30 AND avg_cc < 8 → "B"
    그 외 → "C"
```

### State에 쓰는 값
| 필드 | 값 |
|------|----|
| `final_scores` | `{prompt_score, performance_score, correctness_score, total_score, grade, v21_summary, correctness_details, performance_details}` |
| `updated_at` | 현재 시각 |

**외부 저장 (PostgreSQL)**:
- `submissions` 테이블: `status → DONE`
- `scores` 테이블: 점수 4개 + `rubric_json` (전 노드 결과 전체 포함)
- `sessions` 테이블: `ended_at` 설정

---

## 전체 State 흐름 요약 다이어그램

```
                         [MainGraphState 초기값]
                    session_id, exam_id, spec_id, human_message
                                    │
                   ┌────────────────▼────────────────┐
              N1   │ handle_request                  │
                   │ WRITE: current_turn+1            │
                   │        problem_context           │
                   │        상태 필드 초기화          │
                   └────────────────┬────────────────┘
                                    │
                   ┌────────────────▼────────────────┐
              N2   │ intent_analyzer  (LLM × 1)      │
                   │ READ:  human_message             │
                   │        problem_context           │
                   │        messages (히스토리)       │
                   │ LLM→:  System(문제정보+규칙)     │
                   │        Human(human_message)      │
                   │ WRITE: intent_status             │
                   │        is_submitted              │
                   │        guide_strategy            │
                   │        chat_tokens               │
                   └────────────────┬────────────────┘
                          ┌─────────┴──────────┐
                    일반채팅              제출(SUBMIT)
                          │                    │
          ┌───────────────▼──────┐  ┌──────────▼──────────────────┐
     N3   │ writer  (LLM × 1)   │  │ N4 eval_turn_guard          │
          │ READ: messages[-20:] │  │ READ: messages(전체)        │
          │       guide_strategy │  │       problem_context       │
          │       problem_context│  │ SUBGRAPH(각 턴):            │
          │ LLM→: System(프롬프트│  │   LLM × N턴 × 평가노드     │
          │         +문제+전략)  │  │ WRITE: turn_scores          │
          │       History(20개)  │  │        aggregate_turn_score │
          │       Human(메시지)  │  │ EXT→: Redis turn_logs       │
          │ WRITE: ai_message    │  │        PG prompt_evaluations│
          │        messages+=[..]│  └──────────┬──────────────────┘
          │        chat_tokens   │             │
          └────────┬─────────────┘  ┌──────────▼──────────────────┐
                   │                │ N5 eval_code_execution      │
                  END               │ READ: code_content          │
                                    │       problem_context       │
                                    │ API→: Judge0                │
                                    │ WRITE: code_correctness_score│
                                    │        code_performance_score│
                                    │        execution_time        │
                                    │        memory_used_mb        │
                                    └──────────┬──────────────────┘
                                               │
                                    ┌──────────▼──────────────────┐
                               N6   │ eval_static_analysis        │
                                    │ READ: code_content, v1_code │
                                    │ TOOL: Radon CC + AST        │
                                    │ WRITE: code_quality_metrics │
                                    └──────────┬──────────────────┘
                                               │
                                    ┌──────────▼──────────────────┐
                               N7   │ eval_code_agent (LLM × 1)  │
                                    │ READ: code_content          │
                                    │       N5 지표, N6 지표      │
                                    │       problem_context       │
                                    │ LLM→: System(코드리뷰지침) │
                                    │        Human(코드+지표)     │
                                    │ WRITE: code_eval_report     │
                                    └──────────┬──────────────────┘
                                               │
                                    ┌──────────▼──────────────────┐
                               N8   │ holistic_debate (LLM × 7)  │
                                    │ READ: N4~N7 State 전체      │
                                    │ EXT←: Redis turn_logs       │
                                    │ SUBGRAPH(debate):           │
                                    │   R1 병렬(strict/adv/neut)  │
                                    │   sync_opinions             │
                                    │   R2 순차(strict/adv/neut)  │
                                    │   final_verdict             │
                                    │ WRITE: holistic_flow_score  │
                                    │        r4_context_score     │
                                    │        debate_log           │
                                    └──────────┬──────────────────┘
                                               │
                                    ┌──────────▼──────────────────┐
                               N9   │ aggregate_final_scores      │
                                    │ READ: N4~N8 점수 전체       │
                                    │ CALC: total_score, grade    │
                                    │ WRITE: final_scores         │
                                    │ EXT→: PG scores + rubric_json│
                                    │        PG submissions DONE  │
                                    │        PG sessions ended_at │
                                    └──────────┬──────────────────┘
                                               │
                                              END
```

---

## State 필드 생애주기 요약

| 필드 | 최초 작성 | 마지막 사용 | 비고 |
|------|-----------|------------|------|
| `current_turn` | N1 | N4 | 매 턴 +1 |
| `problem_context` | N1 (또는 초기) | N7, N8 | 전 노드 공유 |
| `messages` | N3 (append) | N4 | `add_messages` 자동 누적 |
| `intent_status`, `guide_strategy` | N2 | N3 | 채팅 플로우 |
| `is_submitted` | N2 | intent_router | 제출 분기 키 |
| `ai_message` | N3 | — | 현재 턴 AI 응답 |
| `chat_tokens` | N2 | N3 | 토큰 누적 |
| `turn_scores` | N4 | N8, N9 | 턴별 점수 딕셔너리 |
| `aggregate_turn_score` | N4 | N9 | 턴 평균 점수 |
| `code_correctness_score` | N5 | N7, N8, N9 | 정확성 점수 |
| `code_performance_score` | N5 | N8, N9 | 성능 점수 |
| `code_quality_metrics` | N6 | N8, N9 | 정적 분석 결과 |
| `code_eval_report` | N7 | N8, N9 | LLM 코드 리뷰 |
| `holistic_flow_score` | N8 | N9 | 토론 종합 점수 |
| `r4_context_maintenance_score` | N8 | N9 | 맥락 유지 점수 |
| `debate_log` | N8 | N9 (rubric_json) | 토론 기록 전체 |
| `final_scores` | N9 | END | 최종 출력 |
