# 전체 Flow Test 시나리오

## 📋 개요

전체 Flow Test는 **Chat API**와 **Submit API**를 연속적으로 실행하여 전체 평가 프로세스를 검증합니다.

---

## 🎯 테스트 목표

1. **Chat API**: 일반 대화 (평가 없음, AI 응답만 생성)
2. **Submit API**: 코드 제출 및 전체 평가 (4번, 6번 노드 실행)
3. **평가 결과 확인**: DB에 저장된 평가 결과 검증

---

## 📊 전체 Flow 시나리오

### Phase 1: 테스트 데이터 준비

**목적**: 테스트에 필요한 DB 데이터 생성

**실행 스크립트**: `test_scripts/setup_submit_test_data.py`

**생성 데이터:**
- Exam (ID: 1000)
- Participant (ID: 1000)
- Problem (ID: 1 - 외판원 순회)
- ProblemSpec (spec_id: 10)
- ExamParticipant (ID: 1000)
- PromptSession (ID: 1000, `ended_at = NULL` - 진행 중인 세션)
- Submission (ID: 1000, status: 'QUEUED')

**실행 명령:**
```bash
uv run python test_scripts/setup_submit_test_data.py
```

---

### Phase 2: Chat API - 대화 생성 (여러 턴)

**목적**: 일반 채팅으로 대화 히스토리 생성 (평가 없음)

**API**: `POST /api/chat/messages`

**시나리오:**

#### Turn 1: 첫 번째 질문
```json
{
  "sessionId": 1000,
  "examParticipantId": 1000,
  "turnId": 1,
  "role": "USER",
  "content": "비트마스킹이 뭔가요?",
  "context": {
    "problemId": 1,
    "specVersion": 1
  }
}
```

**예상 결과:**
- AI 응답 생성 (Writer LLM)
- State의 `messages`에 사용자/AI 메시지 추가
- Redis에 State 저장
- **평가 실행 안 함** (일반 채팅)

**Response:**
```json
{
  "aiMessage": {
    "session_id": 1000,
    "turn": 2,
    "role": "AI",
    "content": "비트마스킹은...",
    "tokenCount": 150,
    "totalToken": 150
  }
}
```

#### Turn 2: 두 번째 질문
```json
{
  "sessionId": 1000,
  "examParticipantId": 1000,
  "turnId": 2,
  "role": "USER",
  "content": "DP로 푸는 방법을 알려주세요",
  "context": {
    "problemId": 1,
    "specVersion": 1
  }
}
```

**예상 결과:**
- AI 응답 생성
- State의 `messages`에 추가 (총 4개 메시지: Turn 1 user/ai, Turn 2 user/ai)
- Redis에 State 저장
- **평가 실행 안 함**

**Response:**
```json
{
  "aiMessage": {
    "session_id": 1000,
    "turn": 4,
    "role": "AI",
    "content": "DP로 푸는 방법은...",
    "tokenCount": 200,
    "totalToken": 350  // 이전 토큰(150) + 현재 토큰(200)
  }
}
```

#### Turn 3: 세 번째 질문 (선택)
```json
{
  "sessionId": 1000,
  "examParticipantId": 1000,
  "turnId": 3,
  "role": "USER",
  "content": "시간 복잡도는 어떻게 되나요?",
  "context": {
    "problemId": 1,
    "specVersion": 1
  }
}
```

**예상 결과:**
- AI 응답 생성
- State의 `messages`에 추가 (총 6개 메시지)
- Redis에 State 저장

---

### Phase 3: Submit API - 코드 제출 및 평가

**목적**: 코드 제출 후 전체 평가 실행

**API**: `POST /api/session/submit`

**시나리오:**

#### Submit 요청
```json
{
  "problemId": 1,
  "specVersion": 1,
  "examParticipantId": 1000,
  "finalCode": "import sys\ninput = sys.stdin.readline\n\ndef tsp(current, visited):\n    ...",
  "language": "python3.11",
  "submissionId": 1000
}
```

**예상 결과:**

1. **세션 조회**
   - `examParticipantId`로 `exam_participants` 조회
   - 진행 중인 세션 조회 (`ended_at = NULL`)

2. **LangGraph 실행 시작**
   - Redis에서 State 로드
   - State 역직렬화 (dict → LangChain BaseMessage 객체)

3. **4번 노드: Eval Turn Guard**
   - **State의 messages에서 모든 턴 추출** (1 ~ current_turn-1)
   - 각 턴에 대해 Eval Turn SubGraph 실행:
     - Intent Analysis
     - 의도별 평가 (Rule Setting, Generation, Optimization 등)
     - Answer Summary
   - **평가 결과 저장:**
     - Redis: `turn_logs:{session_id}:{turn}`
     - PostgreSQL: `prompt_evaluations` (evaluation_type: 'TURN_EVAL')
   - State에 `turn_scores` 반환

4. **6a번 노드: Holistic Flow Evaluation**
   - **Redis에서 turn_logs 조회**: `get_all_turn_logs(session_id)`
   - 모든 턴의 평가 결과 수집
   - LLM으로 전체 플로우 평가 (Chaining 전략 분석)
   - **평가 결과 저장:**
     - State: `holistic_flow_score`, `holistic_flow_analysis`
     - PostgreSQL: `prompt_evaluations` (evaluation_type: 'HOLISTIC_FLOW')

5. **6b번 노드: Aggregate Turn Scores**
   - State의 `turn_scores` 집계
   - 평균 턴 점수 계산

6. **6c번 노드: Code Execution (Judge0)**
   - 코드 정확성 평가 (테스트 케이스 실행)
   - 코드 성능 평가 (실행 시간, 메모리 사용량)
   - Judge0 결과에서 `execution_time`, `memory_used_mb` 추출

7. **7번 노드: Final Score Aggregation**
   - 최종 점수 계산:
     - Prompt: 40% (턴 점수 + 플로우 점수)
     - Correctness: 30% (테스트 케이스 통과 여부)
     - Performance: 30% (실행 시간 + 메모리)
   - 등급 산출 (A, B, C, D, F)
   - **점수 저장:**
     - PostgreSQL: `scores` 테이블
     - `rubric_json`에 상세 정보 포함 (execution_time, memory_used_mb 포함)

8. **Response 반환**
   - 평가 완료 후 Response 반환 (동기 처리)
   - `status: "successed"`

**Response:**
```json
{
  "submissionId": 1000,
  "status": "successed"
}
```

---

### Phase 4: 결과 확인

**목적**: DB에 저장된 평가 결과 검증

**실행 스크립트**: `test_scripts/check_submit_result.py`

**확인 항목:**

1. **Submission 상태**
   - `submissions` 테이블
   - `status` 확인 (SUCCESSED, FAILED 등)
   - `code_inline` 확인

2. **Scores**
   - `scores` 테이블
   - `prompt_score`, `perf_score`, `correctness_score`, `total_score`
   - `rubric_json` 확인:
     - `grade` (A, B, C, D, F)
     - `performance_details.execution_time`
     - `performance_details.memory_used_mb`

3. **Turn Evaluations**
   - `prompt_evaluations` 테이블
   - `evaluation_type = 'TURN_EVAL'`
   - 각 턴별 점수 확인

4. **Holistic Flow Evaluation**
   - `prompt_evaluations` 테이블
   - `evaluation_type = 'HOLISTIC_FLOW'`
   - 전체 플로우 점수 확인

5. **Session 상태**
   - `prompt_sessions` 테이블
   - `ended_at` 확인 (제출 후 종료 여부)

**실행 명령:**
```bash
uv run python test_scripts/check_submit_result.py
```

---

## 🔄 전체 Flow 다이어그램

```
[Phase 1] 테스트 데이터 준비
    ↓
[Phase 2] Chat API (Turn 1)
    → Writer LLM 실행
    → State에 메시지 추가
    → Redis에 State 저장
    → 평가 없음
    ↓
[Phase 2] Chat API (Turn 2)
    → Writer LLM 실행
    → State에 메시지 추가
    → Redis에 State 저장
    → 평가 없음
    ↓
[Phase 2] Chat API (Turn 3) - 선택
    → Writer LLM 실행
    → State에 메시지 추가
    → Redis에 State 저장
    → 평가 없음
    ↓
[Phase 3] Submit API
    → Redis에서 State 로드
    → LangGraph 실행 시작
        ↓
    [4번 노드] Eval Turn Guard
        → State의 messages에서 턴 추출
        → 각 턴 평가 (Eval Turn SubGraph)
        → Redis turn_logs 저장
        → PostgreSQL prompt_evaluations 저장
        ↓
    [6a번 노드] Holistic Flow Evaluation
        → Redis turn_logs 조회
        → 전체 플로우 평가
        → PostgreSQL prompt_evaluations 저장
        ↓
    [6b번 노드] Aggregate Turn Scores
        → State의 turn_scores 집계
        ↓
    [6c번 노드] Code Execution
        → Judge0 실행
        → 정확성/성능 평가
        ↓
    [7번 노드] Final Score Aggregation
        → 최종 점수 계산
        → PostgreSQL scores 저장
        ↓
    → Response 반환
    ↓
[Phase 4] 결과 확인
    → DB에서 평가 결과 검증
```

---

## 🚀 실행 순서

### 1. 서버 및 인프라 실행

```bash
# 터미널 1: PostgreSQL & Redis
docker-compose -f docker-compose.dev.yml up -d

# 터미널 2: FastAPI 서버
uv run scripts/run_dev.py

# 터미널 3: Judge0 Worker (선택, Judge0 사용 시)
uv run python -m app.application.workers.judge_worker
```

### 2. 테스트 데이터 준비

```bash
uv run python test_scripts/setup_submit_test_data.py
```

### 3. Chat API 테스트 (여러 턴)

```bash
# 수동으로 API 호출하거나
# test_full_flow_tsp.py 실행
uv run python test_full_flow_tsp.py
```

또는 수동으로:

```bash
# Turn 1
curl -X POST http://localhost:8000/api/chat/messages \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": 1000,
    "examParticipantId": 1000,
    "turnId": 1,
    "role": "USER",
    "content": "비트마스킹이 뭔가요?",
    "context": {"problemId": 1, "specVersion": 1}
  }'

# Turn 2
curl -X POST http://localhost:8000/api/chat/messages \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": 1000,
    "examParticipantId": 1000,
    "turnId": 2,
    "role": "USER",
    "content": "DP로 푸는 방법을 알려주세요",
    "context": {"problemId": 1, "specVersion": 1}
  }'
```

### 4. Submit API 테스트

```bash
uv run python test_submit_tsp.py
```

### 5. 결과 확인

```bash
uv run python test_scripts/check_submit_result.py
```

---

## ✅ 검증 체크리스트

### Chat API 검증
- [ ] 각 턴에서 AI 응답 생성 확인
- [ ] `tokenCount`와 `totalToken` 누적 확인
- [ ] State의 `messages`에 메시지 추가 확인
- [ ] Redis에 State 저장 확인
- [ ] 평가 실행 안 함 확인 (일반 채팅)

### Submit API 검증
- [ ] 4번 노드 실행 확인 (서버 로그)
- [ ] 각 턴 평가 완료 확인
- [ ] Redis turn_logs 저장 확인
- [ ] PostgreSQL prompt_evaluations 저장 확인 (TURN_EVAL)
- [ ] 6a번 노드 실행 확인
- [ ] Holistic Flow 평가 완료 확인
- [ ] PostgreSQL prompt_evaluations 저장 확인 (HOLISTIC_FLOW)
- [ ] 6c번 노드 실행 확인 (Judge0)
- [ ] 정확성/성능 평가 완료 확인
- [ ] 7번 노드 실행 확인
- [ ] 최종 점수 계산 확인
- [ ] PostgreSQL scores 저장 확인
- [ ] `rubric_json`에 execution_time, memory_used_mb 포함 확인

### 데이터 검증
- [ ] `submissions` 테이블에 제출 정보 저장 확인
- [ ] `scores` 테이블에 점수 저장 확인
- [ ] `prompt_evaluations` 테이블에 평가 결과 저장 확인
- [ ] `prompt_sessions` 테이블의 `ended_at` 확인

---

## ⚠️ 주의 사항

1. **서버 실행 필수**
   - FastAPI 서버가 실행 중이어야 함
   - Judge0 Worker는 선택 (Judge0 사용 시)

2. **DB 초기화**
   - `scripts/init-db.sql` 실행 필요
   - ENUM 타입 생성 확인

3. **Redis 연결**
   - Redis 서버 실행 확인
   - State 저장/로드 확인

4. **타임아웃**
   - Submit API는 평가 완료까지 대기 (최대 5분)
   - LLM 응답 시간에 따라 다를 수 있음

5. **테스트 데이터**
   - SessionId: 1000
   - SubmissionId: 1000
   - ExamParticipantId: 1000
   - ProblemId: 1 (외판원 순회)

---

## 📝 예상 실행 시간

- **Phase 1 (데이터 준비)**: ~1초
- **Phase 2 (Chat API, 3턴)**: ~30-60초 (LLM 응답 시간)
- **Phase 3 (Submit API)**: ~2-5분 (평가 완료까지)
- **Phase 4 (결과 확인)**: ~1초

**총 예상 시간**: 약 3-6분

