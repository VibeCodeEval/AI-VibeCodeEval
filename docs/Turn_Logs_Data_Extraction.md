# Turn Logs 데이터 추출 정보

## 📋 개요

6번 노드 (Holistic Flow Evaluation)에서 Redis `turn_logs`에서 추출하는 정보를 정리합니다.

---

## 🔍 6번 노드에서 추출하는 정보

### 추출 위치

**파일**: `app/domain/langgraph/nodes/holistic_evaluator/flow.py`

**코드 (131-138번 줄):**
```python
structured_logs.append({
    "turn": turn_num,
    "intent": log.get("prompt_evaluation_details", {}).get("intent", "UNKNOWN"),
    "prompt_summary": log.get("user_prompt_summary", ""),
    "llm_reasoning": log.get("llm_answer_reasoning", ""),
    "score": log.get("prompt_evaluation_details", {}).get("score", 0),
    "rubrics": log.get("prompt_evaluation_details", {}).get("rubrics", [])
})
```

---

## 📊 추출되는 필드 상세

### 1. `turn` (턴 번호)
- **소스**: `turn_num` (Redis 키에서 추출)
- **타입**: `int`
- **용도**: 턴 순서 식별

### 2. `intent` (의도)
- **소스**: `log.prompt_evaluation_details.intent`
- **타입**: `str`
- **기본값**: `"UNKNOWN"` (없을 경우)
- **가능한 값**: 
  - `GENERATION`, `OPTIMIZATION`, `DEBUGGING`, `TEST_CASE`
  - `HINT_OR_QUERY`, `FOLLOW_UP`, `RULE_SETTING`, `UNKNOWN`
- **용도**: 각 턴의 의도 분석 (전략적 탐색 평가에 사용)

### 3. `prompt_summary` (사용자 프롬프트 요약)
- **소스**: `log.user_prompt_summary`
- **타입**: `str`
- **기본값**: `""` (없을 경우)
- **내용**: 사용자 메시지의 요약 (처음 200자)
- **용도**: 문제 분해 전략 평가에 사용

### 4. `llm_reasoning` (LLM 답변 추론)
- **소스**: `log.llm_answer_reasoning`
- **타입**: `str`
- **기본값**: `""` (없을 경우)
- **내용**: AI 응답의 추론 과정
- **용도**: 피드백 수용성 평가에 사용

### 5. `score` (턴 점수)
- **소스**: `log.prompt_evaluation_details.score`
- **타입**: `float`
- **기본값**: `0` (없을 경우)
- **범위**: 0-100
- **용도**: 각 턴의 평가 점수 (전체 플로우 평가 참고)

### 6. `rubrics` (평가 루브릭)
- **소스**: `log.prompt_evaluation_details.rubrics`
- **타입**: `list[dict]`
- **기본값**: `[]` (없을 경우)
- **구조**:
  ```python
  [
      {
          "criterion": "규칙 설정 (Rules)",
          "score": 85.0,
          "reason": "평가 근거..."
      },
      {
          "criterion": "코드 생성 (Generation)",
          "score": 90.0,
          "reason": "평가 근거..."
      },
      ...
  ]
  ```
- **용도**: 각 턴의 상세 평가 기준별 점수 (전체 플로우 평가 참고)

---

## 📝 Turn Logs 전체 구조

### Redis에 저장된 turn_log 구조

**저장 위치**: `app/domain/langgraph/nodes/eval_turn_guard.py` (222-234번 줄)

```python
detailed_turn_log = {
    "turn_number": turn,  # 턴 번호
    "user_prompt_summary": human_message[:200] + "...",  # 사용자 메시지 요약
    "prompt_evaluation_details": {
        "intent": intent_type,  # 의도
        "score": turn_score,  # 점수
        "rubrics": rubrics,  # 루브릭
        "final_reasoning": result.get("answer_summary", "재평가 완료")  # 최종 추론
    },
    "llm_answer_summary": result.get("answer_summary", ""),  # LLM 답변 요약
    "llm_answer_reasoning": rubrics[0].get("reason", "") if rubrics else "평가 없음",  # LLM 답변 추론
    "timestamp": datetime.utcnow().isoformat()  # 타임스탬프
}
```

---

## 🎯 6번 노드에서 사용하는 방식

### 1. 구조화된 로그 생성

```python
structured_logs = []
for turn_num in sorted([int(k) for k in all_turn_logs.keys()]):
    log = all_turn_logs[str(turn_num)]
    structured_logs.append({
        "turn": turn_num,
        "intent": log.get("prompt_evaluation_details", {}).get("intent", "UNKNOWN"),
        "prompt_summary": log.get("user_prompt_summary", ""),
        "llm_reasoning": log.get("llm_answer_reasoning", ""),
        "score": log.get("prompt_evaluation_details", {}).get("score", 0),
        "rubrics": log.get("prompt_evaluation_details", {}).get("rubrics", [])
    })
```

### 2. LLM 프롬프트에 포함

```python
user_prompt = f"""턴별 대화 로그:

{json.dumps(structured_logs, ensure_ascii=False, indent=2)}

위 로그를 분석하여 Chaining 전략 점수를 평가하세요."""
```

### 3. 평가 항목

LLM은 다음 항목을 평가합니다:

1. **문제 분해 (Problem Decomposition)**
   - `prompt_summary`를 통해 사용자가 문제를 어떻게 분해했는지 평가

2. **피드백 수용성 (Feedback Integration)**
   - `llm_reasoning`을 통해 이전 턴의 힌트가 다음 턴에 반영되었는지 평가

3. **주도성 및 오류 수정 (Proactiveness)**
   - `intent` 변화를 통해 사용자가 능동적으로 개선했는지 평가

4. **전략적 탐색 (Strategic Exploration)**
   - `intent` 전환을 통해 전략적 탐색이 이루어졌는지 평가
   - 예: `HINT_OR_QUERY` → `OPTIMIZATION` → `DEBUGGING`

5. **고급 프롬프트 기법 활용**
   - `prompt_summary`와 `rubrics`를 통해 고급 기법 사용 여부 평가

---

## 📊 데이터 흐름

```
[4번 노드] 평가 완료
    ↓
[Redis turn_logs 저장]
    {
        "turn_number": 1,
        "user_prompt_summary": "...",
        "prompt_evaluation_details": {
            "intent": "HINT_OR_QUERY",
            "score": 85.0,
            "rubrics": [...]
        },
        "llm_answer_reasoning": "..."
    }
    ↓
[6번 노드] turn_logs 조회
    ↓
[구조화된 로그 생성]
    {
        "turn": 1,
        "intent": "HINT_OR_QUERY",
        "prompt_summary": "...",
        "llm_reasoning": "...",
        "score": 85.0,
        "rubrics": [...]
    }
    ↓
[LLM 프롬프트에 포함]
    ↓
[전체 플로우 평가]
```

---

## ⚠️ 중요 사항

### 1. 역직렬화 불필요

- `turn_logs`는 이미 dict 형태로 저장되어 있음
- `get_json()`으로 JSON을 dict로 파싱만 하면 됨
- LangChain BaseMessage 객체로 변환할 필요 없음

### 2. 필드 누락 처리

- 각 필드에 대해 `.get()` 메서드 사용
- 기본값 제공 (`"UNKNOWN"`, `""`, `0`, `[]`)
- 필드가 없어도 에러 없이 처리

### 3. 턴 순서 정렬

```python
for turn_num in sorted([int(k) for k in all_turn_logs.keys()]):
```

- 턴 번호를 정수로 변환하여 정렬
- 시간 순서대로 평가 진행

---

## 📝 요약

| 필드 | 소스 경로 | 타입 | 기본값 | 용도 |
|------|----------|------|--------|------|
| `turn` | Redis 키 | `int` | - | 턴 식별 |
| `intent` | `prompt_evaluation_details.intent` | `str` | `"UNKNOWN"` | 의도 분석 |
| `prompt_summary` | `user_prompt_summary` | `str` | `""` | 문제 분해 평가 |
| `llm_reasoning` | `llm_answer_reasoning` | `str` | `""` | 피드백 수용성 평가 |
| `score` | `prompt_evaluation_details.score` | `float` | `0` | 턴 점수 참고 |
| `rubrics` | `prompt_evaluation_details.rubrics` | `list[dict]` | `[]` | 상세 평가 참고 |

**역직렬화**: 불필요 (dict 형태로 직접 사용)

