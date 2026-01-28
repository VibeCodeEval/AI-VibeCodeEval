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

## 4. Phase 6B: 평가 노드 통합

### 4.1 통합 구조

**현재**:
```
Turn Evaluator (8개 개별 함수)
├── eval_system_prompt
├── eval_rule_setting
├── eval_generation
├── eval_optimization
├── eval_debugging
├── eval_test_case
├── eval_hint_query
└── eval_follow_up

Holistic Flow (별도 노드)
└── eval_holistic_flow
```

**변경 후**:
```
Integrated Evaluator (단일 통합 평가기)
├── Turn 평가 (기존 8의도 로직 유지)
├── Holistic Flow 평가 (기존 로직 유지)
└── Spec 충족 평가 (신규)
```

### 4.2 Spec 충족 평가 (신규)

```python
class SpecFulfillmentEvaluation(BaseModel):
    spec_fulfillment_score: float    # Spec 충족률 (0-100)
    missing_spec_penalty: float      # 누락 Spec 감점
    clarity_score: float             # 프롬프트 명확성
    details: List[SpecEvalDetail]    # 각 Spec별 평가
```

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
Phase 6A: AST 기반 코드 생성
[ ] 6a-1: Spec Extractor 구현
[ ] 6a-2: AST Analyzer 구현
[ ] 6a-3: Spec-AST Mapper 구현
[ ] 6a-4: Error Injector 구현
[ ] 6a-5: Writer 리팩토링

Phase 6B: 평가 노드 통합
[ ] 6b-1: Turn Evaluator 통합
[ ] 6b-2: Holistic Flow 통합
[ ] 6b-3: Spec 충족 평가 추가
[ ] 6b-4: Gemini 3.0 업그레이드

Phase 6C: 파인튜닝 데이터 생성
[ ] 6c-1: User Simulator 구현
[ ] 6c-2: Simulation Controller 구현
[ ] 6c-3: 데이터셋 생성 파이프라인
[ ] 6c-4: 데이터 검수 도구

Phase 6D: Graph 구조 변경
[ ] 6d-1: MainGraphState 수정
[ ] 6d-2: Graph 노드 연결 변경
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
