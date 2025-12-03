# 평가 시스템 개선 전략

## 개요

LLM 사용 능력 평가 도구의 평가 분류 명확성 향상을 위한 개선 전략 문서입니다. 폐쇄망 환경에서 출력 제한된 LLM을 사용하면서도, LLM의 장점을 최대한 활용하는 균형잡힌 접근 방식을 제시합니다.

## 배경

### 현재 상황
- **목적**: LLM 사용 능력 평가 도구 (코딩 테스트 + LLM 도구 통합 평가)
- **환경**: 폐쇄망 환경 → 출력 제한된 LLM 사용
- **목표**: 검색 시간 단축 + 사고 흐름 판단 + 프롬프트 엔지니어링 능력 평가
- **핵심 목표**: **평가 분류의 명확성** (가장 중요)

### 현재 문제점
1. **의도 분류의 모호성**: 복수 선택 가능하지만 기준 불명확
2. **평가 기준의 경직성**: 5가지 고정 기준만 사용
3. **LLM 일관성 문제**: 구조화된 출력이라도 값의 변동성 존재
4. **과도한 구조화**: LLM의 맥락 이해 능력 미활용

---

## 개선 전략

### 1. 하이브리드 의도 분류

#### 목표
- 기본 의도(8가지) 유지 + LLM 보완으로 유연성 확보
- 평가 명확성과 유연성의 균형

#### 구현 방안
```python
class EnhancedIntentClassification(BaseModel):
    """향상된 의도 분류 결과"""
    # 기본 의도 (구조화 필수)
    base_intent: CodeIntentType = Field(
        ...,
        description="기본 의도 카테고리"
    )
    
    # LLM 보완 (유연성)
    intent_variation: Optional[str] = Field(
        None,
        description="LLM이 제안한 의도 변형 또는 복합 의도 설명"
    )
    
    # 우선순위 기반 선택
    intent_priority: int = Field(
        ...,
        ge=1,
        le=8,
        description="의도 우선순위 (1=최우선)"
    )
    
    intent_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="분류 신뢰도"
    )
    
    llm_reasoning: str = Field(
        ...,
        description="LLM의 분류 근거 (맥락 기반)"
    )
```

#### 의도 선택 우선순위 규칙
```
1. GENERATION (코드 생성이 목적이면 최우선)
2. OPTIMIZATION (기존 코드 개선)
3. DEBUGGING (버그 수정)
4. TEST_CASE (테스트 작성)
5. RULE_SETTING (제약조건 명시)
6. SYSTEM_PROMPT (역할 정의)
7. HINT_OR_QUERY (질문/힌트)
8. FOLLOW_UP (후속 질문)

단일 의도만 선택하되, 우선순위가 높은 것을 선택하세요.
```

#### 의도 정의 구체화
```python
INTENT_DEFINITIONS = {
    "GENERATION": {
        "description": "새로운 코드를 생성하는 요청",
        "keywords": ["작성", "만들어", "구현", "코드", "알고리즘"],
        "examples": [
            "비트마스킹으로 TSP 문제를 풀어줘",
            "이 알고리즘을 코드로 작성해줘"
        ],
        "exclusion": ["최적화", "디버깅", "테스트"],
        "priority": 1
    },
    "OPTIMIZATION": {
        "description": "기존 코드를 최적화하거나 성능을 개선하는 요청",
        "keywords": ["최적화", "개선", "빠르게", "효율", "성능"],
        "examples": [
            "이 코드를 더 빠르게 만들어줘",
            "시간 복잡도를 개선해줘"
        ],
        "exclusion": ["새 코드 작성", "버그 수정"],
        "priority": 2
    },
    # ... (나머지 의도들도 동일한 구조)
}
```

---

### 2. 동적 평가 기준 (공통 + 의도별 특화)

#### 목표
- 공통 기준(5가지) 유지 + LLM이 의도별 특화 기준 추가
- 평가 명확성과 유연성의 균형

#### 구현 방안
```python
class EnhancedTurnEvaluation(BaseModel):
    """향상된 턴 평가 결과"""
    
    # 공통 평가 (구조화 필수)
    common_evaluation: CommonEvaluation
    
    # 의도별 특화 평가 (LLM 추가)
    intent_specific_evaluation: Optional[IntentSpecificEvaluation] = None
    
    # 최종 점수
    final_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="최종 점수 (공통 + 의도별 가중 평균)"
    )
    
    # 평가 신뢰도
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="평가 신뢰도 (일관성 기반)"
    )

class CommonEvaluation(BaseModel):
    """공통 평가 기준 (항상 포함)"""
    clarity: RubricScore  # 명확성
    examples: RubricScore  # 예시
    rules: RubricScore  # 규칙
    context: RubricScore  # 문맥
    problem_relevance: RubricScore  # 문제 적절성

class IntentSpecificEvaluation(BaseModel):
    """의도별 특화 평가 (LLM이 추가)"""
    additional_criteria: List[RubricScore] = Field(
        ...,
        description="LLM이 발견한 의도별 특화 평가 기준"
    )
    hidden_patterns: List[str] = Field(
        default_factory=list,
        description="LLM이 발견한 숨겨진 패턴"
    )
    contextual_factors: List[str] = Field(
        default_factory=list,
        description="맥락 기반 평가 요소"
    )
```

#### 프롬프트 엔지니어링 (구체적 역할 명시)

```python
def create_enhanced_evaluation_prompt(eval_type: str, criteria: str, problem_context: Optional[Dict] = None) -> str:
    """
    향상된 평가 프롬프트 생성 (구체적 역할 명시)
    """
    problem_info_section = ""
    if problem_context:
        basic_info = problem_context.get("basic_info", {})
        ai_guide = problem_context.get("ai_guide", {})
        problem_title = basic_info.get("title", "알 수 없음")
        key_algorithms = ai_guide.get("key_algorithms", [])
        algorithms_text = ", ".join(key_algorithms) if key_algorithms else "없음"
        
        problem_info_section = f"""
[문제 정보]
- 문제: {problem_title}
- 필수 알고리즘: {algorithms_text}

"""
    
    return f"""당신은 '프롬프트 엔지니어링 전문가'이자 '실제 코드를 작성하는 개발자'입니다.

**당신의 역할:**
1. 프롬프트 엔지니어링 전문가로서 사용자의 프롬프트 품질을 평가
2. 실제 개발자로서 이 프롬프트로 코드를 작성할 수 있는지 판단
3. 평가 기준을 명확하고 구체적으로 적용하여 일관된 평가 제공

{problem_info_section}**평가 기준 (매우 구체적):**

## 1. 명확성 (Clarity) - 0-100점
- **90-100점**: 구체적 키워드 3개 이상 + 명확한 요청 + 기술적 용어 사용
  예: "비트마스킹을 사용하여 TSP 문제를 O(N^2 * 2^N) 시간 복잡도로 풀어줘"
- **70-89점**: 구체적 키워드 1-2개 + 약간 모호한 표현
  예: "TSP 문제를 풀어줘"
- **50-69점**: 일반적 표현만 사용, 기술적 세부사항 부족
  예: "이 문제를 해결해줘"
- **0-49점**: 매우 모호한 표현, 요청 의도 불명확
  예: "도와줘"

## 2. 예시 (Examples) - 0-100점
- **90-100점**: 입출력 예시 2개 이상 + 엣지 케이스 포함
  예: "입력: N=4, W=[[0,10,15,20],[10,0,35,25],...] / 출력: 80"
- **70-89점**: 예시 1개 제공 + 기본 케이스만
  예: "입력: N=3 / 출력: 30"
- **50-69점**: 예시 없지만 상황 설명
  예: "도시가 3개인 경우"
- **0-49점**: 예시 없음, 추상적 표현만

## 3. 규칙 (Rules) - 0-100점
- **90-100점**: XML 태그 사용 + 제약조건 명시 + 복잡도 요구사항
  예: "<constraints>시간 복잡도 O(N^2 * 2^N) 이하</constraints>"
- **70-89점**: 제약조건 명시 (XML 태그 없음)
  예: "시간 복잡도 O(N^2 * 2^N) 이하로 작성해줘"
- **50-69점**: 간단한 제약조건 언급
  예: "빠르게 작성해줘"
- **0-49점**: 제약조건 없음

## 4. 문맥 (Context) - 0-100점
- **90-100점**: 이전 턴의 구체적 내용 참조 + 대화 흐름 활용
  예: "이전에 말한 비트마스킹 개념을 사용하여..."
- **70-89점**: 이전 턴 언급 (구체적 내용 없음)
  예: "앞서 말한 방법으로..."
- **50-69점**: 맥락 활용 시도 (불명확)
  예: "그거..."
- **0-49점**: 맥락 활용 없음

## 5. 문제 적절성 (Problem Relevance) - 0-100점
- **90-100점**: 문제 특성({algorithms_text if problem_context else "알 수 없음"})에 맞는 알고리즘 언급 + 필수 개념 포함
  예: "비트마스킹 DP로 TSP 문제를 풀어줘"
- **70-89점**: 문제 관련 키워드 언급
  예: "TSP 문제를 풀어줘"
- **50-69점**: 문제와 관련 있지만 구체적 알고리즘 없음
  예: "이 문제를 풀어줘"
- **0-49점**: 문제와 무관한 요청

**의도별 특화 평가:**
{eval_type} 의도에 대해 다음을 추가로 평가하세요:
{criteria}

**평가 지침:**
1. 각 기준을 독립적으로 평가 (다른 기준에 영향받지 않음)
2. 점수는 정확히 부여 (반올림 최소화)
3. 평가 근거를 구체적으로 작성
4. 실제 개발자 관점에서 "이 프롬프트로 코드를 작성할 수 있는가?" 고려

위 기준을 바탕으로 0-100점 사이의 점수를 부여하고, 상세한 루브릭과 추론을 제공하세요."""
```

---

### 3. 사고 과정 평가 추가

#### 목표
- 최종 결과뿐만 아니라 사고 과정도 평가
- 학습 효과 측정 및 개선 방향 제시

#### 구현 방안
```python
class ThinkingProcessEvaluation(BaseModel):
    """사고 과정 평가"""
    problem_understanding: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="문제 이해도"
    )
    strategy_selection: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="전략 선택 능력"
    )
    prompt_refinement: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="프롬프트 개선 능력"
    )
    context_utilization: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="맥락 활용 능력"
    )

class LearningTrajectory(BaseModel):
    """학습 곡선"""
    improvement_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="개선율 (턴별 점수 증가율)"
    )
    consistency: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="일관성 (점수 변동성의 역수)"
    )
    learning_pattern: str = Field(
        ...,
        description="학습 패턴 (점진적 개선, 급격한 변화, 정체 등)"
    )
```

---

### 4. 구체적 피드백 제공

#### 목표
- 점수뿐만 아니라 구체적 개선 방안 제시
- 학습 가이드 및 맞춤형 피드백 제공

#### 구현 방안
```python
class EnhancedFeedback(BaseModel):
    """향상된 피드백"""
    strengths: List[str] = Field(
        ...,
        description="강점 분석"
    )
    weaknesses: List[str] = Field(
        ...,
        description="약점 분석"
    )
    improvement_suggestions: List[str] = Field(
        ...,
        description="구체적 개선 제안"
    )
    next_steps: List[str] = Field(
        ...,
        description="다음 단계 가이드"
    )
    learning_resources: Optional[List[str]] = Field(
        None,
        description="추천 학습 자료"
    )
```

---

## LLM 일관성 문제 해결

### 문제점
- 구조화된 출력이라도 값의 변동성 존재
- 같은 입력에 대해 매번 다른 점수/근거 제공 가능

### 해결 방안

#### 방안 1: 평가 기준 구체화 (권장)
- 프롬프트에 매우 구체적인 평가 기준 명시
- 점수 범위별 구체적 예시 제공
- 평가 지침 명확화

#### 방안 2: 다중 평가 + 평균/중앙값 (선택적)
```python
async def evaluate_with_consistency(state: EvalTurnState, n_samples: int = 3):
    """
    N번 평가하여 일관성 확보 (신뢰도 낮을 때만 사용)
    """
    results = []
    for _ in range(n_samples):
        result = await _evaluate_turn(state, eval_type, criteria)
        results.append(result)
    
    # 점수 일관성 검사
    scores = [r["score"] for r in results]
    score_range = max(scores) - min(scores)
    
    if score_range > 10:  # 차이가 10점 이상이면
        logger.warning(f"평가 일관성 낮음: {scores}, 범위: {score_range}")
        # 재평가 또는 플래그 설정
    
    # 중앙값 반환 (이상치에 덜 민감)
    return {
        "score": statistics.median(scores),
        "score_range": (min(scores), max(scores)),
        "consistency": 1 - (score_range / 100),
        "all_reasonings": [r["final_reasoning"] for r in results]
    }
```

#### 방안 3: 신뢰도 기반 평가
```python
class TurnEvaluation(BaseModel):
    score: float
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="평가 신뢰도 (일관성 기반)"
    )
    
    # 신뢰도가 낮으면 다중 평가 수행
    if confidence < 0.7:
        result = await evaluate_with_consistency(state, n_samples=3)
```

---

## 6a 노드 (Holistic Evaluator) 구조화 전략

### 현재 구조
- 구조화된 출력: `HolisticFlowEvaluation` (Pydantic 모델)
- LLM의 사고 능력을 적극 활용 예정

### 비판적 분석

#### 구조화의 필요성
- **필요한 부분**: 핵심 점수 (비교/집계용)
- **불필요한 부분**: 상세 분석 (LLM 능력 활용)

### 개선 방안: 계층적 구조화

#### Level 1: 핵심 지표 (구조화 필수)
```python
class HolisticFlowEvaluation(BaseModel):
    """전체 플로우 평가 결과"""
    # 핵심 점수 (구조화 필수 - 비교/집계용)
    overall_flow_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="전체 플로우 점수"
    )
    strategy_coherence: float
    problem_solving_approach: float
    iteration_quality: float
```

#### Level 2: 상세 분석 (구조화 선택)
```python
class DetailedHolisticAnalysis(BaseModel):
    """상세 분석 (LLM이 자유롭게 분석)"""
    problem_decomposition_insights: str = Field(
        ...,
        description="문제 분해 패턴 분석"
    )
    feedback_integration_patterns: str = Field(
        ...,
        description="피드백 수용 패턴 분석"
    )
    strategic_shifts: str = Field(
        ...,
        description="전략적 전환 분석"
    )
    advanced_techniques_used: List[str] = Field(
        ...,
        description="사용된 고급 프롬프트 기법"
    )
    improvement_suggestions: str = Field(
        ...,
        description="개선 제안"
    )
```

#### Level 3: 자유 텍스트 (구조화 불필요)
```python
class HolisticFlowEvaluation(BaseModel):
    # 핵심 점수 (구조화)
    overall_flow_score: float
    
    # 자유 분석 (구조화 불필요)
    free_analysis: str = Field(
        ...,
        description="LLM이 자유롭게 작성한 전체 분석"
    )
    key_insights: List[str] = Field(
        ...,
        description="핵심 인사이트만 추출 (구조화)"
    )
```

### 권장: Level 1 + Level 3 하이브리드
- 핵심 점수는 구조화 (비교/집계)
- 상세 분석은 자유 텍스트 (LLM 능력 활용)
- 핵심 인사이트만 구조화하여 추출

---

## 평가 명확성과 유연성의 균형

### 현재 균형
```
명확성: ⬆️⬆️⬆️ (구조화된 출력, 고정 기준)
유연성: ⬇️⬇️ (고정 카테고리, 제한된 평가)
```

### 개선 방향

#### 전략: 하이브리드 접근
```python
class EnhancedTurnEvaluation(BaseModel):
    """명확성 + 유연성 균형"""
    
    # 명확성 부분 (구조화 필수)
    structured_evaluation: StructuredEvaluation
    
    # 유연성 부분 (구조화 선택)
    llm_insights: Optional[LLMInsights] = None
    
    # 최종 점수 (명확성 기반, 유연성 보정)
    final_score: float = Field(
        ...,
        computed=lambda self: self.compute_final_score()
    )
    
    def compute_final_score(self) -> float:
        """명확성 기반, 유연성 보정"""
        base_score = self.structured_evaluation.score
        
        if self.llm_insights and self.structured_evaluation.confidence < 0.8:
            # 신뢰도 낮으면 LLM 보정 적용
            adjustment = self.llm_insights.adjustment_factor
            return base_score * 0.7 + (base_score * adjustment) * 0.3
        
        return base_score

class StructuredEvaluation(BaseModel):
    """구조화된 평가 (명확성)"""
    score: float
    rubrics: list[Rubric]
    confidence: float  # 평가 신뢰도

class LLMInsights(BaseModel):
    """LLM 인사이트 (유연성)"""
    contextual_factors: List[str]
    hidden_patterns: List[str]
    improvement_suggestions: List[str]
    adjustment_factor: float = Field(
        ...,
        ge=-0.2,
        le=0.2,
        description="점수 조정 계수 (-20% ~ +20%)"
    )
    adjustment_reasoning: str
```

#### 단계별 평가 프로세스
```python
async def enhanced_evaluation(state: EvalTurnState) -> EnhancedTurnEvaluation:
    """
    향상된 평가 (명확성 + 유연성)
    """
    # Step 1: 구조화된 평가 (명확성)
    structured_result = await structured_evaluation(state)
    
    # Step 2: 신뢰도 검사
    if structured_result.confidence < 0.8:
        # 신뢰도 낮으면 LLM 보정 (유연성)
        llm_insights = await llm_contextual_evaluation(state, structured_result)
        final_score = combine_scores(structured_result, llm_insights)
    else:
        # 신뢰도 높으면 구조화된 평가만 사용
        final_score = structured_result.score
        llm_insights = None
    
    return EnhancedTurnEvaluation(
        structured_evaluation=structured_result,
        llm_insights=llm_insights,
        final_score=final_score
    )
```

---

## 구현 우선순위

### Phase 1: 핵심 개선 (즉시 구현)
1. ✅ 의도 정의 구체화 (예시, 키워드, 배제 기준)
2. ✅ 평가 기준 구체화 (프롬프트 엔지니어링 강화)
3. ✅ 우선순위 기반 의도 선택 (단일 선택 + 우선순위)

### Phase 2: 일관성 향상 (단기)
1. 신뢰도 필드 추가 (`confidence`)
2. 평가 기준 구체화 (점수 범위별 예시)
3. 다중 평가 메커니즘 (선택적)

### Phase 3: 유연성 확보 (중기)
1. 사고 과정 평가 추가
2. 구체적 피드백 제공
3. LLM 인사이트 통합

### Phase 4: 고도화 (장기)
1. 학습 곡선 추적
2. 맞춤형 학습 경로 제시
3. 동적 평가 기준 (의도별 특화)

---

## 결론

### 핵심 원칙
1. **기본 구조는 유지** (출력 제한 환경 대응)
2. **LLM 능력을 선택적으로 활용** (보완적 역할)
3. **평가 명확성과 유연성의 균형**

### 최종 권장사항
- **의도 분류**: 구체적 정의 + 우선순위 기반 단일 선택
- **평가 기준**: 매우 구체적인 프롬프트 엔지니어링 (복잡해도 좋음)
- **일관성**: 평가 기준 구체화 + 신뢰도 기반 다중 평가 (선택적)
- **6a 노드**: 계층적 구조화 (핵심 점수 구조화 + 상세 분석 자유)
- **균형**: 하이브리드 접근 (구조화 + LLM 보정)

---

## 참고 자료
- [Claude Prompt Engineering Guide](https://platform.claude.com/docs/ko/build-with-claude/prompt-engineering/overview)
- [Middleware Guide](./Middleware_Guide.md)
- [Guardrail Implementation Strategy](./Guardrail_Implementation_Strategy.md)



