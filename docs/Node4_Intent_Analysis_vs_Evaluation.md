# 4번 노드: 의도 분석 vs 평가의 차이

## 📋 개요

4번 노드에서 "의도 분석"과 "평가"는 서로 다른 역할을 수행합니다. 메트릭 사용 여부와 평가 시나리오를 명확히 정리합니다.

---

## 🔍 핵심 차이점

### 1. 의도 분석 (Intent Analysis) - `intent_analysis()`

**역할**: 의도 분류 (Classification)

**위치**: `app/domain/langgraph/nodes/turn_evaluator/analysis.py`

**기능**:
- 사용자 프롬프트를 8가지 의도 중 하나로 **분류**
- 평가가 아니라 **분류(Classification)** 작업

**프롬프트 구조**:
```
Role: 코딩 대화의 의도를 분류하는 전문가
Task: 8가지 의도 중 가장 적절한 의도를 단일 선택

의도 우선순위:
1. GENERATION (최우선)
2. OPTIMIZATION
3. DEBUGGING
...
```

**메트릭 사용**: ❌ **사용하지 않음**
- `calculate_all_metrics()` 호출 없음
- 문제 정보, 메트릭 정보 포함하지 않음
- 단순히 의도만 분류

**출력**:
```python
{
    "intent_types": ["GENERATION"],  # 분류된 의도
    "intent_confidence": 0.95        # 신뢰도
}
```

---

### 2. 공통 턴 평가 (Common Turn Evaluation) - `_evaluate_turn()`

**역할**: 프롬프트 품질 평가 (Evaluation)

**위치**: `app/domain/langgraph/nodes/turn_evaluator/evaluators.py`

**기능**:
- 사용자 프롬프트의 **품질을 평가**
- 5개 루브릭 기준으로 점수 부여

**프롬프트 구조**:
```
Role: 프롬프트 엔지니어링 전문가
Task: 사용자 프롬프트가 '{eval_type}' 의도를 얼마나 잘 전달하는지 평가

[문제 정보]
- 문제: {title}
- 필수 알고리즘: {algorithms}

[정량적 메트릭]
- 텍스트 길이, 단어 수, 예시 개수 등...

[평가 기준]
1. 명확성 (Clarity)
2. 문제 적절성 (Problem Relevance)
3. 예시 (Examples)
4. 규칙 (Rules)
5. 문맥 (Context)
```

**메트릭 사용**: ✅ **사용함**
- `calculate_all_metrics()` 호출 (46줄)
- 메트릭 정보를 프롬프트에 포함
- 문제 정보도 포함

**출력**:
```python
{
    "intent": "코드 생성 요청 (Generation)",
    "score": 85.0,                    # 평가 점수
    "rubrics": [...],                 # 루브릭별 점수 및 근거
    "final_reasoning": "..."          # 종합 평가 근거
}
```

---

## 📊 평가 시나리오

### 전체 플로우

```
1. Intent Analysis (의도 분석)
   └─> intent_analysis()
       ├─> 메트릭 사용: ❌
       ├─> 평가: ❌ (분류만 수행)
       └─> 출력: {intent_types: ["GENERATION"], intent_confidence: 0.95}

2. Intent Router (의도별 라우팅)
   └─> intent_router()
       └─> 의도에 따라 평가 함수 선택
           └─> ["eval_generation"]

3. 개별 평가 함수 실행
   └─> eval_generation()
       └─> _evaluate_turn() 호출
           ├─> 메트릭 사용: ✅
           ├─> 평가: ✅ (프롬프트 품질 평가)
           └─> 출력: {score: 85, rubrics: [...], final_reasoning: "..."}
```

---

## ✅ 사용자 질문에 대한 답변

### Q1: 메트릭을 기준으로 의도 분석에 대한 평가를 하는건 아닌 것 같은데 맞아?

**답변**: ✅ **맞습니다.**

- **의도 분석(`intent_analysis`)**: 메트릭을 사용하지 않음
  - 단순히 의도를 분류하는 작업
  - 메트릭 계산 없음
  - 문제 정보 포함하지 않음

- **메트릭 사용 위치**: 공통 턴 평가(`_evaluate_turn`)에서만 사용
  - `prepare_evaluation_input_internal()` 함수 내부 (46줄)
  - 프롬프트 품질 평가 시 사용

---

### Q2: 의도 분석에 대한 평가는 공통 턴 평가에 대해서만 진행하나?

**답변**: ✅ **맞습니다. 더 정확히는:**

1. **의도 분석 자체는 평가가 아닙니다**
   - `intent_analysis()`는 평가가 아니라 **분류(Classification)** 작업
   - 의도를 선택하는 것이지, 프롬프트 품질을 평가하는 것이 아님

2. **의도 분석 결과를 바탕으로 평가가 진행됩니다**
   ```
   의도 분석 → 의도별 라우팅 → 개별 평가 함수 → _evaluate_turn()
   ```

3. **공통 턴 평가(`_evaluate_turn`)가 실제 평가를 수행합니다**
   - 메트릭 사용
   - 5개 루브릭 기준으로 점수 부여
   - 프롬프트 품질 평가

---

## 🔄 정확한 관계도

```
┌─────────────────────────────────────┐
│  intent_analysis()                   │
│  - 의도 분류 (Classification)        │
│  - 메트릭 사용: ❌                   │
│  - 평가: ❌                          │
│  - 출력: {intent_types, confidence}  │
└──────────────┬──────────────────────┘
               │ 결과 사용
               ▼
┌─────────────────────────────────────┐
│  intent_router()                    │
│  - 의도별 평가 함수 선택              │
└──────────────┬──────────────────────┘
               │ 라우팅
               ▼
┌─────────────────────────────────────┐
│  eval_generation() / eval_optimization() / ... │
│  - 개별 평가 함수                     │
└──────────────┬──────────────────────┘
               │ 호출
               ▼
┌─────────────────────────────────────┐
│  _evaluate_turn()                   │
│  - 공통 턴 평가 (Evaluation)         │
│  - 메트릭 사용: ✅                   │
│  - 평가: ✅                          │
│  - 출력: {score, rubrics, reasoning} │
└─────────────────────────────────────┘
```

---

## 📝 요약

| 구분 | 의도 분석 | 공통 턴 평가 |
|------|----------|------------|
| **함수** | `intent_analysis()` | `_evaluate_turn()` |
| **역할** | 의도 분류 (Classification) | 프롬프트 품질 평가 (Evaluation) |
| **메트릭 사용** | ❌ 없음 | ✅ 사용 (`calculate_all_metrics`) |
| **문제 정보** | ❌ 포함하지 않음 | ✅ 포함 |
| **평가 기준** | 의도 우선순위 규칙 | 5개 루브릭 (명확성, 문제 적절성, 예시, 규칙, 문맥) |
| **출력** | `{intent_types, confidence}` | `{score, rubrics, final_reasoning}` |
| **평가 대상** | 평가 대상 아님 (전처리) | 사용자 프롬프트의 품질 |

---

## 💡 핵심 포인트

1. **의도 분석은 평가가 아닙니다**
   - 분류(Classification) 작업
   - 평가를 위한 전처리 단계

2. **메트릭은 평가에서만 사용됩니다**
   - `prepare_evaluation_input_internal()`에서 계산
   - `_evaluate_turn()`에서 사용

3. **평가 시나리오**:
   - 의도 분석 → 의도별 라우팅 → 개별 평가 함수 → `_evaluate_turn()` (메트릭 사용)

4. **의도 분석에 대한 평가는 없습니다**
   - 의도 분석 자체를 평가하는 단계는 없음
   - 의도 분석 결과를 바탕으로 프롬프트 품질을 평가함



