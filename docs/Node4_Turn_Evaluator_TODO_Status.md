# Node 4번 (Turn Evaluator) TODO 리스트 현황

## 📋 개요

이전에 계획되었던 Node 4번(Turn Evaluator) 개선 사항들의 현재 상태를 정리합니다.

---

## ✅ 완료된 항목

### Phase 1: 핵심 개선 (즉시 구현)

1. ✅ **의도 정의 구체화** (예시, 키워드, 배제 기준)
   - 상태: 완료
   - 파일: `app/domain/langgraph/nodes/turn_evaluator/analysis.py`
   - 내용: 8가지 의도 분류 시스템 구현

2. ✅ **평가 기준 구체화** (프롬프트 엔지니어링 강화)
   - 상태: 완료
   - 파일: `app/domain/langgraph/nodes/turn_evaluator/evaluators.py`
   - 내용: 5가지 평가 기준(명확성, 문제 적절성, 예시, 규칙, 문맥) 구현

3. ✅ **우선순위 기반 의도 선택** (단일 선택 + 우선순위)
   - 상태: 부분 완료
   - 파일: `app/domain/langgraph/nodes/turn_evaluator/routers.py`
   - 내용: 복수 의도 선택 가능 (우선순위 기반 단일 선택은 미구현)

4. ✅ **평가 피드백 강화**
   - 상태: 완료
   - 파일: `app/domain/langgraph/nodes/turn_evaluator/evaluators.py`
   - 내용: `rubrics`, `final_reasoning` 필드 추가

5. ✅ **토큰 추적 구현**
   - 상태: 완료
   - 파일: `app/domain/langgraph/nodes/turn_evaluator/`
   - 내용: 모든 평가 노드에서 토큰 사용량 추적

---

## 🔄 진행 중인 항목

없음

---

## 📝 미완료 항목 (예정)

### Phase 2: 일관성 향상 (단기)

1. ⏳ **신뢰도 필드 추가** (`confidence`)
   - 상태: 미구현
   - 계획: `TurnEvaluation` 모델에 `confidence` 필드 추가
   - 파일: `app/domain/langgraph/states.py`, `app/domain/langgraph/nodes/turn_evaluator/evaluators.py`
   - 우선순위: 중간

2. ⏳ **평가 기준 구체화** (점수 범위별 예시)
   - 상태: 부분 완료
   - 계획: 각 점수 범위(0-49, 50-69, 70-89, 90-100)별 구체적 예시 추가
   - 파일: `app/domain/langgraph/nodes/turn_evaluator/evaluators.py`
   - 우선순위: 중간

3. ⏳ **다중 평가 메커니즘** (선택적)
   - 상태: 미구현
   - 계획: 신뢰도가 낮을 때만 N번 평가하여 일관성 확보
   - 파일: `app/domain/langgraph/nodes/turn_evaluator/evaluators.py`
   - 우선순위: 낮음

### Phase 3: 유연성 확보 (중기)

1. ⏳ **사고 과정 평가 추가**
   - 상태: 미구현
   - 계획: 문제 이해도, 전략 선택, 프롬프트 개선, 맥락 활용, 학습 곡선 추적
   - 파일: `app/domain/langgraph/nodes/turn_evaluator/` (신규 파일 필요)
   - 우선순위: 중간

2. ⏳ **구체적 피드백 제공**
   - 상태: 부분 완료 (기본 피드백은 구현됨)
   - 계획: 강점/약점 분석, 개선 제안, 다음 단계 가이드, 맞춤형 학습 경로
   - 파일: `app/domain/langgraph/nodes/turn_evaluator/aggregation.py`
   - 우선순위: 중간

3. ⏳ **LLM 인사이트 통합**
   - 상태: 미구현
   - 계획: 맥락 기반 평가, 숨겨진 평가 포인트 발견
   - 파일: `app/domain/langgraph/nodes/turn_evaluator/evaluators.py`
   - 우선순위: 낮음

### Phase 4: 고도화 (장기)

1. ⏳ **학습 곡선 추적**
   - 상태: 미구현
   - 계획: 턴별 점수 추이 분석, 개선율 계산
   - 파일: `app/domain/langgraph/nodes/turn_evaluator/` (신규 파일 필요)
   - 우선순위: 낮음

2. ⏳ **맞춤형 학습 경로 제시**
   - 상태: 미구현
   - 계획: 약점 기반 학습 자료 추천
   - 파일: `app/domain/langgraph/nodes/turn_evaluator/` (신규 파일 필요)
   - 우선순위: 낮음

3. ⏳ **동적 평가 기준** (의도별 특화)
   - 상태: 미구현
   - 계획: 의도별 특화 평가 기준 추가 (예: HINT_OR_QUERY는 예시/규칙/문맥 선택)
   - 파일: `app/domain/langgraph/nodes/turn_evaluator/evaluators.py`
   - 우선순위: 낮음

---

## 🎯 이전 대화 요약의 TODO 리스트

### 원래 계획되었던 항목들

1. ✅ `intent_classification_hybrid`: 하이브리드 의도 분류 구현
   - 상태: 부분 완료 (복수 선택 가능, LLM 보완은 미구현)

2. ⏳ `evaluation_criteria_dynamic`: 동적 평가 기준 구현
   - 상태: 미구현
   - 내용: 공통 기준(5가지) + LLM 추가 평가(의도별 특화 기준)

3. ⏳ `thinking_process_evaluation`: 사고 과정 평가 추가
   - 상태: 미구현
   - 내용: 문제 이해도, 전략 선택, 프롬프트 개선, 맥락 활용, 학습 곡선 추적

4. ⏳ `feedback_enhancement`: 구체적 피드백 제공
   - 상태: 부분 완료 (기본 피드백은 구현됨)
   - 내용: 강점/약점 분석, 개선 제안, 다음 단계 가이드, 맞춤형 학습 경로

5. ⏳ `intent_priority_system`: 우선순위 기반 의도 선택
   - 상태: 미구현
   - 내용: 단일 선택 + 우선순위 규칙으로 모호성 감소

6. ⏳ `intent_definitions_refinement`: 의도 정의 구체화
   - 상태: 부분 완료 (기본 정의는 있음)
   - 내용: 예시, 키워드, 배제 기준 추가로 LLM 분류 일관성 향상

---

## 📊 현재 상태 요약

### 완료율
- **Phase 1 (핵심 개선)**: 80% 완료
- **Phase 2 (일관성 향상)**: 0% 완료
- **Phase 3 (유연성 확보)**: 20% 완료
- **Phase 4 (고도화)**: 0% 완료

### 전체 진행률
- **완료**: 5개 항목
- **부분 완료**: 3개 항목
- **미완료**: 10개 항목

---

## 🔗 관련 문서

- `docs/Evaluation_System_Improvement_Strategy.md`: 평가 시스템 개선 전략
- `docs/Evaluation_System_Architecture.md`: 평가 시스템 아키텍처
- `docs/Evaluation_Feedback_Implementation.md`: 평가 피드백 구현

---

## 📝 참고사항

### 현재 우선순위

**높음:**
- 의도 분류 일관성 향상 (복수 선택 시 우선순위 기반 단일 선택)
- 평가 기준 구체화 (점수 범위별 예시)

**중간:**
- 신뢰도 필드 추가
- 사고 과정 평가 추가
- 구체적 피드백 강화

**낮음:**
- 다중 평가 메커니즘
- LLM 인사이트 통합
- 학습 곡선 추적
- 맞춤형 학습 경로
- 동적 평가 기준

