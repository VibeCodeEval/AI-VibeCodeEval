# G-Eval 및 신뢰도 필드 구현 가이드

## 📋 개요

G-Eval과 프롬프트 평가 신뢰도 필드의 적용 가능성과 구현 방안을 정리합니다.

---

## 🎯 G-Eval (LLM-as-a-Judge)

### 개념

**G-Eval**은 OpenAI에서 제안한 LLM 기반 평가 프레임워크입니다.

#### 핵심 특징
- **LLM-as-a-Judge**: LLM을 평가자로 사용
- **Chain-of-Thought (CoT)**: 단계별 추론 과정을 통해 평가
- **체크리스트 방식**: 각 평가 항목에 대한 점수를 합산하여 전체 점수 산출

#### 평가 프로세스
```
1. 평가 기준 생성 (LLM)
2. 체크리스트 생성 (각 기준별)
3. 단계별 평가 (CoT)
4. 점수 합산
5. 최종 점수 산출
```

### Gemini에서의 적용 가능성

**✅ 가능합니다**

G-Eval은 모델에 종속되지 않는 프레임워크이므로 Gemini에서도 사용 가능합니다.

#### 구현 방식
```python
# G-Eval 스타일 평가 프롬프트
system_prompt = """당신은 프롬프트 품질 평가 전문가입니다.

평가 프로세스:
1. 평가 기준 확인
2. 각 기준별 체크리스트 작성
3. 단계별 점수 부여 (0-100)
4. 최종 점수 계산

평가 기준:
- 명확성 (Clarity)
- 문제 적절성 (Problem Relevance)
- 예시 (Examples)
- 규칙 (Rules)
- 문맥 (Context)

각 기준에 대해 다음 형식으로 평가하세요:
1. [기준명] 체크리스트:
   - 항목 1: ✓/✗ (점수: X/100)
   - 항목 2: ✓/✗ (점수: X/100)
2. [기준명] 점수: X/100
3. [기준명] 근거: ...

최종 점수: (각 기준 점수의 평균)
"""
```

---

## 📊 신뢰도 필드 (Confidence Score)

### 개념

**신뢰도 필드**는 평가 결과의 일관성과 신뢰성을 나타내는 지표입니다.

#### 신뢰도 계산 방법

1. **Self-Consistency (자체 일관성)**
   - 동일한 프롬프트를 N번 평가
   - 점수 분산 계산
   - 분산이 낮을수록 신뢰도 높음

2. **평가 기준 일치도**
   - 각 루브릭 점수 간 일관성
   - 메트릭과 LLM 평가 간 일치도

3. **신뢰도 점수 공식**
   ```python
   confidence = 1 - (score_variance / max_variance)
   # 또는
   confidence = 1 - (score_range / 100)
   ```

### 현재 코드베이스 상태

**IntentClassification 모델**에는 이미 `confidence` 필드가 있습니다:
```python
class IntentClassification(BaseModel):
    intent_types: list[CodeIntentType]
    confidence: float = Field(..., ge=0.0, le=1.0)  # ✅ 있음
    reasoning: str
```

**TurnEvaluation 모델**에는 `confidence` 필드가 없습니다:
```python
class TurnEvaluation(BaseModel):
    intent: str
    score: float
    rubrics: list[Rubric]
    final_reasoning: str
    # confidence 필드 없음 ❌
```

---

## 🔧 구현 방안

### 1. G-Eval 스타일 평가 프롬프트

#### 현재 평가 프롬프트
```
평가 기준 (Claude Prompt Engineering):
1. 명확성 (Clarity): ...
2. 문제 적절성 (Problem Relevance): ...
...
```

#### G-Eval 스타일 개선
```
평가 프로세스 (G-Eval 방식):

Step 1: 평가 기준 확인
- 명확성 (Clarity)
- 문제 적절성 (Problem Relevance)
- 예시 (Examples)
- 규칙 (Rules)
- 문맥 (Context)

Step 2: 각 기준별 체크리스트 작성
[명확성 체크리스트]
- 요청이 모호하지 않은가? ✓/✗
- 구체적인 값이 포함되어 있는가? ✓/✗
- 적절한 길이인가? (20-200 단어) ✓/✗

Step 3: 단계별 점수 부여
- 각 체크리스트 항목에 대해 0-100점 부여
- 기준별 점수 = 체크리스트 항목 점수의 평균

Step 4: 최종 점수 계산
- 전체 점수 = 각 기준 점수의 평균
```

### 2. 신뢰도 필드 추가

#### TurnEvaluation 모델 확장
```python
class TurnEvaluation(BaseModel):
    intent: str
    score: float
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="평가 신뢰도 (0-1, 높을수록 신뢰도 높음)"
    )
    rubrics: list[Rubric]
    final_reasoning: str
```

#### 신뢰도 계산 방법

**방법 1: Self-Consistency (다중 평가)**
```python
async def evaluate_with_confidence(state: EvalTurnState, n_samples: int = 3):
    """신뢰도를 포함한 평가"""
    results = []
    for _ in range(n_samples):
        result = await _evaluate_turn(state, eval_type, criteria)
        results.append(result)
    
    # 점수 분산 계산
    scores = [r["score"] for r in results]
    score_variance = statistics.variance(scores)
    score_range = max(scores) - min(scores)
    
    # 신뢰도 계산
    confidence = 1 - (score_range / 100)  # 범위가 작을수록 신뢰도 높음
    
    # 중앙값 반환
    median_score = statistics.median(scores)
    
    return {
        "score": median_score,
        "confidence": confidence,
        "score_range": (min(scores), max(scores)),
        "all_reasonings": [r["final_reasoning"] for r in results]
    }
```

**방법 2: 메트릭-LLM 평가 일치도**
```python
def calculate_confidence_from_metrics(llm_score: float, metric_score: float) -> float:
    """메트릭과 LLM 평가 간 일치도 기반 신뢰도"""
    score_diff = abs(llm_score - metric_score)
    # 차이가 작을수록 신뢰도 높음
    confidence = 1 - (score_diff / 100)
    return max(0.0, min(1.0, confidence))
```

**방법 3: 루브릭 일관성**
```python
def calculate_confidence_from_rubrics(rubrics: List[Rubric]) -> float:
    """루브릭 점수 간 일관성 기반 신뢰도"""
    scores = [r.score for r in rubrics]
    if len(scores) == 0:
        return 0.0
    
    score_variance = statistics.variance(scores)
    # 분산이 작을수록 신뢰도 높음
    confidence = 1 - (score_variance / 10000)  # 100^2 = 10000
    return max(0.0, min(1.0, confidence))
```

---

## 🎯 추천 구현 방안

### 옵션 1: G-Eval 스타일 프롬프트 (권장)

**장점:**
- ✅ 체계적인 평가 프로세스
- ✅ 단계별 추론으로 일관성 향상
- ✅ 체크리스트 방식으로 객관성 향상

**구현:**
- 평가 프롬프트를 G-Eval 스타일로 개선
- 체크리스트 형식으로 평가 요청

### 옵션 2: 신뢰도 필드 추가 (권장)

**장점:**
- ✅ 평가 결과의 신뢰성 측정 가능
- ✅ 신뢰도가 낮은 경우 재평가 가능
- ✅ 평가 품질 모니터링 가능

**구현:**
1. `TurnEvaluation` 모델에 `confidence` 필드 추가
2. 루브릭 일관성 기반 신뢰도 계산 (간단)
3. 또는 Self-Consistency 기반 신뢰도 계산 (정확하지만 비용 증가)

### 옵션 3: 하이브리드 접근 (최적)

**G-Eval 스타일 프롬프트 + 신뢰도 필드**

1. 평가 프롬프트를 G-Eval 스타일로 개선
2. 루브릭 일관성 기반 신뢰도 계산
3. 신뢰도가 낮으면(예: < 0.7) Self-Consistency 재평가

---

## 📝 구현 예시

### G-Eval 스타일 평가 프롬프트

```python
system_prompt = f"""당신은 '프롬프트 엔지니어링' 평가 전문가입니다.

평가 프로세스 (G-Eval 방식):

Step 1: 평가 기준 확인
1. 명확성 (Clarity)
2. 문제 적절성 (Problem Relevance)
3. 예시 (Examples)
4. 규칙 (Rules)
5. 문맥 (Context)

Step 2: 각 기준별 체크리스트 작성 및 점수 부여

[명확성 체크리스트]
- 요청이 모호하지 않은가? (0-100점)
- 구체적인 값이 포함되어 있는가? (0-100점)
- 적절한 길이인가? (20-200 단어) (0-100점)
→ 명확성 점수: (체크리스트 점수 평균)

[문제 적절성 체크리스트]
- 문제 특성에 적합한가? (0-100점)
- 필수 개념을 언급했는가? (0-100점)
- 기술 용어를 사용했는가? (0-100점)
→ 문제 적절성 점수: (체크리스트 점수 평균)

[예시 체크리스트]
- 입출력 예시를 제공했는가? (0-100점)
- 예시 개수가 충분한가? (2개 이상: 100점, 1개: 70점, 0개: 0점)
→ 예시 점수: (체크리스트 점수 평균)

[규칙 체크리스트]
- 제약 조건을 명시했는가? (0-100점)
- XML 태그를 사용했는가? (0-100점)
- 구조화 형식을 사용했는가? (0-100점)
→ 규칙 점수: (체크리스트 점수 평균)

[문맥 체크리스트]
- 이전 대화를 참조했는가? (0-100점)
- 참조가 구체적인가? (0-100점)
→ 문맥 점수: (체크리스트 점수 평균)

Step 3: 최종 점수 계산
- 전체 점수 = (명확성 + 문제 적절성 + 예시 + 규칙 + 문맥) / 5

Step 4: 신뢰도 평가
- 각 기준 점수 간 일관성 확인
- 일관성이 높으면 신뢰도 높음

위 프로세스를 따라 평가하세요."""
```

### 신뢰도 필드 추가

```python
class TurnEvaluation(BaseModel):
    intent: str
    score: float
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="평가 신뢰도 (0-1, 루브릭 일관성 기반)"
    )
    rubrics: list[Rubric]
    final_reasoning: str

# 신뢰도 계산
def calculate_confidence_from_rubrics(rubrics: List[Rubric]) -> float:
    """루브릭 점수 간 일관성 기반 신뢰도"""
    if len(rubrics) == 0:
        return 0.0
    
    scores = [r.score for r in rubrics]
    score_variance = statistics.variance(scores)
    
    # 분산이 작을수록 신뢰도 높음
    # 최대 분산: 100^2 = 10000 (모든 점수가 0 또는 100인 경우)
    confidence = 1 - (score_variance / 10000)
    return max(0.0, min(1.0, confidence))
```

---

## ✅ 결론

### G-Eval 적용 가능성
- ✅ **가능합니다**: Gemini에서도 G-Eval 스타일 평가 프롬프트 사용 가능
- ✅ **권장**: 체계적인 평가 프로세스로 일관성 향상

### 신뢰도 필드 추가 가능성
- ✅ **가능합니다**: `TurnEvaluation` 모델에 `confidence` 필드 추가 가능
- ✅ **권장**: 루브릭 일관성 기반 신뢰도 계산 (간단하고 효과적)

### 최종 추천
1. **G-Eval 스타일 프롬프트** 적용 (평가 일관성 향상)
2. **신뢰도 필드** 추가 (평가 신뢰성 측정)
3. **하이브리드 접근**: G-Eval + 신뢰도 필드

---

## 🔗 참고 자료

- [G-Eval Paper](https://arxiv.org/abs/2303.16634)
- [LLM-as-a-Judge](https://arxiv.org/abs/2306.05685)
- [Self-Consistency](https://arxiv.org/abs/2203.11171)

