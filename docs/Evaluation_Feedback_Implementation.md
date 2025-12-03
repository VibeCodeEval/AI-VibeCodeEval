# 평가 피드백 강화 구현 가이드

## 📋 개요

점수 근거와 LLM 의견을 사용자에게 명확히 제공하기 위한 평가 피드백 강화 기능을 구현했습니다.

---

## ✅ 구현 완료 사항

### 1. Turn Evaluation 피드백 강화

#### 수정 파일
- `app/domain/langgraph/nodes/turn_evaluator/aggregation.py`
- `app/application/services/eval_service.py`

#### 추가된 정보
- **detailed_feedback**: 각 Intent별 상세 피드백
  - `rubrics`: 평가 루브릭 목록 (명확성, 예시, 규칙, 문맥, 문제 적절성)
  - `final_reasoning`: 각 Intent에 대한 LLM의 평가 근거
- **comprehensive_reasoning**: 전체 턴에 대한 종합 평가 근거
  - 모든 Intent 평가의 `final_reasoning`을 종합

#### Turn Log 구조
```json
{
  "turn_number": 1,
  "prompt_evaluation_details": {
    "intent": "hint_or_query",
    "score": 85.5,
    "rubrics": [
      {
        "criterion": "힌트/질의 (Hint/Query)",
        "score": 85.5,
        "reason": "사고 과정을 공유하고 막힌 부분을 구체적으로 질문했습니다."
      }
    ],
    "final_reasoning": "[힌트/질의 (Hint/Query)]: 사고 과정을 공유하고...",
    "detailed_evaluations": [
      {
        "criterion": "힌트/질의 (Hint/Query)",
        "score": 85.5,
        "final_reasoning": "상세한 평가 근거...",
        "rubrics": [
          {
            "criterion": "명확성",
            "score": 90,
            "reason": "구체적 키워드를 사용했습니다."
          },
          {
            "criterion": "문제 적절성",
            "score": 85,
            "reason": "문제 특성에 맞는 질문을 했습니다."
          }
        ]
      }
    ],
    "detailed_feedback": [
      {
        "intent": "hint_query_eval",
        "rubrics": [...],
        "final_reasoning": "..."
      }
    ]
  }
}
```

---

### 2. Holistic Flow Evaluation 피드백 강화

#### 수정 파일
- `app/domain/langgraph/nodes/holistic_evaluator/flow.py`
- `app/domain/langgraph/states.py`
- `app/domain/langgraph/nodes/holistic_evaluator/scores.py`
- `app/presentation/schemas/chat.py`
- `app/presentation/api/routes/chat.py`

#### 추가된 정보
- **holistic_flow_analysis**: 체이닝 전략에 대한 상세 분석
  - 문제 분해 전략 평가
  - 피드백 수용성 평가
  - 주도성 평가
  - 전략적 탐색 평가
  - 종합 의견 및 개선 제안

#### State 추가
```python
holistic_flow_analysis: Optional[str]  # 체이닝 전략에 대한 상세 분석
```

#### 최종 점수 응답 구조
```json
{
  "final_scores": {
    "prompt_score": 85.5,
    "performance_score": 78.0,
    "correctness_score": 92.0,
    "total_score": 86.38,
    "grade": "B"
  },
  "feedback": {
    "holistic_flow_analysis": "문제 분해 전략: ...\n피드백 수용성: ...\n주도성: ...\n전략적 탐색: ..."
  }
}
```

---

## 🔧 주요 변경사항

### 1. Turn Evaluation (4번 노드)

#### `aggregation.py`
- `detailed_feedback` 필드 추가
- `comprehensive_reasoning` 필드 추가
- 각 Intent별 `rubrics`와 `final_reasoning` 추출 및 구조화

#### `eval_service.py`
- `detailed_feedback`를 turn_log에 포함
- `comprehensive_reasoning`을 `final_reasoning`으로 사용

### 2. Holistic Flow Evaluation (6a 노드)

#### `flow.py`
- `process_holistic_output_with_response` 수정
  - `holistic_flow_analysis` 필드 추가
  - `strategy_coherence`, `problem_solving_approach`, `iteration_quality` 필드 추가
- 시스템 프롬프트에 상세 분석 요청 추가

#### `scores.py`
- `aggregate_final_scores`에서 `holistic_flow_analysis` 포함
- `feedback` 필드 추가

### 3. API 응답

#### `SubmitResponse` 스키마
- `EvaluationFeedback` 모델 추가
- `feedback` 필드 추가

#### `chat.py` 라우터
- `submit_code`에서 `feedback` 정보 포함

---

## 📊 데이터 흐름

### Turn Evaluation 피드백
```
Turn Evaluator (4번 노드)
    ↓
각 Intent 평가 결과
    ├─ rubrics: 평가 루브릭 목록
    └─ final_reasoning: 평가 근거
    ↓
aggregation.py
    ├─ detailed_feedback: 각 Intent별 상세 피드백
    └─ comprehensive_reasoning: 전체 평가 근거
    ↓
eval_service.py
    └─ turn_log에 포함
    ↓
turn-logs API
    └─ 사용자에게 전달
```

### Holistic Flow Evaluation 피드백
```
Holistic Evaluator (6a 노드)
    ↓
HolisticFlowEvaluation
    ├─ overall_flow_score: 종합 점수
    ├─ strategy_coherence: 전략 일관성
    ├─ problem_solving_approach: 문제 해결 접근법
    ├─ iteration_quality: 반복 개선 품질
    └─ analysis: 상세 분석 (체이닝 전략)
    ↓
State에 저장
    └─ holistic_flow_analysis
    ↓
aggregate_final_scores (7번 노드)
    └─ feedback 필드에 포함
    ↓
SubmitResponse
    └─ 사용자에게 전달
```

---

## 🎯 사용 예시

### Turn Logs API 응답
```json
{
  "session_id": "session-123",
  "turn_logs": {
    "1": {
      "turn_number": 1,
      "prompt_evaluation_details": {
        "intent": "hint_or_query",
        "score": 85.5,
        "final_reasoning": "[힌트/질의 (Hint/Query)]: 사고 과정을 공유하고...",
        "detailed_feedback": [
          {
            "intent": "hint_query_eval",
            "rubrics": [
              {
                "criterion": "명확성",
                "score": 90,
                "reason": "구체적 키워드를 사용했습니다."
              }
            ],
            "final_reasoning": "상세한 평가 근거..."
          }
        ]
      }
    }
  }
}
```

### Submit Response (코드 제출 시)
```json
{
  "session_id": "session-123",
  "final_scores": {
    "prompt_score": 85.5,
    "performance_score": 78.0,
    "correctness_score": 92.0,
    "total_score": 86.38,
    "grade": "B"
  },
  "feedback": {
    "holistic_flow_analysis": "문제 분해 전략: 전체 코드가 아닌 부분 코드로 점진적으로 구성되었습니다...\n피드백 수용성: 이전 턴의 힌트가 다음 턴에 잘 반영되었습니다...\n주도성: 능동적으로 개선 방향을 제시했습니다...\n전략적 탐색: 의도가 HINT_OR_QUERY에서 GENERATION으로 전환되었습니다..."
  }
}
```

---

## 📝 참고사항

### 1. Turn Evaluation 피드백
- **rubrics**: Claude Prompt Engineering 5가지 기준별 평가
- **final_reasoning**: 각 Intent에 대한 LLM의 종합 평가 근거
- **comprehensive_reasoning**: 모든 Intent 평가를 종합한 전체 평가 근거

### 2. Holistic Flow Evaluation 피드백
- **analysis**: 체이닝 전략에 대한 상세 분석
  - 문제 분해 전략 평가
  - 피드백 수용성 평가
  - 주도성 평가
  - 전략적 탐색 평가
  - 종합 의견 및 개선 제안

### 3. API 엔드포인트
- **GET /api/chat/turn-logs**: 턴별 상세 피드백 조회
- **POST /api/chat/submit**: 코드 제출 시 Holistic Flow 분석 포함

---

## 🔗 관련 파일

- `app/domain/langgraph/nodes/turn_evaluator/aggregation.py`: 턴 로그 집계 및 피드백 구조화
- `app/domain/langgraph/nodes/holistic_evaluator/flow.py`: Holistic Flow 평가 및 분석
- `app/application/services/eval_service.py`: 피드백 정보 포함 및 저장
- `app/presentation/schemas/chat.py`: API 스키마 (EvaluationFeedback 추가)
- `app/presentation/api/routes/chat.py`: API 응답에 피드백 포함


