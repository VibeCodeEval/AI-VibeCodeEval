# LangGraph API·LLM 호출 맵

> **목적**: 메인 그래프와 서브그래프를 **Chat / Eval**로 구분해, 노드별 **외부 LLM(Gemini·Vertex)** 및 **Judge0** 등 호출을 정리한다.  
> **근거 코드**: `app/domain/langgraph/graph.py`, `subgraph_eval_turn.py`, `subgraph_debate.py`, `nodes/chat/*`, `nodes/eval/*`, `nodes/eval_turn/*`, `nodes/system/system_nodes.py`  
> **참고 문서**: `.maestro/agents/AGENT_OVERVIEW.md`, `.maestro/agents/project_maestro.md`, `.maestro/agents/graph_orchestrator.md` (계층·역할만 기술, 호출 횟수는 본 문서)  
> **비용 추정**: [Gemini_API_Cost_Estimate.md](./Gemini_API_Cost_Estimate.md)

---

## 1. 그래프 관련 파일

| 구분 | 경로 | 역할 |
|------|------|------|
| 메인 그래프 | `app/domain/langgraph/graph.py` | START→handle_request→intent→(writer \| eval_turn_guard)→…→END |
| 턴 평가 서브그래프 | `app/domain/langgraph/subgraph_eval_turn.py` | N4에서 `create_eval_turn_subgraph()`로 생성 후 `ainvoke` |
| 토론 서브그래프 | `app/domain/langgraph/subgraph_debate.py` | N8에서 `create_debate_subgraph()`로 생성 후 `ainvoke` |

`project_maestro.md` 상의 대응:

- **채팅 루프**: n1 → n2 → n3 (+ system 노드)
- **평가**: n4 + eval_turn 서브그래프 → n5~n9 (N8에서 토론 서브그래프)

---

## 2. 메인 그래프 엣지 요약

- **START** → `handle_request` → `intent_analyzer` → `intent_router`  
  - `writer` | `handle_failure` | `summarize_memory` | `handle_request` | `eval_turn_guard`
- `writer` → `writer_router` → `end`(END) | `handle_failure` | `summarize_memory` | `handle_request`
- `eval_turn_guard` → `main_router` → `eval_code_execution`(N5) | `handle_request` | `end`
- `handle_failure` → `main_router` (동일 분기 키)
- `summarize_memory` → `handle_request`
- **제출 후 평가 체인**: N5 → N6 → N7 → N8 → N9 → END

### 알려진 불일치 (코드 점검 시 참고)

`app/domain/langgraph/nodes/chat/routers.py`의 `writer_router`는 `"eval_turn"`을 반환할 수 있으나, **`graph.py`의 `writer` 조건부 엣지 맵에 `eval_turn` 키가 없어** 현재 컴파일 그래프에서는 해당 분기가 연결되지 않는다.

---

## 3. Chat 구간 — 노드별 호출

| 노드 | LLM (Gemini / Vertex) | 기타 |
|------|------------------------|------|
| n1 `handle_request` | 없음 | Redis, 필요 시 DB `get_problem_info` |
| n2 `intent_analyzer` | **최소 1회** `llm.ainvoke`; 파싱 실패 시 **추가 1회** `structured_llm.ainvoke` | — |
| n3 `writer` | **1회** `chain.ainvoke` | — |
| `handle_failure` | 없음 | — |
| `summarize_memory` | 메시지 개수 ≥ 10일 때 **1회** `get_llm().ainvoke` | — |

### 일반 채팅 1요청(제출 아님, 성공 경로)

- 대략 **LLM 2~3회**: 의도(1~2) + Writer(1)
- `summarize_memory` 경로 시 **+1회**

### 제출 의도만 처리하는 1요청 (`intent_router` → `eval_turn_guard`)

- **Writer 미실행** → 의도 분석과 동일하게 **LLM 약 1~2회**

---

## 4. Eval 구간 — 노드별 호출

### 4.1 N4 `eval_turn_guard` + Eval Turn 서브그래프

- **평가 대상 턴**: `turns_to_evaluate = range(1, current_turn)`  
  - 예: 제출 요청 직전 `handle_request` 이후 `current_turn == 6`이면 턴 **1~5** 각각 서브그래프 1회(단, 아래 SAVE 예외).
- **SAVE 턴**: 사용자 메시지가 `SAVE`(대소문자 무시)인 턴은 N4에서 **평가 생략**(서브그래프 미호출).

서브그래프 흐름 (`subgraph_eval_turn.py`):

`START` → `intent_analysis` → `intent_router`(단일 노드 리스트) → 의도별 평가 노드 1개 → `summarize_answer` → `aggregate_turn_log` → END

| 단계 | LLM | 비고 |
|------|-----|------|
| `intent_analysis` | **1~2회+α** | 특성 추출: `llm.ainvoke` + (실패 시) 구조화 재호출. 규칙으로 의도 확정 시 추가 없음; 애매하면 `_disambiguate_intent_llm`으로 **추가 1~2회** |
| 의도별 평가 노드 1개 | **1~2회** | `_evaluate_turn`: 원본 `ainvoke` + 구조화 파싱(실패 시 `structured_llm.ainvoke`) |
| `summarize_answer` | **0~1회** | `ai_message` 없으면 스킵 |
| `aggregate_turn_log` | 없음 | 집계만 |

**턴당(서브그래프 1회) 대략**: LLM **3~6회** (폴백·의도 분기에 따라 변동).

### 4.2 N5 `eval_code_execution`

- **Judge0(작업 큐)**: Correctness용 **`JudgeTask` 1회** enqueue 후 폴링.
- Performance 점수는 **동일 Correctness 실행 결과의 시간·메모리**로 계산(별도 Judge 태스크 없음).
- Correctness 실패 시 Performance 평가 생략 분기 있음(코드 내 `skip_performance`).

### 4.3 N6 `eval_static_analysis`

- **LLM 없음** — Radon CC 등 로컬 정적 분석.

### 4.4 N7 `eval_code_agent` (코드 리뷰)

- **구조화 출력 LLM 1회** (`structured_llm.ainvoke`).

### 4.5 N8 `holistic_debate` + `subgraph_debate.py`

| 단계 | LLM 호출 수 |
|------|-------------|
| Round 1 (병렬: strict / advocate / neutral) | **3** |
| Round 2 (순차: strict → advocate → neutral) | **3** |
| `final_verdict` | **1** |
| **합계(정상 경로)** | **7회 / 제출 1건** |

예외 시 LLM 대신 휴리스틱 폴백 분기 있음.

### 4.6 N9 `aggregate_final_scores`

- **LLM 없음** — 가중치·등급 산출 및 저장 로직.

---

## 5. 시나리오 예시: 대화 5번 + 제출 1번

**가정**

- 일반 메시지 5번: 매번 n2 + n3 성공, `summarize_memory` 미경유.
- 제출 6번째 요청: `intent_router` → `eval_turn_guard`만 (Writer 없음).
- 제출 시점 `current_turn == 6` → Eval Turn 대상 **턴 1~5**, SAVE 스킵 없음.
- N5 Judge0 성공 플로우.

| 구간 | LLM (대략) | Judge0 |
|------|------------|--------|
| 채팅 5요청 | 5 × (2~3) ≈ **10~15** | — |
| 제출 요청(의도만) | **1~2** | — |
| Eval Turn ×5 | 5 × (3~6) ≈ **15~30** | — |
| N7 + N8 | **1 + 7 = 8** | — |
| N5 | — | **1** |

**LLM 합(발생 구간)**: 대략 **34~55회** + 파싱·의도 폴백·메모리 요약 시 증가.  
**HTTP 클라이언트→백엔드** 관점에서 메시지 API가 5+1이면 **6회**(제출이 별도 엔드포인트/동일 엔드포인트 여부는 API 설계에 따름).

---

## 6. 유지보수 시 확인 포인트

1. **`graph.py`와 `writer_router`**: `eval_turn` 분기를 쓸 계획이면 엣지 맵에 반영 필요.
2. **N4 턴 범위**: `current_turn` 증가 시점(`n1`)과 제출 시점을 바꾸면 Eval Turn 호출 횟수가 달라진다.
3. **SAVE / 가드레일 / 재시도**: 실제 호출 수는 이 분기들에 의해 줄거나 늘 수 있다.

---

## 7. 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-04-05 | 초안 작성; Gemini 비용 문서(`Gemini_API_Cost_Estimate.md`) 링크 추가 |
