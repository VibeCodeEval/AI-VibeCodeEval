# Node 4 (Turn Evaluator) 입력/출력 형식 가이드

## 📋 개요

Node 4 (Turn Evaluator)는 사용자 프롬프트와 AI 응답을 평가하여 `prompt_evaluations` 테이블의 `details` (JSONB) 필드에 저장합니다.

## 🗄️ 데이터베이스 스키마

### `prompt_evaluations` 테이블

```sql
CREATE TABLE prompt_evaluations (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES prompt_sessions(id) ON DELETE CASCADE,
    turn INTEGER,  -- TURN_EVAL: NOT NULL, HOLISTIC_FLOW: NULL
    evaluation_type evaluation_type_enum NOT NULL,  -- 'TURN_EVAL' | 'HOLISTIC_FLOW'
    details JSONB NOT NULL,  -- 모든 평가 데이터 저장
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- 제약 조건
    CONSTRAINT check_valid_turn_logic CHECK (
        (evaluation_type::text = 'HOLISTIC_FLOW' AND turn IS NULL) OR
        (evaluation_type::text = 'TURN_EVAL' AND turn IS NOT NULL)
    ),
    
    -- Unique 제약
    UNIQUE(session_id, turn, evaluation_type) WHERE evaluation_type = 'TURN_EVAL',
    UNIQUE(session_id) WHERE evaluation_type = 'HOLISTIC_FLOW'
);
```

## 📥 입력 형식 (Node 4 함수 입력)

### `EvalTurnState` (TypedDict)

```python
{
    "session_id": str,  # 예: "session_1"
    "turn": int,  # 턴 번호 (예: 1, 2, 3, ...)
    "human_message": str,  # 사용자 프롬프트
    "ai_message": str,  # AI 응답
    "problem_context": Optional[Dict[str, Any]],  # 문제 정보
    "is_guardrail_failed": bool,  # 가드레일 실패 여부
    "guardrail_message": Optional[str],  # 가드레일 메시지
    "intent_types": Optional[List[str]],  # 의도 타입 목록
    "intent_confidence": float,  # 의도 신뢰도 (0.0-1.0)
    # ... 기타 필드
}
```

### 예시

```python
state = {
    "session_id": "session_1",
    "turn": 1,
    "human_message": "외판원 순회 문제를 풀기 위해 비트마스킹 DP 코드를 작성해주세요.",
    "ai_message": "네, 비트마스킹 DP를 사용한 외판원 순회 코드를 작성해드리겠습니다.",
    "problem_context": {
        "basic_info": {
            "title": "외판원 순회 (TSP)",
            "problem_id": "2098",
        },
        "ai_guide": {
            "key_algorithms": ["DP", "Bitmasking"],
        },
    },
    "is_guardrail_failed": False,
    "guardrail_message": None,
    "intent_types": ["generation"],
    "intent_confidence": 0.95,
}
```

## 📤 출력 형식 (Node 4 함수 반환값)

### 평가 함수 반환 형식

각 평가 함수(`eval_generation`, `eval_optimization` 등)는 다음 형식을 반환합니다:

```python
{
    "generation_eval": {  # 또는 "optimization_eval", "debugging_eval" 등
        "intent": str,  # 의도 (예: "generation", "optimization")
        "score": float,  # 전체 점수 (0-100)
        "average": float,  # 평균 점수 (score와 동일)
        "rubrics": [
            {
                "criterion": str,  # 평가 기준 (예: "명확성 (Clarity)")
                "score": float,  # 해당 기준 점수 (0-100)
                "reasoning": str,  # 평가 근거 (필수)
            },
            # ... 5개 루브릭 (명확성, 문제 적절성, 예시, 규칙, 문맥)
        ],
        "final_reasoning": str,  # 전체 평가 요약 (필수)
        "eval_tokens": {  # 토큰 사용량 (선택)
            "prompt_tokens": int,
            "completion_tokens": int,
            "total_tokens": int,
        },
    }
}
```

### 예시

```python
{
    "generation_eval": {
        "intent": "generation",
        "score": 85.5,
        "average": 85.5,
        "rubrics": [
            {
                "criterion": "명확성 (Clarity)",
                "score": 90.0,
                "reasoning": "사용자가 구체적으로 '비트마스킹 DP 코드'를 요청하여 명확합니다."
            },
            {
                "criterion": "문제 적절성 (Problem Relevance)",
                "score": 95.0,
                "reasoning": "외판원 순회 문제에 비트마스킹 DP가 적합한 알고리즘입니다."
            },
            {
                "criterion": "예시 (Examples)",
                "score": 70.0,
                "reasoning": "입출력 예시는 제공하지 않았지만, 문제 맥락이 명확합니다."
            },
            {
                "criterion": "규칙 (Rules)",
                "score": 80.0,
                "reasoning": "제약 조건은 명시하지 않았지만, 기본적인 요구사항은 포함되어 있습니다."
            },
            {
                "criterion": "문맥 (Context)",
                "score": 85.0,
                "reasoning": "이전 대화를 참조하지 않았지만, 문제 맥락을 잘 활용했습니다."
            }
        ],
        "final_reasoning": "사용자 프롬프트는 코드 생성 의도를 명확히 전달하고 있으며, 문제 특성에 적합한 알고리즘을 요청했습니다. 다만, 입출력 예시나 구체적인 제약 조건을 제공하지 않은 점이 아쉽습니다.",
        "eval_tokens": {
            "prompt_tokens": 1200,
            "completion_tokens": 450,
            "total_tokens": 1650,
        }
    }
}
```

## 💾 저장 형식 (prompt_evaluations.details)

### `details` JSONB 필드 구조

`evaluation_storage_service.py`의 `save_turn_evaluation` 함수가 다음 형식으로 저장합니다:

```python
{
    "score": float,  # 점수 (prompt_evaluation_details.score)
    "analysis": str,  # 분석 내용 (comprehensive_reasoning 또는 final_reasoning)
    "intent": str,  # 의도 (prompt_evaluation_details.intent)
    "intent_types": List[str],  # 의도 타입 목록 (turn_log.intent_types)
    "rubrics": List[Dict],  # 루브릭 목록 (prompt_evaluation_details.rubrics)
    "evaluations": Dict[str, Any],  # 상세 평가 정보 (turn_log.evaluations)
    "detailed_feedback": List[Dict],  # 상세 피드백 (turn_log.detailed_feedback)
    "turn_score": float,  # 턴 점수 (turn_log.turn_score)
    "is_guardrail_failed": bool,  # 가드레일 실패 여부
    "guardrail_message": Optional[str],  # 가드레일 메시지
}
```

### 예시

```json
{
    "score": 85.5,
    "analysis": "사용자 프롬프트는 코드 생성 의도를 명확히 전달하고 있으며, 문제 특성에 적합한 알고리즘을 요청했습니다. 다만, 입출력 예시나 구체적인 제약 조건을 제공하지 않은 점이 아쉽습니다.",
    "intent": "generation",
    "intent_types": ["generation"],
    "rubrics": [
        {
            "criterion": "명확성 (Clarity)",
            "score": 90.0,
            "reasoning": "사용자가 구체적으로 '비트마스킹 DP 코드'를 요청하여 명확합니다."
        },
        {
            "criterion": "문제 적절성 (Problem Relevance)",
            "score": 95.0,
            "reasoning": "외판원 순회 문제에 비트마스킹 DP가 적합한 알고리즘입니다."
        },
        {
            "criterion": "예시 (Examples)",
            "score": 70.0,
            "reasoning": "입출력 예시는 제공하지 않았지만, 문제 맥락이 명확합니다."
        },
        {
            "criterion": "규칙 (Rules)",
            "score": 80.0,
            "reasoning": "제약 조건은 명시하지 않았지만, 기본적인 요구사항은 포함되어 있습니다."
        },
        {
            "criterion": "문맥 (Context)",
            "score": 85.0,
            "reasoning": "이전 대화를 참조하지 않았지만, 문제 맥락을 잘 활용했습니다."
        }
    ],
    "evaluations": {
        "generation_eval": {
            "intent": "generation",
            "score": 85.5,
            "rubrics": [...],
            "final_reasoning": "..."
        }
    },
    "detailed_feedback": [
        {
            "intent": "generation",
            "rubrics": [...],
            "final_reasoning": "..."
        }
    ],
    "turn_score": 85.5,
    "is_guardrail_failed": false,
    "guardrail_message": null
}
```

## 🔄 데이터 흐름

```
1. Node 4 함수 호출
   ↓
   EvalTurnState (입력)
   ↓
2. 평가 함수 실행
   ↓
   eval_generation(state) → {"generation_eval": {...}}
   ↓
3. 결과 집계 (aggregate_turn_log)
   ↓
   turn_log = {
       "prompt_evaluation_details": {...},
       "evaluations": {...},
       "detailed_feedback": [...],
       ...
   }
   ↓
4. PostgreSQL 저장 (evaluation_storage_service)
   ↓
   prompt_evaluations.details (JSONB)
```

## ✅ 필수 필드 체크리스트

### 평가 함수 반환값 필수 필드

- [x] `intent`: 의도 타입 (문자열)
- [x] `score`: 전체 점수 (0-100)
- [x] `rubrics`: 루브릭 목록 (5개)
  - [x] 각 rubric에 `criterion` 필수
  - [x] 각 rubric에 `score` 필수 (0-100)
  - [x] 각 rubric에 `reasoning` 필수 (평가 근거)
- [x] `final_reasoning`: 전체 평가 요약 (필수)

### 저장 형식 필수 필드

- [x] `score`: 점수
- [x] `analysis`: 분석 내용 (final_reasoning)
- [x] `intent`: 의도
- [x] `intent_types`: 의도 타입 목록
- [x] `rubrics`: 루브릭 목록
- [x] `evaluations`: 상세 평가 정보
- [x] `detailed_feedback`: 상세 피드백
- [x] `turn_score`: 턴 점수
- [x] `is_guardrail_failed`: 가드레일 실패 여부

## 📝 주의사항

1. **`reasoning` 필드 필수**: 각 rubric의 `reasoning` 필드는 반드시 포함해야 합니다.
2. **`final_reasoning` 필드 필수**: 전체 평가 요약은 반드시 포함해야 합니다.
3. **점수 범위**: 모든 점수는 0-100 사이의 값이어야 합니다.
4. **루브릭 개수**: 항상 5개의 루브릭이 포함되어야 합니다 (명확성, 문제 적절성, 예시, 규칙, 문맥).
5. **JSON 파싱**: LLM 응답을 JSON으로 파싱할 때 필드명이 정확해야 합니다 (`reason`이 아닌 `reasoning`).

## 🧪 테스트 예시

### JSON 예시 파일 사용

테스트용 메시지 예시는 `tests/test_messages_examples.json` 파일에 포함되어 있습니다:

```json
{
  "test_cases": [
    {
      "name": "Generation - 기본 코드 생성 요청",
      "human_message": "외판원 순회 문제를 풀기 위해 비트마스킹 DP 코드를 작성해주세요.",
      "ai_message": "네, 비트마스킹 DP를 사용한 외판원 순회 코드를 작성해드리겠습니다.",
      "expected_intent": "generation"
    },
    ...
  ],
  "problem_context_example": {
    "basic_info": {
      "title": "외판원 순회 (TSP)",
      "problem_id": "2098"
    },
    "ai_guide": {
      "key_algorithms": ["DP", "Bitmasking"]
    }
  }
}
```

### Python 코드 예시

```python
# tests/test_node4_unit.py 참고
import json

# JSON 파일에서 예시 로드
with open("tests/test_messages_examples.json", "r", encoding="utf-8") as f:
    examples = json.load(f)

# 첫 번째 예시 사용
test_case = examples["test_cases"][0]
problem_context = examples["problem_context_example"]

state = {
    "session_id": "test_session",
    "turn": 1,
    "human_message": test_case["human_message"],
    "ai_message": test_case["ai_message"],
    "problem_context": problem_context,
    "is_guardrail_failed": False,
    "guardrail_message": None,
    "intent_types": None,
    "intent_confidence": 0.0,
    # ... 기타 필드
}

result = await eval_generation(state)
assert "generation_eval" in result
assert "score" in result["generation_eval"]
assert "rubrics" in result["generation_eval"]
assert len(result["generation_eval"]["rubrics"]) == 5
assert "reasoning" in result["generation_eval"]["rubrics"][0]
assert "final_reasoning" in result["generation_eval"]
```

### 직접 JSON 형식으로 작성

```json
{
  "session_id": "test_session",
  "turn": 1,
  "human_message": "외판원 순회 문제를 풀기 위해 비트마스킹 DP 코드를 작성해주세요.",
  "ai_message": "네, 비트마스킹 DP를 사용한 외판원 순회 코드를 작성해드리겠습니다.",
  "problem_context": {
    "basic_info": {
      "title": "외판원 순회 (TSP)",
      "problem_id": "2098"
    },
    "ai_guide": {
      "key_algorithms": ["DP", "Bitmasking"]
    }
  },
  "is_guardrail_failed": false,
  "guardrail_message": null,
  "intent_types": null,
  "intent_confidence": 0.0
}
```


