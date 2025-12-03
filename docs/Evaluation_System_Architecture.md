# 평가 시스템 아키텍처 문서

## 📋 개요

이 문서는 현재 LangGraph 평가 시스템의 전체 아키텍처와 Intent 분석, 평가 방식에 대한 상세한 설명을 제공합니다.

---

## 🏗️ 시스템 아키텍처

### 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph Main Flow                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [1] Handle Request                                          │
│      └─ 턴 번호 증가, 상태 초기화                            │
│                                                              │
│  [2] Intent Analyzer (2-Layer Guardrails)                    │
│      ├─ Layer 1: 키워드 기반 빠른 검증                       │
│      └─ Layer 2: LLM 기반 상세 분석                          │
│         ├─ 가드레일 검사                                     │
│         ├─ Guide Strategy 결정                              │
│         └─ Intent Status 결정                                │
│                                                              │
│  [3] Writer LLM                                              │
│      └─ Guide Strategy에 따른 Socratic 답변 생성            │
│                                                              │
│  [4] Turn Evaluator (백그라운드)                            │
│      └─ Eval Turn SubGraph 실행                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Eval Turn SubGraph (Node 4)                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [4.0] Intent Analysis                                       │
│      └─ 8가지 Intent 분류 (복수 선택 가능)                   │
│                                                              │
│  [4.0.1] Intent Router                                       │
│      └─ 선택된 Intent에 따라 평가 노드 라우팅                │
│                                                              │
│  [4.R~4.F] 의도별 평가                                       │
│      ├─ [4.R] Rule Setting                                  │
│      ├─ [4.G] Generation                                     │
│      ├─ [4.O] Optimization                                  │
│      ├─ [4.D] Debugging                                      │
│      ├─ [4.T] Test Case                                      │
│      ├─ [4.H] Hint/Query                                     │
│      └─ [4.F] Follow Up                                      │
│                                                              │
│  [4.X] Answer Summary                                        │
│      └─ AI 답변 요약                                         │
│                                                              │
│  [4.4] Turn Log Aggregation                                 │
│      └─ 턴 점수 계산 및 로그 생성                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│         Holistic Evaluator (코드 제출 시)                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [6a] Holistic Flow Evaluation                               │
│      └─ 전체 플로우 평가 (문제 분해, 피드백 수용성 등)       │
│                                                              │
│  [6b] Aggregate Turn Scores                                  │
│      └─ 모든 턴 점수의 평균                                  │
│                                                              │
│  [6c] Code Performance                                       │
│      └─ 코드 성능 평가                                       │
│                                                              │
│  [6d] Code Correctness                                       │
│      └─ 코드 정확성 평가                                     │
│                                                              │
│  [7] Aggregate Final Scores                                  │
│      └─ 최종 점수 집계 및 등급 산정                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔍 Intent 분석 상세

### Intent Analyzer (Node 2)

#### 목적
- 사용자 메시지의 의도 분석
- 가드레일 검사 (정답 직접 요청 차단)
- Guide Strategy 결정 (Writer LLM의 답변 스타일 결정)

#### 2-Layer Guardrails

**Layer 1: 키워드 기반 빠른 검증**
- **목적**: 정답 직접 요청을 빠르게 차단 (LLM 호출 없음)
- **방식**: 정규식/키워드 매칭
- **차단 키워드**: 
  - 일반: "정답 코드", "전체 코드", "완성된 코드" 등
  - 문제별: 문제 컨텍스트에 따라 동적 추가

**Layer 2: LLM 기반 상세 분석**
- **목적**: 더 정교한 가드레일 검사 및 Guide Strategy 결정
- **입력**: 사용자 메시지, 문제 컨텍스트
- **출력**: 
  - `status`: "SAFE" 또는 "BLOCKED"
  - `block_reason`: "DIRECT_ANSWER", "JAILBREAK", "OFF_TOPIC" (BLOCKED인 경우)
  - `guide_strategy`: "SYNTAX_GUIDE", "LOGIC_HINT", "ROADMAP" (SAFE인 경우)
  - `intent_status`: "PASSED_HINT", "PASSED_SUBMIT", "FAILED_GUARDRAIL"

#### Guide Strategy

**SYNTAX_GUIDE**
- 문법/구문 관련 질문
- 예: "Python에서 리스트 컴프리헨션 문법이 뭐야?"

**LOGIC_HINT**
- 로직/알고리즘 관련 질문
- 예: "비트마스킹을 어떻게 사용해야 할까?"

**ROADMAP**
- 전체적인 접근 방법 질문
- 예: "이 문제를 어떻게 접근해야 할까?"

---

### Turn Evaluator Intent Analysis (Node 4.0)

#### 목적
- 턴의 의도를 8가지 유형으로 분류
- 복수 선택 가능 (한 턴에 여러 Intent 포함 가능)

#### 8가지 Intent 유형

1. **SYSTEM_PROMPT**
   - 시스템 프롬프트 설정, AI 역할/페르소나 정의
   - 평가 대상 아님

2. **RULE_SETTING**
   - 규칙 설정, 요구사항 정의, 제약조건 설명
   - 평가 노드: [4.R]

3. **GENERATION**
   - 새로운 코드 생성 요청
   - 평가 노드: [4.G]

4. **OPTIMIZATION**
   - 기존 코드 최적화, 성능 개선
   - 평가 노드: [4.O]

5. **DEBUGGING**
   - 버그 수정, 오류 해결
   - 평가 노드: [4.D]

6. **TEST_CASE**
   - 테스트 케이스 작성, 테스트 관련
   - 평가 노드: [4.T]

7. **HINT_OR_QUERY**
   - 힌트 요청, 질문, 설명 요청
   - 평가 노드: [4.H]

8. **FOLLOW_UP**
   - 후속 질문, 추가 요청, 확인
   - 평가 노드: [4.F]

#### Intent Router (Node 4.0.1)

**역할**: 선택된 Intent에 따라 평가 노드를 동적으로 라우팅

**로직**:
```python
if "rule_setting" in intent_types:
    → eval_rule_setting()
if "generation" in intent_types:
    → eval_generation()
# ... (나머지 Intent도 동일)
```

---

## 📊 평가 방식 상세

### Turn Evaluator 평가 (Node 4.R~4.F)

#### 평가 기준: Claude Prompt Engineering 5가지

1. **명확성 (Clarity)**
   - 요청이 모호하지 않고 구체적인가?
   - 기술적 용어를 사용했는가?
   - 구체적 키워드를 포함했는가?

2. **문제 적절성 (Problem Relevance)**
   - 요청이 문제 특성에 적합한가?
   - 필수 알고리즘을 언급했는가?
   - 문제 컨텍스트를 활용했는가?

3. **예시 (Examples)**
   - 입출력 예시를 제공했는가?
   - 엣지 케이스를 포함했는가?
   - 멀티샷 예시를 제공했는가?

4. **규칙 (Rules)**
   - 제약조건을 명시했는가?
   - XML 태그를 사용했는가?
   - 복잡도 요구사항을 명시했는가?

5. **문맥 (Context)**
   - 이전 대화를 참조했는가?
   - 배경 지식을 활용했는가?
   - 대화 흐름을 고려했는가?

#### 의도별 특화 기준

**Rule Setting (4.R)**
- 제약 조건(시간/공간 복잡도, 언어 등)을 명확히 XML 태그나 리스트로 명시했는가?

**Generation (4.G)**
- 원하는 기능의 입출력 예시(Input/Output Examples)를 제공하고, 구현 조건을 상세히 기술했는가?

**Optimization (4.O)**
- 현재 코드의 문제점(병목)을 지적하고, 목표 성능(O(n) 등)이나 구체적인 최적화 전략을 제시했는가?

**Debugging (4.D)**
- 발생한 에러 메시지, 재현 단계, 또는 예상치 못한 동작을 구체적으로 설명했는가?

**Test Case (4.T)**
- 테스트하고 싶은 엣지 케이스(Edge Cases)나 경계 조건(Boundary Conditions)을 명시했는가?

**Hint/Query (4.H)**
- 단순히 정답을 묻는 것이 아니라, 자신의 사고 과정(Chain of Thought)을 공유하고 막힌 부분을 구체적으로 질문했는가?

**Follow Up (4.F)**
- 이전 턴의 AI 답변을 기반으로, 추가적인 개선점이나 의문점을 논리적으로 연결하여 질문했는가?

#### 점수 계산

**각 Intent 평가 점수**: 0-100점
- Claude Prompt Engineering 5가지 기준 각각 0-100점 평가
- 5가지 기준의 평균 또는 가중 평균

**턴 점수**: 모든 Intent 평가 점수의 평균
```python
turn_score = sum(intent_scores) / len(intent_scores)
```

**가드레일 위반 시**: 즉시 0점 처리

---

### Holistic Flow Evaluation (Node 6a)

#### 평가 기준

1. **문제 분해 (Problem Decomposition)**
   - 전체 코드가 아닌 부분 코드로 점진적으로 구성되는가?
   - 큰 문제를 작은 단계로 나누어 해결하는가?
   - 문제 특성에 맞는 접근 방식인가?
   - 힌트 로드맵 순서와 유사하게 진행되었는가?

2. **피드백 수용성 (Feedback Integration)**
   - 턴 N의 AI 힌트 내용이 턴 N+1의 사용자 요청에 반영되었는가?
   - 이전 턴의 제안을 다음 턴에서 활용하는가?

3. **주도성 및 오류 수정 (Proactiveness)**
   - 사용자가 AI의 이전 오류를 구체적으로 지적하는가?
   - 능동적으로 개선 방향을 제시하는가?

4. **전략적 탐색 (Strategic Exploration)**
   - 의도가 HINT_OR_QUERY에서 OPTIMIZATION으로 전환되는 등 능동적인 변화가 있는가?
   - DEBUGGING에서 TEST_CASE로 전환하는 등 전략적 탐색이 있는가?

5. **고급 프롬프트 기법 활용 (Advanced Techniques Bonus)**
   - System Prompting, XML 태그, Few-shot 예시 등 고급 기법을 사용했는가?
   - 이러한 기법 사용 시 보너스 점수를 부여

#### 점수 계산

**점수 범위**: 0-100점
- 각 항목을 0-100점으로 평가
- `overall_flow_score`를 종합 점수로 반환

---

## 📈 점수 집계 방식

### 턴 점수 집계 (Node 4.4)

```python
# 모든 Intent 평가 점수 수집
all_scores = []
for eval_data in eval_results.values():
    score = eval_data.get("score", 0)
    all_scores.append(score)

# 평균 계산
turn_score = sum(all_scores) / len(all_scores) if all_scores else 0
```

### 턴 점수 평균 (Node 6b)

```python
# 모든 턴 점수 수집
all_scores = []
for turn, scores in turn_scores.items():
    if "turn_score" in scores:
        all_scores.append(scores["turn_score"])

# 평균 계산
aggregate_turn_score = sum(all_scores) / len(all_scores) if all_scores else 0
```

### 프롬프트 점수 (Node 7)

```python
# Holistic Flow 점수와 턴 점수 평균의 평균
prompt_scores = []
if holistic_flow_score is not None:
    prompt_scores.append(holistic_flow_score)
if aggregate_turn_score is not None:
    prompt_scores.append(aggregate_turn_score)

prompt_score = sum(prompt_scores) / len(prompt_scores) if prompt_scores else 0
```

### 최종 점수 (Node 7)

```python
# 가중 평균
total_score = (
    prompt_score * 0.25 +      # 프롬프트 활용 (25%)
    perf_score * 0.25 +        # 성능 (25%)
    correctness_score * 0.50   # 정확성 (50%)
)
```

**등급 기준**:
- **A**: 90점 이상
- **B**: 80점 이상
- **C**: 70점 이상
- **D**: 60점 이상
- **F**: 60점 미만

---

## 🔄 평가 흐름 예시

### 시나리오: TSP 문제 해결

#### 턴 1: HINT_OR_QUERY
```
사용자: "TSP 문제를 해결하려고 하는데, N이 최대 16이므로 O(N!) 완전 탐색은 시간 초과가 발생할 것 같습니다. 비트마스킹을 사용해야 한다는 것은 알겠지만, 상태를 어떻게 정의해야 할지 막막합니다."
```

**처리**:
1. [2] Intent Analyzer: PASSED_HINT, LOGIC_HINT
2. [3] Writer LLM: 비트마스킹 개념 설명
3. [4] Turn Evaluator (백그라운드):
   - Intent: HINT_OR_QUERY
   - 평가: 명확성(90), 문제 적절성(95), 예시(70), 규칙(60), 문맥(80)
   - 점수: 79점

#### 턴 2: GENERATION
```
사용자: "비트마스킹을 사용하여 TSP 문제의 메모이제이션 부분을 작성해주세요. dp[current][visited] 형태로 구현하고, visited는 비트마스크로 표현하세요."
```

**처리**:
1. [2] Intent Analyzer: PASSED_HINT, LOGIC_HINT
2. [3] Writer LLM: 부분 코드 생성
3. [4] Turn Evaluator (백그라운드):
   - Intent: GENERATION
   - 평가: 명확성(95), 문제 적절성(90), 예시(85), 규칙(80), 문맥(75)
   - 점수: 85점

#### 턴 3: OPTIMIZATION
```
사용자: "이전에 말씀해주신 비트마스킹 개념을 사용하여 dp[current][visited] 형태로 구현했습니다. 하지만 visited 배열을 복사하는 부분이 메모리 낭비를 일으킵니다. 비트마스크 연산을 직접 사용하도록 최적화해주세요."
```

**처리**:
1. [2] Intent Analyzer: PASSED_HINT, LOGIC_HINT
2. [3] Writer LLM: 최적화된 코드 제공
3. [4] Turn Evaluator (백그라운드):
   - Intent: OPTIMIZATION, FOLLOW_UP
   - 평가: 명확성(90), 문제 적절성(95), 예시(80), 규칙(85), 문맥(95)
   - 점수: 89점

#### 코드 제출 후

**Holistic Flow Evaluation**:
- 문제 분해: 90점 (점진적 구성)
- 피드백 수용성: 95점 (이전 턴 힌트 반영)
- 주도성: 85점 (능동적 개선 제시)
- 전략적 탐색: 90점 (의도 전환)
- 고급 기법: 80점 (XML 태그 사용)
- **종합 점수**: 88점

**최종 점수 계산**:
- 프롬프트 점수: (88 + 84.3) / 2 = 86.15점
- 성능 점수: 85점
- 정확성 점수: 90점
- **총점**: 86.15 * 0.25 + 85 * 0.25 + 90 * 0.50 = **87.79점 (B등급)**

---

## 📚 참고 자료

- [프롬프트 엔지니어링 가이드](./Prompt_Engineering_Guide.md)
- [평가 시스템 개선 전략](./Evaluation_System_Improvement_Strategy.md)
- [토큰 추적 구현 가이드](./Token_Tracking_Implementation_Guide.md)


