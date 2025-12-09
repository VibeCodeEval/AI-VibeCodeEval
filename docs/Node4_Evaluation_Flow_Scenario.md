# 4번 노드 평가 시나리오 및 함수 관계

## 📋 개요

4번 노드(Turn Evaluator)의 평가 시나리오와 핵심 함수들의 관계를 정리합니다.

---

## 🔗 두 부분의 관계

### 1. `prepare_evaluation_input_internal` (49-111줄)

**역할**: 평가 프롬프트 생성 함수

**위치**: `app/domain/langgraph/nodes/turn_evaluator/evaluators.py`

**기능**:
- 문제 정보 추출 및 포맷팅
- 정량적 메트릭 계산 (`calculate_all_metrics`)
- 평가 기준(5개 루브릭) 포함한 system_prompt 생성
- user_prompt 생성 (사용자 프롬프트 + AI 응답)

**생성하는 프롬프트 구조**:
```
[시스템 프롬프트]
- Role: 프롬프트 엔지니어링 전문가
- 문제 정보 (제목, 필수 알고리즘)
- 정량적 메트릭 (텍스트 길이, 단어 수, 예시 개수 등)
- 평가 기준 (5개 루브릭):
  1. 명확성 (Clarity)
  2. 문제 적절성 (Problem Relevance)
  3. 예시 (Examples)
  4. 규칙 (Rules) - criteria 파라미터로 동적 삽입
  5. 문맥 (Context)

[사용자 프롬프트]
- 사용자 프롬프트
- AI 응답 (참고용)
```

**호출 위치**:
- `_evaluate_turn()` 함수 내부 (251줄)
- `create_evaluation_chain()` 함수 내부 (160줄)

---

### 2. `_evaluate_turn` (232-244줄)

**역할**: 공통 턴 평가 실행 함수

**위치**: `app/domain/langgraph/nodes/turn_evaluator/evaluators.py`

**기능**:
- `prepare_evaluation_input_internal` 호출하여 프롬프트 생성
- LLM 호출 (토큰 추적 포함)
- 구조화된 출력 파싱 (`TurnEvaluation` 모델)
- 결과 반환 (score, rubrics, final_reasoning)

**호출 위치**:
- 모든 개별 평가 함수들에서 호출:
  - `eval_system_prompt()` (313줄)
  - `eval_rule_setting()` (328줄)
  - `eval_generation()` (343줄)
  - `eval_optimization()` (358줄)
  - `eval_debugging()` (373줄)
  - `eval_test_case()` (388줄)
  - `eval_hint_query()` (403줄)
  - `eval_follow_up()` (418줄)

---

## 🔄 함수 호출 관계도

```
┌─────────────────────────────────────────┐
│  개별 평가 함수들                        │
│  (eval_system_prompt, eval_generation,  │
│   eval_optimization, ...)                │
└──────────────┬──────────────────────────┘
               │ 호출
               ▼
┌─────────────────────────────────────────┐
│  _evaluate_turn()                       │
│  - 공통 평가 로직                        │
│  - LLM 호출 및 파싱                      │
└──────────────┬──────────────────────────┘
               │ 호출 (251줄)
               ▼
┌─────────────────────────────────────────┐
│  prepare_evaluation_input_internal()    │
│  - 프롬프트 생성                         │
│  - 문제 정보 + 메트릭 + 평가 기준         │
└─────────────────────────────────────────┘
```

---

## 📊 평가 시나리오

### 전체 평가 플로우

```
1. Intent Analysis (의도 분석)
   └─> intent_analysis()
       └─> LLM으로 8가지 의도 중 분류
           (SYSTEM_PROMPT, RULE_SETTING, GENERATION, 
            OPTIMIZATION, DEBUGGING, TEST_CASE, 
            HINT_OR_QUERY, FOLLOW_UP)

2. Intent Router (의도별 라우팅)
   └─> intent_router()
       └─> 의도에 따라 평가 노드 선택
           └─> 다중 의도 시 병렬 실행 가능

3. 개별 평가 함수 실행 (의도별)
   └─> eval_system_prompt() / eval_generation() / ...
       └─> _evaluate_turn() 호출
           └─> prepare_evaluation_input_internal() 호출
               └─> 프롬프트 생성
           └─> LLM 호출
           └─> 결과 파싱 (TurnEvaluation)
           └─> 반환: {score, rubrics, final_reasoning}

4. Turn Log Aggregation (턴 로그 집계)
   └─> aggregate_turn_log()
       └─> 모든 평가 결과 수집
       └─> 평균 점수 계산
       └─> turn_log 생성
```

---

## 🎯 평가 시나리오 상세

### 시나리오 1: 단일 의도 (예: GENERATION)

```
1. Intent Analysis
   └─> 의도: ["GENERATION"]

2. Intent Router
   └─> 선택된 노드: ["eval_generation"]

3. eval_generation() 실행
   └─> _evaluate_turn() 호출
       ├─> eval_type: "코드 생성 요청 (Generation)"
       ├─> criteria: "원하는 기능의 입출력 예시를 제공하고, 구현 조건을 상세히 기술했는가?"
       └─> prepare_evaluation_input_internal() 호출
           ├─> 문제 정보 추출
           ├─> 메트릭 계산
           ├─> system_prompt 생성 (5개 루브릭 포함)
           └─> user_prompt 생성
       └─> LLM 호출
       └─> 결과 파싱
       └─> 반환: {score: 85, rubrics: [...], final_reasoning: "..."}

4. aggregate_turn_log()
   └─> turn_score: 85
```

---

### 시나리오 2: 다중 의도 (예: GENERATION + OPTIMIZATION)

```
1. Intent Analysis
   └─> 의도: ["GENERATION", "OPTIMIZATION"]

2. Intent Router
   └─> 선택된 노드: ["eval_generation", "eval_optimization"]

3. 병렬 실행 (LangGraph)
   ├─> eval_generation() 실행
   │   └─> _evaluate_turn() 호출
   │       ├─> eval_type: "코드 생성 요청 (Generation)"
   │       └─> 결과: {score: 85, ...}
   │
   └─> eval_optimization() 실행
       └─> _evaluate_turn() 호출
           ├─> eval_type: "최적화 요청 (Optimization)"
           └─> 결과: {score: 70, ...}

4. aggregate_turn_log()
   └─> turn_score: (85 + 70) / 2 = 77.5
```

---

## 📝 프롬프트 구조 상세

### `prepare_evaluation_input_internal`이 생성하는 프롬프트

**System Prompt 구성**:
1. **Role 정의**: "당신은 '프롬프트 엔지니어링' 전문가입니다."
2. **문제 정보** (문제 정보가 있는 경우):
   ```
   [문제 정보]
   - 문제: {problem_title}
   - 필수 알고리즘: {algorithms_text}
   ```
3. **정량적 메트릭**:
   ```
   [정량적 메트릭 (참고용)]
   - 텍스트 길이: {text_length}자
   - 단어 수: {word_count}개
   - 문장 수: {sentence_count}개
   - 명확성 메트릭: 구체적 값 포함 {has_specific_values}, 값 개수 {specific_value_count}개
   - 예시 메트릭: 예시 포함 {has_examples}, 예시 개수 {example_count}개
   - 규칙 메트릭: XML 태그 {xml_tag_count}개, 제약조건 {constraint_count}개
   - 문맥 메트릭: 이전 대화 참조 {has_context_reference}, 참조 횟수 {context_reference_count}회
   - 문제 적절성 메트릭: 기술 용어 {technical_term_count}개
   - 코드 블록: {has_code_blocks}, {code_block_count}개
   ```
4. **평가 기준 (5개 루브릭)**:
   - 각 루브릭마다 메트릭 참고값과 점수 범위별 기준 포함
   - 4번 루브릭(Rules)은 `criteria` 파라미터로 동적 삽입

**User Prompt 구성**:
```
[사용자 프롬프트]
{human_message}

[AI 응답 (참고용)]
{ai_message}

위 사용자 프롬프트를 '{eval_type}' 관점에서 평가하세요.
```

---

## 🔍 평가 기준 (5개 루브릭)

### 1. 명확성 (Clarity)
- **메트릭**: 단어 수, 문장 수, 구체적 값 개수
- **점수 기준**:
  - 90-100점: 단어 수 20-200개, 문장 수 2-10개, 구체적 값 1개 이상
  - 70-89점: 단어 수 10-20개 또는 200-300개, 문장 수 1-2개 또는 10-15개
  - 50-69점: 단어 수 5-10개 또는 300개 이상, 문장 수 1개 또는 15개 이상
  - 0-49점: 단어 수 5개 미만, 문장 수 1개 미만, 매우 모호한 표현

### 2. 문제 적절성 (Problem Relevance)
- **메트릭**: 기술 용어 개수
- **점수 기준**:
  - 90-100점: 기술 용어 3개 이상, 문제 특성에 맞는 알고리즘 명시
  - 70-89점: 기술 용어 1-2개, 문제 관련 키워드 언급
  - 50-69점: 기술 용어 0-1개, 문제와 관련 있지만 구체적 알고리즘 없음
  - 0-49점: 기술 용어 0개, 문제와 무관한 요청

### 3. 예시 (Examples)
- **메트릭**: 예시 포함 여부, 예시 개수
- **점수 기준**:
  - 90-100점: 예시 2개 이상, 입출력 쌍 포함, 엣지 케이스 포함
  - 70-89점: 예시 1개, 기본 케이스만
  - 50-69점: 예시 없지만 상황 설명
  - 0-49점: 예시 없음, 추상적 표현만

### 4. 규칙 (Rules)
- **메트릭**: XML 태그 개수, 제약조건 개수, 구조화 형식 사용 여부
- **criteria**: 평가 유형별로 동적으로 변경
  - System Prompt: "AI에게 구체적인 역할을 부여하고, 임무의 범위와 답변 스타일을 명확히 정의했는가?"
  - Generation: "원하는 기능의 입출력 예시를 제공하고, 구현 조건을 상세히 기술했는가?"
  - Optimization: "현재 코드의 문제점을 지적하고, 목표 성능이나 구체적인 최적화 전략을 제시했는가?"
  - 등등...
- **점수 기준**:
  - 90-100점: XML 태그 2개 이상 또는 제약조건 2개 이상, 구조화 형식 사용, 출력 형식 지정
  - 70-89점: XML 태그 1개 또는 제약조건 1개, 구조화 형식 사용, 출력 형식 지정
  - 50-69점: 제약조건 언급 (XML 태그 없음), 간단한 구조화, 출력 형식 지정
  - 0-49점: 제약조건 없음, 구조화 형식 없음, 출력 형식 지정 없음

### 5. 문맥 (Context)
- **메트릭**: 이전 대화 참조 여부, 참조 횟수
- **점수 기준**:
  - 90-100점: 이전 대화 참조 2회 이상, 구체적 내용 언급
  - 70-89점: 이전 대화 참조 1회, 간단한 언급
  - 50-69점: 맥락 활용 시도 (불명확)
  - 0-49점: 맥락 활용 없음

---

## 💡 핵심 포인트

### 두 함수는 함께 사용됨

1. **`prepare_evaluation_input_internal`**: 
   - 프롬프트 생성만 담당
   - 재사용 가능한 유틸리티 함수
   - 문제 정보, 메트릭, 평가 기준을 종합하여 프롬프트 생성

2. **`_evaluate_turn`**: 
   - 실제 평가 실행 담당
   - `prepare_evaluation_input_internal`을 내부적으로 호출
   - LLM 호출, 파싱, 결과 반환까지 전체 평가 프로세스 관리

### 평가 시나리오 요약

1. **의도 분석** → 8가지 의도 중 분류
2. **의도별 라우팅** → 해당 평가 함수 선택
3. **개별 평가 실행** → `_evaluate_turn` 호출
   - 프롬프트 생성 (`prepare_evaluation_input_internal`)
   - LLM 호출
   - 결과 파싱
4. **턴 로그 집계** → 모든 평가 결과 종합

### 프롬프트 특징

- **문제 정보 포함**: 문제 제목, 필수 알고리즘
- **정량적 메트릭 포함**: 객관적 측정값 제공
- **5개 루브릭**: 명확성, 문제 적절성, 예시, 규칙, 문맥
- **동적 criteria**: 평가 유형별로 4번 루브릭(Rules)의 기준이 변경됨
- **점수 범위별 기준**: 각 루브릭마다 4단계 점수 기준 제공

---

## 📌 참고

- `create_evaluation_chain()` 함수는 현재 사용되지 않음 (레거시 코드)
- 실제 평가는 `_evaluate_turn()` 함수를 직접 호출하는 방식 사용
- 모든 평가 함수는 동일한 프롬프트 구조를 사용하되, `eval_type`과 `criteria`만 변경



