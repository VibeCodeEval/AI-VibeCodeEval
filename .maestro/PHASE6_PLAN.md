# Phase 6: 시스템 리팩토링 계획

> AST 기반 코드 생성 + 평가 통합 + 파인튜닝 데이터 자동 생성

**작성일**: 2026-01-26
**상태**: Planning
**우선순위**: High

---

## 1. 개요

### 1.1 현재 시스템
```
사용자 프롬프트 → Intent Analyzer (가드레일) → Writer (Socratic 힌트) → 평가
                      ↓
              정답 코드 직접 제공 X
              힌트/가이드만 제공
```

### 1.2 목표 시스템
```
사용자 프롬프트 → Spec Extractor → AST Analyzer → Error Injector → Writer → 평가
                      ↓                 ↓                ↓
              누락 Spec 추출      정답 코드 분석    누락 부분 변형
                                                        ↓
                                              의도적으로 불완전한 코드 제공
```

### 1.3 핵심 변경 사항
| 항목 | 현재 | 변경 후 |
|------|------|---------|
| Writer 역할 | Socratic (힌트만) | 코드 직접 생성 |
| 코드 품질 | N/A | Spec 명확성에 비례 |
| 오답 생성 | 없음 | AST 기반 변형 |
| 평가 구조 | 분리 (8의도 + Holistic) | 통합 |

---

## 2. 실행 순서

```
┌─────────────────────────────────────────────────────────────────┐
│ Phase 6A: AST 기반 코드 생성 시스템                              │
│ ├── 6a-1: Spec Extractor 구현                                   │
│ ├── 6a-2: AST Analyzer 구현                                     │
│ ├── 6a-3: Spec-AST Mapper 구현                                  │
│ ├── 6a-4: Error Injector 구현                                   │
│ └── 6a-5: Writer 노드 리팩토링                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Phase 6B: 평가 노드 통합                                         │
│ ├── 6b-1: Turn Evaluator 통합                                   │
│ ├── 6b-2: Holistic Flow 통합                                    │
│ ├── 6b-3: Spec 충족 평가 추가                                   │
│ └── 6b-4: Gemini 3.0 업그레이드                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Phase 6C: 파인튜닝 데이터 자동 생성                              │
│ ├── 6c-1: User Simulator 구현                                   │
│ ├── 6c-2: Simulation Controller 구현                            │
│ ├── 6c-3: 데이터셋 생성 파이프라인                               │
│ └── 6c-4: 데이터 검수 도구                                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Phase 6D: Graph 구조 변경                                        │
│ ├── 6d-1: MainGraphState 수정                                   │
│ └── 6d-2: Graph 노드 연결 변경                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Phase 6A: AST 기반 코드 생성 시스템

### 3.1 핵심 개념: 역할 분담

```
      "무엇이 부족한가?"          "어디를 바꿀까?"         "어떻게 바꿀까?"
            │                        │                        │
            ▼                        ▼                        ▼
    ┌───────────────┐        ┌───────────────┐        ┌───────────────┐
    │     LLM       │        │     AST       │        │     LLM       │
    │ (Spec 추출)   │   →    │ (위치 지정)   │   →    │ (코드 변형)   │
    └───────────────┘        └───────────────┘        └───────────────┘
         창의적                   결정론적                  창의적
```

### 3.2 Task 6a-1: Spec Extractor

**목적**: 사용자 프롬프트에서 명시된/누락된 요구사항 추출

**파일**: `app/domain/langgraph/nodes/spec_extractor.py`

**입력**:
```python
{
    "user_prompt": "DP로 외판원 문제 풀어줘. 시간복잡도 O(N²·2ⁿ)으로.",
    "problem_context": {
        "basic_info": {"title": "외판원 순회"},
        "ai_guide": {"key_algorithms": ["DP", "비트마스킹"]}
    }
}
```

**출력**:
```python
class SpecResult(BaseModel):
    specified_requirements: List[str]  # ["DP", "시간복잡도 O(N²·2ⁿ)"]
    missing_requirements: List[MissingSpec]  # [{"category": "비트마스킹", ...}]
    ambiguous_requirements: List[str]  # ["상태 정의 불명확"]
```

### 3.3 Task 6a-2: AST Analyzer

**목적**: 정답 코드를 AST로 분석하여 구성 요소 식별

**파일**: `app/domain/langgraph/ast_injector/analyzer.py`

**구성 요소 유형**:
```python
class ComponentType(Enum):
    FUNCTION_DEF = "function_definition"      # 함수 정의
    BASE_CASE = "base_case"                   # 기저 조건
    RECURSIVE_CALL = "recursive_call"         # 재귀 호출
    MEMOIZATION = "memoization"               # 메모이제이션
    BIT_OPERATION = "bit_operation"           # 비트 연산
    LOOP_STRUCTURE = "loop_structure"         # 루프 구조
    STATE_TRANSITION = "state_transition"     # 상태 전이 (점화식)
```

**분석 예시** (백준 2098 외판원 순회):
```
정답 코드 분석 결과:
├── FUNCTION_DEF: tsp (line 10-20)
├── MEMOIZATION: @lru_cache (line 9)
├── BASE_CASE: if visited == (1 << n) - 1 (line 12-13)
├── BIT_OPERATION: visited & (1 << next_city) (line 17)
├── BIT_OPERATION: visited | (1 << next_city) (line 18)
└── STATE_TRANSITION: result = min(...) (line 18)
```

### 3.4 Task 6a-3: Spec-AST Mapper

**목적**: 누락된 Spec과 AST 구성 요소 매핑

**파일**: `app/domain/langgraph/ast_injector/mapper.py`

**매핑 테이블**:
```python
SPEC_MAPPING = {
    "기저조건": [ComponentType.BASE_CASE],
    "메모이제이션": [ComponentType.MEMOIZATION],
    "비트마스킹": [ComponentType.BIT_OPERATION],
    "점화식": [ComponentType.STATE_TRANSITION],
    "시간복잡도": [ComponentType.LOOP_STRUCTURE, ComponentType.RECURSIVE_CALL],
}
```

### 3.5 Task 6a-4: Error Injector

**목적**: AST 기반으로 코드 변형

**파일**: `app/domain/langgraph/ast_injector/injector.py`

**변형 유형**:
```python
class ModificationType(Enum):
    REMOVE = "remove"              # 완전 제거
    SIMPLIFY = "simplify"          # 단순화
    MAKE_INCORRECT = "incorrect"   # 잘못된 로직
    MAKE_INCOMPLETE = "incomplete" # 불완전하게
    REPLACE_ALGORITHM = "replace"  # 다른 알고리즘 대체
```

**변형 예시**:
- 비트마스킹 미명시 → 비트 연산을 집합(set)으로 대체 (비효율적)
- 메모이제이션 미명시 → @lru_cache 제거
- 기저조건 미명시 → 기저조건 불완전하게 처리

### 3.6 Task 6a-5: Writer 리팩토링

**목적**: Socratic → Spec 기반 코드 생성

**변경 사항**:
1. 가드레일 완화 (코드 생성 허용)
2. 정답 코드 + AST 변형 코드 생성
3. Spec 충족도에 따른 코드 품질 결정

---

## 4. Phase 6B: Spec 중심 통합 평가 시스템

> **2026-01-29 업데이트**: 기존 계획을 "Spec 중심 통합 평가"로 재설계

### 4.1 핵심 철학 변경

```
┌─────────────────────────────────────────────────────────────────┐
│ "불완전한 코드는 첫 프롬프트의 불완전한 Spec에서 비롯된다"       │
│                                                                 │
│ → 첫 프롬프트 품질이 가장 중요 (55% 가중치)                     │
│ → 후속 턴은 보완/회복 (25%)                                     │
│ → 효율성은 부수적 (20%)                                         │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 평가 지표 변경

**AS-IS (기존 43+ 개별 지표)**:
```
Turn Evaluator (8개 의도 × 5개 루브릭 = 40개)
├── eval_system_prompt
├── eval_rule_setting
├── eval_generation
├── eval_optimization
├── eval_debugging
├── eval_test_case
├── eval_hint_query
└── eval_follow_up

Holistic Flow (3개 지표)
└── problem_decomposition, feedback_integration, strategic_exploration
```

**TO-BE (6개 핵심 지표)**:
```
Integrated Evaluator (Spec 중심)
├── 1. Spec 완전성 (35%) - 필수 Spec 명시 여부
├── 2. 명확성 (7%) - 구체적 값, 조건 명시
├── 3. 구조화 (7%) - XML 태그, 마크다운 활용
├── 4. 예시/구체성 (6%) - I/O 예시, 엣지 케이스
├── 5. 맥락 연결 (15%) - 이전 턴 참조, Spec 회복
└── 6. 효율성 (20%) - 턴 수, 회복 속도
```

### 4.3 가중치 구조

```
┌─────────────────────────────────────────────────────────────────┐
│ 첫 프롬프트 (55%)                                               │
│ ├── Spec 완전성 (35%)                                          │
│ └── 표현 품질 (20%) = 명확성(7%) + 구조화(7%) + 예시(6%)        │
├─────────────────────────────────────────────────────────────────┤
│ 후속 턴 (25%)                                                   │
│ ├── 맥락 연결 (15%) - 이전 턴 참조 품질                         │
│ └── Spec 회복 (10%) - 누락 Spec 보완 품질                       │
├─────────────────────────────────────────────────────────────────┤
│ 효율성 (20%)                                                    │
│ ├── 턴 수 효율성 - 적은 턴으로 완료                             │
│ └── 회복 속도 - 빠른 Spec 보완                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.4 데이터 저장 전략

```
[대화 중 - 매 턴]
User 입력 → Spec Extractor → TurnAnalysis 생성
                                    │
                                    ▼
                    PostgreSQL prompt_messages.meta에 저장
                    {
                      "turn_analysis": {
                        "is_first_prompt": true,
                        "spec_completeness": 20,
                        "clarity_score": 25,
                        "has_structure": false,
                        "has_examples": false,
                        "spec_recovery_count": 0,
                        "summary": "DP만 명시, 세부 요구사항 없음"
                      }
                    }

[제출 시]
PostgreSQL에서 turn_analysis 조회
    │
    ▼
Integrated Evaluator (규칙 기반, LLM 호출 없음)
    │
    ▼
scores 테이블에 최종 점수 저장
```

### 4.5 Context Window 최적화

```
AS-IS: 원본 대화 전체 → LLM (5000+ 토큰)
TO-BE: turn_analysis 배열 → 규칙 기반 (500 토큰)

약 90% 토큰 절감
```

### 4.6 Task 상세

| Task ID | 작업 | 파일 | 설명 |
|---------|------|------|------|
| 6b-1 | TurnAnalysis 모델 정의 | `states.py` | Pydantic 모델 추가 |
| 6b-2 | Spec Extractor 확장 | `spec_extractor.py` | TurnAnalysis 생성 로직 |
| 6b-3 | TurnAnalysis 저장 | `eval_service.py` | meta에 저장 로직 |
| 6b-4 | Integrated Evaluator | `integrated_evaluator.py` (신규) | 통합 평가 노드 |
| 6b-5 | Graph 연결 | `graph.py` | 노드 연결 |
| 6b-6 | 최종 점수 통합 | `scores.py` | rubric_json 상세 저장 |

### 4.7 기존 호환성

```
✅ 유지 항목:
- Redis turn_logs 저장 (기존 eval_holistic_flow 호환)
- TURN_EVAL, HOLISTIC_FLOW 평가 (기존 로직 유지)
- scores 테이블 구조 (변경 없음)

🆕 추가 항목:
- prompt_messages.meta에 turn_analysis 저장
- Integrated Evaluator 노드
- 6개 핵심 지표 기반 점수 계산
```

### 4.8 현재 구현 상태 vs 목표 (2026-01-29 정리)

**실제 구현된 제출 시 플로우**:
```
eval_turn_guard (Node4)
  → 턴마다 Eval Turn SubGraph 실행 (8가지 의도 LLM 평가)  ← 그대로 유지
  → main_router
  → integrated_evaluator (규칙 기반만, LLM 없음)           ← 6B에서 추가
  → eval_holistic_flow (Node6, LLM)                      ← 그대로 유지
  → aggregate_turn_scores → eval_code_execution → aggregate_final_scores
```

**목표였던 설계**:
- Node4(턴별 8의도 LLM) + Node6(Holistic Flow LLM) 을 **통합해서 한번에** 진행
- 제출 시 **하나의 통합 평가기**가 LLM as Judge로 사용자 프롬프트 품질 평가 (8요소 + Chaining)
- 6개 핵심 지표로 정리하되, **평가 자체는 LLM**으로 수행

**갭 (미완료)**:
| 항목 | 현재 | 목표 |
|------|------|------|
| Node4·Node6 통합 | ❌ 분리 실행 (Node4 → Node6 순차) | ✅ 통합해서 한번에 진행 |
| 사용자 프롬프트 LLM 평가 | ✅ Node4에서 8의도 LLM 유지 | ✅ 유지 (통합 평가기 내에서 수행하기로 함) |
| Integrated Evaluator | 규칙 기반만 (TurnAnalysis 합산) | LLM as Judge 포함 통합 평가기로 확장 예정 |

**정리**: 6b-1~6b-6 구현은 완료되었으나, "Node4 + Node6 통합해서 한번에" 는 **미구현**.  
추가 작업: 제출 시 **통합 평가 노드 하나**에서 구조화 데이터(TurnAnalysis 등) + LLM 호출로 8요소·Chaining을 한번에 평가하는 설계 및 구현 필요.

---

## 5. Phase 6C: 파인튜닝 데이터 자동 생성

### 5.1 시뮬레이션 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│ User Simulator (LLM)                                            │
│ ├── 품질별(bad/medium/good) 초기 프롬프트 생성                   │
│ └── 후속 질문 생성                                               │
└─────────────────────────────────────────────────────────────────┘
                              ↕ API 호출
┌─────────────────────────────────────────────────────────────────┐
│ 현재 시스템 (Writer + Evaluator)                                 │
│ ├── /api/chat - AI 응답 생성                                    │
│ └── /api/chat/submit - 평가 실행                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 데이터셋 저장 (.maestro/data/finetuning/phase6_gemma/)          │
│ ├── bad_samples.jsonl (40-50개)                                 │
│ ├── medium_samples.jsonl (40-50개)                              │
│ └── good_samples.jsonl (40-50개)                                │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 데이터 형식

**JSONL 형식**:
```json
{"input": "[문제 정보]\n문제: 외판원 순회\n알고리즘: DP, 비트마스킹\n\n[사용자 프롬프트]\n정답 코드 알려줘\n\n위 프롬프트를 평가하세요.", "output": "{\"label\": \"bad\", \"score\": 10, \"reasoning\": \"정답을 직접 요청\", \"missing_specs\": [\"알고리즘\", \"시간복잡도\"], \"feedback\": \"구체적인 요구사항을 명시하세요.\"}"}
```

### 5.3 품질별 프롬프트 특징

| 품질 | 점수 | 특징 |
|------|------|------|
| **bad** | 0-40 | 정답 직접 요청, 모호한 지시, 핵심 Spec 누락 |
| **medium** | 41-70 | 부분적 Spec 명시, 개선 여지 있음 |
| **good** | 71-100 | 완벽한 Spec, XML 태그, 구조화된 포맷 |

---

## 6. Phase 6D: Graph 구조 변경

### 6.1 새로운 Graph 구조

```python
# graph.py

# 노드 추가
builder.add_node("spec_extractor", spec_extractor)
builder.add_node("ast_analyzer", ast_analyzer)
builder.add_node("error_injector", error_injector)
builder.add_node("integrated_evaluator", integrated_evaluator)

# 엣지 연결
builder.add_edge(START, "handle_request")
builder.add_edge("handle_request", "spec_extractor")
builder.add_edge("spec_extractor", "ast_analyzer")
builder.add_edge("ast_analyzer", "error_injector")
builder.add_edge("error_injector", "writer")
builder.add_edge("writer", "integrated_evaluator")
builder.add_edge("integrated_evaluator", "code_execution")
builder.add_edge("code_execution", "final_scores")
builder.add_edge("final_scores", END)
```

### 6.2 State 확장

```python
class MainGraphState(TypedDict):
    # 기존 필드...
    
    # 신규 필드
    spec_result: Optional[Dict[str, Any]]       # Spec 추출 결과
    ast_analysis: Optional[Dict[str, Any]]      # AST 분석 결과
    modification_plan: Optional[Dict[str, Any]] # 변형 계획
    modified_code: Optional[str]                # 변형된 코드
```

---

## 7. 진행 상태 추적

### 체크리스트

```
Phase 6A: AST 기반 코드 생성 ✅ COMPLETED (2026-01-29)
[x] 6a-1: Spec Extractor 구현
[x] 6a-2: AST Analyzer 구현
[x] 6a-3: Spec-AST Mapper 구현
[x] 6a-4: Error Injector 구현
[x] 6a-5: Writer 리팩토링

Phase 6B: Spec 중심 통합 평가 ✅ COMPLETED (2026-01-29)
[x] 6b-1: TurnAnalysis 모델 정의 (states.py)
[x] 6b-2: Spec Extractor 확장 - TurnAnalysis 생성
[x] 6b-3: TurnAnalysis 저장 로직 (prompt_messages.meta)
[x] 6b-4: Integrated Evaluator 노드 생성 (신규 파일)
[x] 6b-5: Graph 노드 연결
[x] 6b-6: 최종 점수 통합 (scores.py 수정)

Phase 6C: 파인튜닝 데이터 생성
[ ] 6c-1: User Simulator 구현
[ ] 6c-2: Simulation Controller 구현
[ ] 6c-3: 데이터셋 생성 파이프라인
[ ] 6c-4: 데이터 검수 도구

Phase 6D: Graph 구조 변경
[x] 6d-1: MainGraphState 수정 (Phase 6A에서 선행 완료)
[ ] 6d-2: Graph 노드 연결 변경 (Phase 6B와 통합)
```

---

## 8. 참고 문서

- 상세 태스크 정의: `.maestro/tasks/phase6_system_refactoring.json`
- 명령 파일: `.maestro/commands/pending/CMD_005_phase6_refactoring.json`
- 기존 평가 로직: `app/domain/langgraph/nodes/turn_evaluator/`
- 기존 Writer: `app/domain/langgraph/nodes/writer.py`
- 문제 정보: `app/domain/langgraph/utils/problem_info.py`

---

## 9. 완료 보고 형식

작업 완료 시 `.maestro/commands/completed/CMD_005_phase6_refactoring_COMPLETED.json` 파일 생성:

```json
{
  "command_id": "CMD_005",
  "completed_at": "2026-XX-XXTXX:XX:XXZ",
  "agent": "sub_agent_refactoring",
  "status": "completed",
  "result": {
    "files_created": [...],
    "files_modified": [...],
    "tests_passed": true,
    "dataset_generated": {
      "bad": 50,
      "medium": 50,
      "good": 50,
      "total": 150
    },
    "notes": "..."
  }
}
```

---

*Created by Maestro Agent - 2026-01-26*
