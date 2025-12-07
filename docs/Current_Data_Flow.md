# 현재 데이터 흐름 및 평가 프로세스

## 📋 개요

현재 시스템의 데이터 흐름과 평가 프로세스를 정리합니다.

---

## 🔄 일반 채팅 (Chat) 흐름

### 1. API 호출
```
POST /api/chat/messages
```

### 2. 처리 과정

#### 2.1. 세션 확인
- PostgreSQL `prompt_sessions` 테이블에서 세션 조회
- `exam_id`, `participant_id`로 진행 중인 세션 확인

#### 2.2. LangGraph 실행
- `eval_service.process_message()` 호출
- **Redis에서 기존 State 로드**: `state_repo.get_state(session_id)` → Redis에서 State 로드
- **LangGraph에 State 전달**: `self.graph.ainvoke(state, config)`
  - ⚠️ 중요: LangGraph 실행 중에는 State가 **메모리**에 있음 (MemorySaver 사용)
  - 각 노드에서 `state.get("messages")`는 **메모리의 LangGraph State 객체**에서 가져옴
- LangGraph 실행:
  - **1번 노드**: Intent Analyzer (의도 분석)
  - **3번 노드**: Writer LLM (AI 응답 생성)
- **LangGraph 실행 완료 후**: `state_repo.save_state()` → Redis에 저장

#### 2.3. 메시지 저장 (Redis만)
- **Writer 노드**에서 `messages` 배열에 메시지 추가:
  ```python
  new_messages = [
      {
          "turn": current_turn,
          "role": "user",
          "content": human_message,
          "timestamp": datetime.utcnow().isoformat()
      },
      {
          "turn": current_turn,
          "role": "assistant", 
          "content": ai_content,
          "timestamp": datetime.utcnow().isoformat()
      }
  ]
  ```
- **StateRepository.save_state()** 호출
- **Redis에 저장**: `graph_state:{session_id}`
  - 키: `graph_state:session_1000`
  - 값: JSON (messages, current_turn, problem_context 등)
  - TTL: 기본 3600초 (1시간)

#### 2.4. 턴 매핑 저장 (Redis)
- **Writer 노드**에서 턴-메시지 인덱스 매핑 저장
- Redis 키: `turn_mapping:{session_id}`
  - 값: `{"1": {"start_msg_idx": 0, "end_msg_idx": 1}, ...}`

#### 2.5. 토큰 저장 (Redis)
- 현재 턴 토큰 계산: `tokenCount = user_tokens + ai_tokens`
- 전체 누적 토큰: `totalToken = previous_tokens + tokenCount`
- Redis 키: `session_token:{session_id}`

### 3. 저장 위치 요약

| 데이터 | 저장 위치 | 설명 |
|--------|----------|------|
| 메시지 (대화 내용) | **Redis만** | `graph_state:{session_id}` → `messages` 배열 |
| 턴 매핑 | **Redis만** | `turn_mapping:{session_id}` |
| 토큰 사용량 | **Redis만** | `session_token:{session_id}` |
| 평가 결과 | **없음** | 일반 채팅에서는 평가하지 않음 |

---

## 📤 제출 (Submit) 흐름

### 1. API 호출
```
POST /api/session/submit
```

### 2. 처리 과정

#### 2.1. 세션 확인
- PostgreSQL `prompt_sessions` 테이블에서 세션 조회
- `exam_id`, `participant_id`로 진행 중인 세션 확인

#### 2.2. LangGraph 실행
- `eval_service.submit_code()` 호출
- **Redis에서 기존 State 로드**: `state_repo.get_state(session_id)` → Redis에서 State 로드
- State에 제출 정보 추가:
  - `is_submitted: True`
  - `code_content: "..."`
  - `lang: "python3.11"`
- **LangGraph에 State 전달**: `self.graph.ainvoke(state, config)`
  - ⚠️ 중요: LangGraph 실행 중에는 State가 **메모리**에 있음 (MemorySaver 사용)
  - 각 노드에서 `state.get("messages")`는 **메모리의 LangGraph State 객체**에서 가져옴
- **LangGraph 실행 완료 후**: `state_repo.save_state()` → Redis에 저장

#### 2.3. 4번 노드: Eval Turn Guard (턴별 평가)

**데이터 소스:**
- **LangGraph State** (메모리)에서 `messages` 배열 추출
  - ⚠️ 중요: LangGraph 실행 중에는 State가 메모리에 있음
  - 초기 State는 Redis에서 로드되었지만, 실행 중에는 메모리 State 객체 사용
  - **Redis turn_mapping 조회하지 않음** - State의 messages에서 turn 정보로 직접 검색

**평가 과정:**
1. LangGraph State의 `messages`에서 모든 턴 추출 (1 ~ current_turn-1)
2. 각 턴에 대해 **Eval Turn SubGraph** 실행:
   - 4.0 Intent Analysis (의도 분석)
   - 4.R/G/O/D/T/H/F (의도별 평가)
   - 4.X Answer Summary (답변 요약)
   - 4.4 Turn Log Aggregation (턴 로그 집계)

**저장 위치:**
- **Redis**: `turn_logs:{session_id}:{turn}`
  - 키: `turn_logs:session_1000:1`
  - 값: JSON (turn_number, prompt_evaluation_details, llm_answer_summary 등)
- **PostgreSQL**: `prompt_evaluations` 테이블
  - `evaluation_type: 'TURN_EVAL'`
  - `turn: 1, 2, 3, ...`
  - `details: JSONB` (score, analysis 등)

#### 2.4. 6a번 노드: Holistic Flow Evaluation (전체 플로우 평가)

**데이터 소스:**
- **LangGraph State** (메모리)에서 `messages` 배열 추출
  - ⚠️ 중요: LangGraph 실행 중에는 State가 메모리에 있음
- **Redis Turn Logs**에서 모든 턴 평가 결과 조회: `turn_logs:{session_id}:*` (Redis에서 조회)

**평가 과정:**
1. LangGraph State의 `messages`에서 전체 대화 추출
2. 모든 턴의 평가 결과 수집 (Redis turn_logs)
3. LLM으로 전체 플로우 평가:
   - 문제 분해 (Problem Decomposition)
   - 피드백 수용성 (Feedback Integration)
   - 주도성 및 오류 수정 (Proactiveness)
   - 전략적 탐색 (Strategic Exploration)
   - 고급 프롬프트 기법 활용 (Advanced Techniques Bonus)

**저장 위치:**
- **Redis**: State의 `holistic_flow_score`, `holistic_flow_analysis` 업데이트
- **PostgreSQL**: `prompt_evaluations` 테이블
  - `evaluation_type: 'HOLISTIC_FLOW'`
  - `turn: NULL` (전체 평가)
  - `details: JSONB` (score, analysis 등)

#### 2.5. 6b번 노드: Aggregate Turn Scores (턴 점수 집계)

**데이터 소스:**
- **Redis State**에서 `turn_scores` 추출
- 또는 **Redis Turn Logs**에서 점수 추출

**처리:**
- 모든 턴 점수의 평균 계산
- State의 `aggregate_turn_score` 업데이트

#### 2.6. 6c번 노드: Eval Code Execution (코드 실행 평가)

**데이터 소스:**
- State의 `code_content` (제출 코드)
- State의 `problem_context` (테스트 케이스, 제한 시간 등)

**평가 과정:**
1. **Correctness 평가**:
   - Judge0로 코드 실행
   - 테스트 케이스 통과 여부 확인
   - **Judge0 결과에서 `execution_time`, `memory_used` 추출**
2. **Performance 평가**:
   - Judge0로 코드 실행 (성능 측정)
   - 실행 시간과 메모리 사용량 확인
   - 합격 기준과 비교하여 점수 계산

**저장 위치:**
- State의 `code_correctness_score`, `code_performance_score` 업데이트
- State의 `execution_time`, `memory_used_mb` 업데이트

#### 2.7. 7번 노드: Aggregate Final Scores (최종 점수 집계)

**데이터 소스:**
- State의 모든 점수:
  - `holistic_flow_score`
  - `aggregate_turn_score`
  - `code_correctness_score`
  - `code_performance_score`
  - `execution_time`
  - `memory_used_mb`

**처리:**
- 가중치 적용:
  - Prompt: 40% (턴 점수 + 플로우 점수)
  - Correctness: 30%
  - Performance: 30%
- 최종 점수 계산 및 등급 부여

**저장 위치:**
- **PostgreSQL**: `scores` 테이블
  - `submission_id`
  - `prompt_score`, `perf_score`, `correctness_score`, `total_score`
  - `rubric_json: JSONB` (모든 상세 정보 포함)
    - `execution_time`: Judge0 결과에서 추출
    - `memory_used_mb`: Judge0 결과에서 추출
    - `performance_details`: `{execution_time, memory_used_mb, skip_performance, skip_reason}`
    - `correctness_details`: `{test_cases_passed, test_cases_total, pass_rate}`
- **PostgreSQL**: `submissions` 테이블
  - `status: 'DONE'` 업데이트
- **PostgreSQL**: `prompt_sessions` 테이블
  - `ended_at` 설정 (세션 종료)

---

## 📊 데이터 저장 위치 요약

### Redis 저장 데이터

| 키 패턴 | 데이터 | 설명 |
|---------|--------|------|
| `graph_state:{session_id}` | State 전체 | messages, current_turn, problem_context 등 |
| `turn_mapping:{session_id}` | 턴-메시지 매핑 | `{"1": {"start_msg_idx": 0, "end_msg_idx": 1}}` |
| `turn_logs:{session_id}:{turn}` | 턴 평가 로그 | 각 턴의 상세 평가 결과 |
| `session_token:{session_id}` | 토큰 사용량 | 전체 누적 토큰 |

### PostgreSQL 저장 데이터

| 테이블 | 데이터 | 저장 시점 |
|--------|--------|----------|
| `prompt_sessions` | 세션 정보 | 세션 생성 시 (백엔드) |
| `prompt_messages` | **저장하지 않음** | 백엔드에서 저장 |
| `prompt_evaluations` | 평가 결과 | 제출 시 (4번, 6a 노드) |
| `submissions` | 제출 정보 | 제출 시 (백엔드) |
| `scores` | 최종 점수 | 제출 시 (7번 노드) |

---

## ⚠️ 중요 사항

### 1. 메시지 저장
- **일반 채팅**: 메시지는 **Redis에만 저장** (PostgreSQL에는 저장하지 않음)
- **제출 시**: 메시지는 평가에 사용되지만, PostgreSQL에는 저장하지 않음
- 메시지 저장은 **백엔드에서 처리** (Worker는 AI 응답 생성만 담당)

### 2. 평가 데이터 소스
- **4번 노드 (턴 평가)**: **LangGraph State** (메모리)의 `messages` 배열 사용
  - 초기 State는 Redis에서 로드되지만, 실행 중에는 메모리 State 객체 사용
- **6a번 노드 (플로우 평가)**: **LangGraph State** (메모리)의 `messages` 배열 + Redis Turn Logs 사용
- **6c번 노드 (코드 실행)**: LangGraph State의 `code_content` 사용

### 3. Judge0 결과 포함
- **Correctness 평가** 결과에서 `execution_time`, `memory_used` 추출
- **Performance 평가** 결과에서 `execution_time`, `memory_used` 추출
- Performance 평가가 실패하면 Correctness 결과에서 가져온 값 사용
- `scores` 테이블의 `rubric_json`에 `performance_details`로 포함

---

## 🔍 확인 방법

### Redis 데이터 확인
```python
# State 확인
state = await redis_client.get_graph_state("session_1000")
messages = state.get("messages", [])

# 턴 매핑 확인
turn_mapping = await redis_client.get_turn_mapping("session_1000")

# 턴 로그 확인
turn_logs = await redis_client.get_all_turn_logs("session_1000")
```

### PostgreSQL 데이터 확인
```sql
-- 평가 결과 확인
SELECT * FROM prompt_evaluations 
WHERE session_id = 1000 
ORDER BY turn, evaluation_type;

-- 최종 점수 확인
SELECT submission_id, total_score, rubric_json 
FROM scores 
WHERE submission_id = 1000;
```

