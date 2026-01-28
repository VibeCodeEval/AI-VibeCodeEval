# 🎯 하부 Agent 작업 지시문

> 생성일: 2026-01-19
> 프로젝트: AI-VibeCodeEval
> 작성자: Maestro (Head Agent)

---

## 📋 작업 개요

| Phase | 작업명 | 우선순위 | 의존성 | 데이터 소스 |
|-------|--------|----------|--------|------------|
| **Phase 4** | 프롬프트 YAML 분리 | 🔴 High | 없음 (바로 시작 가능) | 코드 내 하드코딩 프롬프트 |
| **Phase 5-A** | 응답 파인튜닝 (문답 데이터) | 🟡 Medium | Phase 4 완료 후 | `prompt_messages` |
| **Phase 5-B** | 평가 파인튜닝 (TURN_EVAL) | 🟡 Medium | Phase 4 완료 후 | `prompt_evaluations` (turn ≠ NULL) |
| **Phase 5-C** | Chaining 파인튜닝 (HOLISTIC_FLOW) | 🟡 Medium | Phase 4 완료 후 | `prompt_evaluations` (turn = NULL) |

---

# 🔧 Phase 4: 프롬프트 YAML 분리

## 목표
LangGraph 노드에 하드코딩된 프롬프트를 별도 YAML 파일로 분리하여 유지보수성 향상

## 명령 파일
```
.maestro/commands/pending/CMD_001_phase4_features.json
```

## 작업 단계

### Step 1: 프롬프트 로더 유틸리티 생성
```python
# 생성할 파일: app/domain/langgraph/prompts/__init__.py

import yaml
from pathlib import Path
from typing import Dict, Any

PROMPTS_DIR = Path(__file__).parent

def load_prompt(name: str) -> Dict[str, Any]:
    """YAML 프롬프트 파일 로드"""
    file_path = PROMPTS_DIR / f"{name}.yaml"
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def render_prompt(name: str, **variables) -> str:
    """프롬프트 템플릿에 변수 치환"""
    data = load_prompt(name)
    template = data.get('template', '')
    return template.format(**variables)
```

### Step 2: 프롬프트 파일 생성

| 파일명 | 원본 위치 | 라인 |
|--------|----------|------|
| `intent_analyzer.yaml` | `nodes/intent_analyzer.py` | 381-544 |
| `writer_guardrail.yaml` | `nodes/writer.py` | 57-82 |
| `writer_normal.yaml` | `nodes/writer.py` | 85-314 |
| `eval_intent_analysis.yaml` | `nodes/turn_evaluator/analysis.py` | 72-131 |
| `eval_holistic_flow.yaml` | `nodes/holistic_evaluator/flow.py` | - |

### Step 3: YAML 파일 형식
```yaml
# 예시: intent_analyzer.yaml
version: "1.0"
name: intent_analyzer
description: Intent Analysis 시스템 프롬프트

template: |
  # Role Definition
  
  당신은 '바이브코딩'의 **AI 시험 감독관**입니다.
  
  ## 문제 정보
  - 제목: {problem_title}
  - 설명: {problem_description}
  - 알고리즘: {algorithms}
  
  # Guardrail Policy
  ...

variables:
  - problem_title
  - problem_description
  - algorithms
  - input_format
  - output_format
```

### Step 4: 기존 코드 수정
```python
# Before (intent_analyzer.py)
def create_intent_analysis_system_prompt(...):
    return f"""# Role Definition
    당신은 '바이브코딩'의 **AI 시험 감독관**입니다...
    """

# After
from app.domain.langgraph.prompts import render_prompt

def create_intent_analysis_system_prompt(...):
    return render_prompt(
        'intent_analyzer',
        problem_title=problem_title,
        problem_description=problem_description,
        algorithms=algorithms,
        ...
    )
```

## 완료 기준
- [ ] `app/domain/langgraph/prompts/` 폴더 생성
- [ ] `__init__.py` 로더 유틸리티 작성
- [ ] 5개 이상 YAML 프롬프트 파일 생성
- [ ] 기존 노드 코드에서 프롬프트 로더 호출로 교체
- [ ] 서버 정상 실행 확인

---

# 📊 Phase 5-A: 응답 파인튜닝 (문답 데이터)

## 목표
DB에서 사용자-AI 문답 쌍을 추출하여 Writer LLM 응답 품질 개선에 활용

## 명령 파일
```
.maestro/commands/pending/CMD_002_phase5a_response.json
```

## 데이터 소스
```sql
-- prompt_messages 테이블에서 USER + ASSISTANT 쌍 추출
SELECT 
    pm_user.session_id,
    pm_user.turn,
    pm_user.content AS user_prompt,
    pm_ai.content AS ai_response,
    pe.details->>'intent' AS intent,
    pe.details->>'is_guardrail_failed' AS is_guardrail_failed,
    pe.details->>'score' AS eval_score
FROM prompt_messages pm_user
JOIN prompt_messages pm_ai 
    ON pm_user.session_id = pm_ai.session_id 
    AND pm_user.turn = pm_ai.turn
JOIN prompt_evaluations pe 
    ON pm_user.session_id = pe.session_id 
    AND pm_user.turn = pe.turn
WHERE pm_user.role = 'USER' 
    AND pm_ai.role = 'ASSISTANT'
    AND pe.evaluation_type = 'TURN_EVAL'
ORDER BY pm_user.session_id, pm_user.turn;
```

## 출력 형식 (JSONL)
```json
{
  "id": "resp_4_3",
  "user_prompt": "DP에 대해 알고 있어?",
  "ai_response": "네, 동적 계획법(DP)에 대한 지식을...",
  "intent": "HINT_OR_QUERY",
  "guide_strategy": "SYNTAX_GUIDE",
  "is_guardrail_failed": false,
  "eval_score": 44.0,
  "metadata": {
    "session_id": 4,
    "turn": 3,
    "created_at": "2026-01-19T00:22:53"
  }
}
```

## 작업 단계

### Step 1: 추출 스크립트 작성
```
scripts/extract_response_pairs.py
```

### Step 2: 데이터 분류
- **정상 응답**: `is_guardrail_failed = false`
- **가드레일 응답**: `is_guardrail_failed = true`

### Step 3: 출력 파일
```
.maestro/data/finetuning/response_pairs.jsonl      # 전체
.maestro/data/finetuning/response_normal.jsonl     # 정상 응답
.maestro/data/finetuning/response_guardrail.jsonl  # 가드레일 응답
.maestro/data/finetuning/response_examples.json    # Few-shot 예시
```

## 완료 기준
- [ ] 추출 스크립트 작성
- [ ] 최소 50개 이상 문답 데이터 추출
- [ ] 가드레일 응답 별도 분류
- [ ] Few-shot 예시 선정 (전략별 3-5개)

---

# 📈 Phase 5-B: 평가 파인튜닝 (평가 데이터)

## 목표
DB에서 평가 데이터를 추출하여 Evaluator LLM 평가 품질 개선에 활용

## 명령 파일
```
.maestro/commands/pending/CMD_003_phase5b_evaluation.json
```

## 데이터 소스
```sql
-- prompt_evaluations 테이블에서 평가 데이터 추출
SELECT 
    pe.id,
    pe.session_id,
    pe.turn,
    pm.content AS user_prompt,
    pe.details
FROM prompt_evaluations pe
JOIN prompt_messages pm 
    ON pe.session_id = pm.session_id 
    AND pe.turn = pm.turn
WHERE pm.role = 'USER'
    AND pe.evaluation_type = 'TURN_EVAL'
    AND pe.details->>'score' IS NOT NULL
ORDER BY pe.session_id, pe.turn;
```

## details JSONB 구조
```json
{
  "score": 44.0,
  "analysis": "[hint_query_eval]: 사용자 프롬프트는...",
  "intent": "HINT_OR_QUERY",
  "intent_types": ["hint_or_query"],
  "intent_confidence": 1.0,
  "rubrics": [
    {"name": "clarity", "score": 40.0, "reasoning": "..."},
    {"name": "problem_relevance", "score": 80.0, "reasoning": "..."},
    {"name": "examples", "score": 0.0, "reasoning": "..."},
    {"name": "rules", "score": 0.0, "reasoning": "..."},
    {"name": "context", "score": 0.0, "reasoning": "..."}
  ],
  "weights": {
    "HINT_OR_QUERY": {"clarity": 0.5, "problem_relevance": 0.3, ...}
  },
  "turn_score": 44.0,
  "is_guardrail_failed": false,
  "ai_summary": "AI 응답 요약..."
}
```

## 출력 형식 (JSONL)
```json
{
  "id": "eval_4_3",
  "user_prompt": "DP에 대해 알고 있어?",
  "intent": "HINT_OR_QUERY",
  "intent_confidence": 1.0,
  "score": 44.0,
  "rubrics": {
    "clarity": {"score": 40.0, "reasoning": "프롬프트는 'DP'라는 대상을..."},
    "problem_relevance": {"score": 80.0, "reasoning": "DP는 필수 알고리즘..."},
    "examples": {"score": 0.0, "reasoning": "예시 없음"},
    "rules": {"score": 0.0, "reasoning": "규칙 없음"},
    "context": {"score": 0.0, "reasoning": "문맥 참조 없음"}
  },
  "weights": {"clarity": 0.5, "problem_relevance": 0.3, "context": 0.2},
  "analysis": "[hint_query_eval]: 사용자 프롬프트는..."
}
```

## 작업 단계

### Step 1: 추출 스크립트 작성
```
scripts/extract_evaluation_data.py
```

### Step 2: 데이터 정제
- `score`가 NULL인 데이터 제외
- `analysis`가 비어있는 데이터 제외
- 의도별 균등 샘플링

### Step 3: 점수대별 분류
- **고점 (70+)**: 좋은 프롬프트 예시
- **중점 (40-69)**: 보통 프롬프트
- **저점 (0-39)**: 개선 필요 프롬프트

### Step 4: 출력 파일
```
.maestro/data/finetuning/evaluation_data.jsonl     # 전체
.maestro/data/finetuning/evaluation_cleaned.jsonl  # 정제
.maestro/data/finetuning/eval_high_score.jsonl     # 고점
.maestro/data/finetuning/eval_medium_score.jsonl   # 중점
.maestro/data/finetuning/eval_low_score.jsonl      # 저점
.maestro/data/finetuning/evaluation_examples.json  # Few-shot 예시
```

### Step 5: YAML 프롬프트에 예시 삽입 (Phase 4 완료 후)
```yaml
# app/domain/langgraph/prompts/eval_criteria/hint_query.yaml
examples:
  - user_prompt: "DP에 대해 알고 있어?"
    score: 44
    reasoning: "구체성이 낮고 예시가 없음"
  - user_prompt: "비트마스킹 관련 코드 힌트 가능해?"
    score: 75
    reasoning: "명확한 요청, 문제 적절성 높음"
```

## 완료 기준
- [ ] 추출 스크립트 작성
- [ ] 최소 100개 이상 평가 데이터 추출
- [ ] 의도별 최소 10개 이상 분포
- [ ] 점수대별 분류 완료
- [ ] Few-shot 예시 선정 (의도별 3-5개)
- [ ] Phase 4 완료 후 YAML에 예시 삽입

---

# 🔗 Phase 5-C: Chaining 파인튜닝 (HOLISTIC_FLOW)

## 목표
DB에서 **Chaining 전략 평가 데이터**를 추출하여 6a 노드(Holistic Flow Evaluator)의 평가 품질 개선에 활용

## 명령 파일
```
.maestro/commands/pending/CMD_004_phase5c_chaining.json
```

## 핵심 차이점
| 구분 | Phase 5-B (TURN_EVAL) | Phase 5-C (HOLISTIC_FLOW) |
|------|----------------------|---------------------------|
| **평가 대상** | 개별 턴 | 세션 전체 |
| **turn 값** | NOT NULL (1, 2, 3...) | **NULL** |
| **평가 항목** | 루브릭 (clarity, relevance 등) | **Chaining 전략** |
| **저장 위치** | 4번 노드 (eval_turn_guard) | **6a 노드** (holistic_evaluator/flow.py) |

## 데이터 소스
```sql
-- prompt_evaluations 테이블에서 HOLISTIC_FLOW 평가 추출
SELECT 
    pe.id,
    pe.session_id,
    pe.evaluation_type,
    pe.details,
    pe.created_at
FROM prompt_evaluations pe
WHERE pe.evaluation_type::text = 'HOLISTIC_FLOW'
    AND pe.turn IS NULL  -- 세션 전체 평가
    AND pe.details->>'score' IS NOT NULL
ORDER BY pe.session_id;
```

## details JSONB 구조 (HOLISTIC_FLOW)
```json
{
  "score": 72.5,
  "analysis": "사용자는 문제를 체계적으로 분해하고...",
  "problem_decomposition": {
    "score": 80.0,
    "analysis": "복잡한 TSP 문제를 DP와 비트마스킹으로 분해..."
  },
  "feedback_integration": {
    "score": 65.0,
    "analysis": "AI 피드백을 일부 수용했으나..."
  },
  "strategic_exploration": {
    "score": 72.5,
    "analysis": "다양한 접근법을 시도함..."
  },
  "structured_logs": [
    {
      "turn": 1,
      "intent": "HINT_OR_QUERY",
      "user_prompt_summary": "DP 개념 질문",
      "ai_summary": "DP 기본 개념 설명",
      "turn_score": 44.0
    },
    {
      "turn": 2,
      "intent": "CODE_REVIEW",
      "user_prompt_summary": "코드 검토 요청",
      "ai_summary": "코드 개선점 제안",
      "turn_score": 60.0
    }
  ]
}
```

## 출력 형식 (JSONL)
```json
{
  "id": "chaining_session_4",
  "session_id": 4,
  "total_score": 72.5,
  "analysis": "사용자는 문제를 체계적으로 분해하고...",
  "evaluation_criteria": {
    "problem_decomposition": {
      "score": 80.0,
      "analysis": "복잡한 TSP 문제를 DP와 비트마스킹으로 분해..."
    },
    "feedback_integration": {
      "score": 65.0,
      "analysis": "AI 피드백을 일부 수용했으나..."
    },
    "strategic_exploration": {
      "score": 72.5,
      "analysis": "다양한 접근법을 시도함..."
    }
  },
  "turn_summaries": [
    {"turn": 1, "intent": "HINT_OR_QUERY", "user_summary": "DP 개념 질문", "ai_summary": "DP 기본 개념 설명", "score": 44.0},
    {"turn": 2, "intent": "CODE_REVIEW", "user_summary": "코드 검토 요청", "ai_summary": "코드 개선점 제안", "score": 60.0}
  ],
  "turn_count": 2,
  "metadata": {
    "problem_spec_id": 1,
    "created_at": "2026-01-19T00:35:00"
  }
}
```

## 작업 단계

### Step 1: 추출 스크립트 작성
```
scripts/extract_chaining_finetuning_data.py
```

### Step 2: 평가 항목 파싱
- **problem_decomposition**: 문제 분해 능력 (복잡한 문제를 단계별로 분해)
- **feedback_integration**: 피드백 수용성 (AI 조언을 반영하여 개선)
- **strategic_exploration**: 전략적 탐색 (다양한 접근법 시도)

### Step 3: 점수대별 분류
- **고점 (70+)**: 우수한 Chaining 전략
- **중점 (40-69)**: 보통 Chaining 전략
- **저점 (0-39)**: 개선 필요

### Step 4: 출력 파일
```
.maestro/data/finetuning/chaining_data.jsonl         # 전체
.maestro/data/finetuning/chaining_high_score.jsonl   # 고점
.maestro/data/finetuning/chaining_medium_score.jsonl # 중점
.maestro/data/finetuning/chaining_low_score.jsonl    # 저점
.maestro/data/finetuning/chaining_examples.json      # Few-shot 예시
```

## 완료 기준
- [ ] 추출 스크립트 작성
- [ ] HOLISTIC_FLOW 데이터 추출 (최소 20개 이상)
- [ ] 3개 평가 항목 모두 파싱
- [ ] structured_logs에서 턴별 요약 추출
- [ ] 점수대별 분류 완료
- [ ] Few-shot 예시 선정

---

# 🔗 작업 흐름도

```
                         ┌─────────────────┐
                         │    Phase 4      │
                         │ 프롬프트 YAML    │
                         │     분리        │
                         └────────┬────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Phase 5-A     │     │   Phase 5-B     │     │   Phase 5-C     │
│ 응답 파인튜닝    │     │ 턴 평가 파인튜닝 │     │ Chaining 파인튜닝│
│  (문답 데이터)   │     │  (TURN_EVAL)    │     │ (HOLISTIC_FLOW) │
│                 │     │  turn ≠ NULL    │     │  turn = NULL    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                        │                        │
         │                        │                        │
         ▼                        ▼                        ▼
   Writer LLM             Turn Evaluator          Holistic Evaluator
   응답 품질 개선          턴별 평가 정확도         Chaining 전략 평가
```

## 📊 평가 데이터 구분

| 테이블 | evaluation_type | turn | 용도 |
|--------|-----------------|------|------|
| `prompt_messages` | - | NOT NULL | Phase 5-A (USER + ASSISTANT 쌍) |
| `prompt_evaluations` | `TURN_EVAL` | NOT NULL | Phase 5-B (턴별 루브릭 평가) |
| `prompt_evaluations` | `HOLISTIC_FLOW` | **NULL** | Phase 5-C (세션 전체 Chaining 평가) |

---

# 📞 문의

질문이나 이슈 발생 시:
- `.maestro/commands/pending/` 폴더의 상세 명령 파일 참고
- 작업 완료 시 `.maestro/commands/completed/` 폴더로 이동 후 결과 보고

---

> **중요**: Phase 4 완료 후 Phase 5-A, 5-B, 5-C **병렬 진행 가능**
