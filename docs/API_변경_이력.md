# API 변경 이력

> **최종 통합일**: 2026-03-27 | **원본**: API_Changes_2024-12-07.md, Endpoint_Change_History.md

---

## 2026-05-20: BE 채점 result 콜백 (Issue #37 · BE PR #67)

- AI → BE: `POST /api/callbacks/ai/submissions/{submissionId}/result` (`status`, `testCases`, `score`)
- `analysis`: `RUNNING` / `FAILED`만; `DONE`은 result만
- BE PR #67: `DONE`+빈 TC → 400, runs replace, SSE `scoring_complete`
- 상세: [`docs/ai-callback-scoring.md`](ai-callback-scoring.md)

---

## 2025-12-06: 엔드포인트 및 Worker 라우팅 변경

API 엔드포인트 수정 및 FastAPI 측 구현 변경을 기록한 내용입니다.

### 1. `/api/chat/message` → `/api/session/{sessionId}/messages`

#### 변경 전

```python
POST /api/chat/message
{
  "session_id": "session_123",
  "exam_id": 1,
  "participant_id": 100,
  "spec_id": 10,
  "message": "문제 조건을 다시 설명해줘."
}
```

**문제점:**

- PostgreSQL에 메시지 저장 안 함
- 세션 생성 안 함
- Spring Boot가 별도로 `/api/chat/save-message` 호출 필요

#### 변경 후

```python
POST /api/session/{sessionId}/messages
{
  "role": "USER",
  "content": "문제 조건을 다시 설명해줘."
}
```

**개선 사항:**

- 세션 자동 생성/조회
- 사용자 메시지 즉시 저장
- AI 응답 저장
- Turn 번호 미리 계산 (UPDATE 제거)

---

### 2. `/api/chat/submit` → `/api/session/{sessionId}/submit`

#### 변경 전

```python
POST /api/chat/submit
{
  "session_id": "session_123",
  "exam_id": 1,
  "participant_id": 100,
  "spec_id": 10,
  "code": "def solve():\n    return 42",
  "lang": "python"
}
```

#### 변경 후

```python
POST /api/session/{sessionId}/submit
{
  "code": "def solve():\n    return 42",
  "lang": "python"
}
```

**개선 사항:**

- `sessionId`를 Path Parameter로 이동
- `examId`, `participantId`, `specId`는 세션에서 자동 조회
- Response에 Submission 정보 추가

> **참고**: 이후 Worker 중심 계획(아래 2024-12-07 절)에서는 Submit 경로·Request Body가 다시 `POST /api/session/submit` 등으로 재정의될 수 있습니다. 시기별로 명세를 구분해 적용하세요.

---

### 3. 세션 생성 API 추가

```python
POST /api/session/start
{
  "examId": 1,
  "participantId": 100,
  "specId": 20
}
```

**목적:**

- 세션 생성을 명시적으로 분리
- 세션 ID를 먼저 받아서 이후 API 호출에 사용

> **참고**: 2024-12-07 Worker 역할 분리 계획에서는 `POST /api/session/start` 제거·백엔드 전담이 포함됩니다(아래 절).

---

### 기술적 변경 사항 (구현)

#### `get_db_context` → `get_db` 변경

**파일**: `app/presentation/api/routes/chat.py`

**변경 내용:**

- `send_message` 함수: `get_db_context` → `get_db`
- `get_problem_info` 함수: `get_db_context` → `get_db`
- `save_chat_message` 함수: `get_db_context` → `get_db`

**이유:**

- FastAPI의 의존성 주입 패턴에 맞춤
- 세션 관리 자동화

#### 전역 예외 핸들러 추가

**파일**: `app/main.py`

**변경 내용:**

- 모든 예외를 캡처하여 로깅
- JSON 형식으로 에러 응답 반환
- 에러 타입, 메시지, 경로 정보 포함

#### 세션 생성 및 Turn 번호 계산 로직 추가

**파일**: `app/presentation/api/routes/chat.py`

**변경 내용:**

- `SessionRepository.get_or_create_session()` 호출
- `SessionRepository.get_next_turn_number()` 호출
- 사용자 메시지 즉시 저장
- AI 응답 저장

---

### 데이터 플로우 변경

#### 변경 전

```
[클라이언트] → POST /api/chat/message
  ↓
[LangGraph Worker]
  ↓
[Redis에만 State 저장]
  ↓
[응답 반환]
```

**PostgreSQL 저장:**

- 세션 생성 안 함
- 메시지 저장 안 함

#### 변경 후 (2025-12-06 기준)

```
[클라이언트] → POST /api/session/start
  ↓
[세션 생성 (PostgreSQL)]
  ↓
[클라이언트] → POST /api/session/{sessionId}/messages
  ↓
[1] 세션 조회 (PostgreSQL)
  ↓
[2] Turn 번호 계산 (PostgreSQL)
  ↓
[3] 사용자 메시지 저장 (PostgreSQL)
  ↓
[4] LangGraph 실행 (Redis)
  ↓
[5] AI 응답 저장 (PostgreSQL)
  ↓
[응답 반환]
```

**PostgreSQL 저장:**

- 세션 자동 생성
- 사용자 메시지 저장
- AI 응답 저장

---

### 핵심 개선 사항

#### 자동화

- 세션 자동 생성/조회
- 메시지 자동 저장
- Spring Boot는 한 번만 호출

#### 성능 최적화

- UPDATE 제거
- INSERT만 사용
- Turn 번호 미리 계산

#### 데이터 안정성

- 사용자 메시지 즉시 저장
- AI 응답 생성 실패해도 사용자 메시지 보존
- 각 메시지가 독립적으로 저장

#### RESTful 설계

- 리소스 중심 경로 구조
- Path Parameter 활용
- 명확한 엔드포인트 분리

---

### 추가된 함수: `SessionRepository.get_next_turn_number()`

```python
async def get_next_turn_number(self, session_id: int) -> int:
    """다음 턴 번호 계산"""
    from sqlalchemy import func
    
    query = select(func.max(PromptMessage.turn)).where(
        PromptMessage.session_id == session_id
    )
    result = await self.db.execute(query)
    max_turn = result.scalar_one_or_none()
    
    if max_turn is None:
        return 1  # 첫 턴
    
    return max_turn + 1  # 다음 턴
```

**장점:**

- UPDATE 없이 INSERT만 사용
- 성능 최적화

---

### Session ID 매핑

**매핑:**

- PostgreSQL: `session.id` (int, 예: `123`)
- Redis: `"session_{id}"` (str, 예: `"session_123"`)

**이유:**

- LangGraph는 문자열 session_id 사용
- PostgreSQL은 정수 ID 사용
- 자동 변환으로 일관성 유지

---

### 수정된 파일 목록

1. `app/presentation/api/routes/chat.py`
   - `get_db_context` → `get_db` 변경
   - 세션 생성 및 메시지 저장 로직 추가

2. `app/presentation/api/routes/session.py`
   - 새로운 세션 관리 엔드포인트 추가
   - 메시지 전송 엔드포인트 추가
   - 코드 제출 엔드포인트 추가

3. `app/main.py`
   - 전역 예외 핸들러 추가

4. `app/infrastructure/persistence/session.py`
   - `get_db()` 함수 확인 (정상)

---

### 테스트 체크리스트

1. 세션 자동 생성 확인
2. 사용자 메시지 저장 확인
3. AI 응답 저장 확인
4. Turn 번호 정확성 확인
5. Session ID 매핑 확인
6. 에러 처리 확인

---

## 2024-12-07: LangGraph Worker API 구조 변경 (계획)

LangGraph Worker의 API 구조 변경사항을 정리한 문서입니다. 백엔드(Spring Boot)와의 역할 분리 및 책임 명확화를 위한 변경입니다.

**통신 방식**: RESTful API만 사용 (WebSocket, SSE 미사용)

---

### 주요 변경사항

#### 1. 엔드포인트 변경

**기존(또는 당시 기준)**

- `POST /api/session/{sessionId}/messages` (Path Parameter)
- `POST /api/chat/message` (레거시)

**변경 후(계획)**

- `POST /api/chat/messages` (신규)
- 레거시 API 제거 예정

---

#### 2. Request Body 변경

**기존**

```json
{
  "role": "USER",
  "content": "문제 조건을 다시 설명해줘."
}
```

- Path Parameter로 `sessionId` 전달
- 세션 정보는 별도 조회

**변경 후**

```json
{
  "sessionId": 1,
  "examParticipantId": 9001,
  "turnId": 1,
  "role": "USER",
  "content": "이 문제를 DP로 푸는 힌트를 줘",
  "context": {
    "problemId": 1,
    "specVersion": 1
  }
}
```

**필드 설명:**

- `sessionId` (integer, 필수): 세션 ID
- `examParticipantId` (integer, 필수): 참가자 식별값
- `turnId` (integer, 필수): DB의 `prompt_messages.turn`
- `role` (string, 필수): 역할 (USER)
- `content` (string, 필수): 메시지 내용
- `context` (object, 필수): 문제 컨텍스트
  - `problemId` (integer): 문제 ID
  - `specVersion` (integer): 스펙 버전

---

#### 3. Response Body 변경

**기존**

```json
{
  "userMessage": {
    "id": 3001,
    "turn": 1,
    "role": "USER",
    "content": "...",
    "tokenCount": null
  },
  "aiMessage": {
    "id": 3002,
    "turn": 2,
    "role": "AI",
    "content": "...",
    "tokenCount": 120
  },
  "session": {
    "id": 2001,
    "totalTokens": 135
  }
}
```

**변경 후**

```json
{
  "aiMessage": {
    "session_id": 1,
    "turn": 2,
    "role": "AI",
    "content": "다음은 문제 조건입니다...",
    "tokenCount": 120,
    "totalToken": 135
  }
}
```

**변경 포인트:**

- `userMessage` 제거 (백엔드에서 저장하므로 불필요)
- `session` 필드 제거 (`aiMessage`에 통합)
- `aiMessage`에 `totalToken` 추가 (전체 누적 토큰)
- 메시지 ID 제거 (Worker가 저장하지 않으므로)

**필드 설명:**

- `session_id` (integer): 세션 ID
- `turn` (integer): AI 응답 턴 (이전 대화 Turn + 1)
- `role` (string): "AI"
- `content` (string): LLM이 생성한 응답
- `tokenCount` (integer): 현재 AI 응답 생성에 사용된 토큰
- `totalToken` (integer): 전체 누적 토큰 (세션 토큰)

---

#### 4. 역할 및 책임 변경

**기존 (Worker가 처리하던 것)**

- 세션 생성 (`get_or_create_session`)
- 사용자 메시지 저장 (PostgreSQL)
- AI 응답 생성 (LangGraph)
- AI 응답 저장 (PostgreSQL)
- 세션 토큰 업데이트 (PostgreSQL)
- 평가 결과 저장 (`prompt_evaluations`)

**변경 후 (Worker가 처리하는 것)**

- 세션 생성 (백엔드에서 처리)
- 사용자 메시지 저장 (백엔드에서 처리)
- AI 응답 생성 (LangGraph) — **핵심 역할**
- AI 응답 저장 (백엔드에서 처리)
- 세션 토큰 업데이트 (백엔드에서 처리)
- 평가 결과 저장 (`prompt_evaluations`) — **유지**

**결론**: Worker는 "AI 응답 생성기" 역할로 전환

---

#### 5. 처리 흐름 변경

**기존 흐름**

```
1. Request 수신
2. 세션 조회 또는 생성 (get_or_create_session)
3. 사용자 메시지 저장 (PostgreSQL)
4. LangGraph 실행 (AI 응답 생성)
5. AI 응답 저장 (PostgreSQL)
6. 세션 토큰 업데이트 (PostgreSQL)
7. Response 반환
```

**변경 후 흐름**

```
1. Request 수신 (sessionId 포함)
2. 세션 존재 확인 (get_session_by_id) - 없으면 404
3. LangGraph 실행 (AI 응답 생성)
4. 토큰 계산 (이전 토큰 + 현재 토큰)
5. Response 반환 (aiMessage만 반환)
```

---

#### 6. 코드 변경 포인트

**제거할 코드**

1. `POST /api/session/start` 엔드포인트
2. `get_or_create_session()` 메서드 호출
3. `MessageStorageService.save_message()` 호출
4. 세션 토큰 업데이트 로직 (`session.total_tokens` 업데이트)
5. 사용자 메시지 저장 로직
6. **WebSocket 엔드포인트** (`WS /api/chat/ws`)
7. **SSE (Server-Sent Events) 관련 코드**

**변경할 코드**

1. 세션 조회: `get_or_create_session()` → `get_session_by_id()` (존재 확인만)
2. 에러 처리: 세션이 없으면 404 반환
3. Response 구조: `aiMessage`만 반환, `totalToken` 포함

**유지할 코드**

1. LangGraph 실행: AI 응답 생성
2. 토큰 계산: 이전 토큰 조회 + 현재 토큰 계산
3. 평가 결과 저장: `prompt_evaluations` 테이블 저장 (제출 시)

---

#### 7. 토큰 계산 로직

```python
# 현재 AI 응답 토큰
current_tokens = chat_tokens.get("total_tokens", 0)

# 이전 누적 토큰 (Redis 또는 DB에서 조회)
previous_tokens = await get_previous_tokens(session_id)

# 전체 누적 토큰
total_tokens = previous_tokens + current_tokens

# Response에 포함
ai_message = {
    "session_id": session_id,
    "turn": ai_turn,  # 이전 Turn + 1
    "role": "AI",
    "content": ai_response,
    "tokenCount": current_tokens,    # 현재 Turn 토큰
    "totalToken": total_tokens       # 전체 누적 토큰
}
```

---

#### 8. Turn 계산 로직

```python
# Redis에서 마지막 턴 조회 또는 Request의 turnId 사용
last_turn = await redis_client.get_last_turn(session_id)
# 또는
last_turn = request.turnId  # 사용자 턴

# AI 응답 턴 = 사용자 턴 + 1
ai_turn = last_turn + 1
```

---

### 변경 예정 사항 (Submit API 등)

#### Submit API 변경

**엔드포인트 변경**

- 기존: `POST /api/chat/submit` 또는 `POST /api/session/{sessionId}/submit`
- 변경 후: `POST /api/session/submit`

**Request Body**

```json
{
  "problemId": 1,
  "specVersion": 1,
  "examParticipantId": 9001,
  "finalCode": "def solve(): print('hello')",
  "language": "python3.11",
  "submissionId": 88001
}
```

**필드 설명:**

- `problemId` (integer, 필수): 문제 ID
- `specVersion` (integer, 필수): 스펙 버전
- `examParticipantId` (integer, 필수): 참가자 식별값
- `finalCode` (string, 필수): 제출 코드
- `language` (string, 필수): 프로그래밍 언어 (예: python3.11)
- `submissionId` (integer, 필수): 제출 ID (백엔드에서 생성)

**Response Body**

```json
{
  "submissionId": 88001,
  "status": "successed"
}
```

**필드 설명:**

- `submissionId` (integer): 제출 ID
- `status` (string): 처리 상태 (`successed` 또는 `failed`)

**처리 방식**

- **비동기 처리**: 백엔드 서버를 잡아두지 않고 비동기로 처리
- **DB 저장**: 평가 완료 후 DB에 저장
- **완료 메시지**: 저장 완료 후 Response 반환
- **실패 처리**: 실패 시 `status: "failed"` 반환

**평가 결과 저장**

1. **4번 Node (Turn Evaluation)**: `prompt_evaluations` 테이블에 저장
   - `evaluation_type`: `TURN_EVAL` (ENUM)
   - `turn`: 평가 대상 턴 번호
   - `details`: 평가 상세 정보 (JSONB)

2. **6a번 Node (Holistic Flow)**: `prompt_evaluations` 테이블에 저장
   - `evaluation_type`: `HOLISTIC_FLOW` (ENUM)
   - `turn`: NULL (세션 전체 평가)
   - `details`: 평가 상세 정보 (JSONB)

3. **최종 점수**: `scores` 테이블에 저장
   - `submission_id`: 제출 ID
   - `prompt_score`: 프롬프트 점수
   - `perf_score`: 성능 점수
   - `correctness_score`: 정확성 점수
   - `total_score`: 총점
   - `rubric_json`: 상세 평가 내역

#### 레거시 API 제거 (계획)

- `POST /api/chat/message` 제거 예정
- `POST /api/session/{sessionId}/messages` 제거 예정
- 마이그레이션 완료 후 제거

---

### 주의사항 (2024-12-07 계획 기준)

1. **세션 존재 확인 필수**: Request의 `sessionId`로 세션이 존재하는지 확인
2. **에러 처리**: 세션이 없으면 404 반환
3. **토큰 계산**: 이전 토큰을 정확히 조회해야 함
4. **Turn 계산**: 이전 대화의 Turn을 정확히 계산해야 함

---

### 변경 이력 (원본 API_Changes_2024-12-07)

| 날짜 | 변경사항 |
|------|---------|
| 2024-12-07 | API 구조 변경 계획 수립 |
| 2024-12-07 | Request/Response 구조 변경 결정 |
| 2024-12-07 | 역할 및 책임 분리 결정 |
| 2024-12-07 | Submit API 변경사항 추가 |
| 2024-12-07 | WebSocket/SSE 미사용 결정 (RESTful API만 사용) |

---

## 관련 문서

- [API Specification](./API_Specification.md) — 전체 API 명세
- [Database Changes Summary](./Database_Changes_Summary.md) — DB 변경사항
- [Message Storage Implementation](./Message_Storage_Implementation.md) — 메시지 저장 구현 내용
