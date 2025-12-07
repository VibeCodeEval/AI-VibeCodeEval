# API 변경사항 (2024-12-07)

## 📋 개요

LangGraph Worker의 API 구조 변경사항을 정리한 문서입니다.
백엔드(Spring Boot)와의 역할 분리 및 책임 명확화를 위한 변경입니다.

**통신 방식**: RESTful API만 사용 (WebSocket, SSE 미사용)

---

## 🔄 주요 변경사항

### 1. 엔드포인트 변경

#### 기존
- `POST /api/session/{sessionId}/messages` (Path Parameter)
- `POST /api/chat/message` (레거시)

#### 변경 후
- `POST /api/chat/messages` (신규)
- 레거시 API 제거 예정

---

### 2. Request Body 변경

#### 기존
```json
{
  "role": "USER",
  "content": "문제 조건을 다시 설명해줘."
}
```
- Path Parameter로 `sessionId` 전달
- 세션 정보는 별도 조회

#### 변경 후
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

**필드 설명**:
- `sessionId` (integer, 필수): 세션 ID
- `examParticipantId` (integer, 필수): 참가자 식별값
- `turnId` (integer, 필수): DB의 `prompt_messages.turn`
- `role` (string, 필수): 역할 (USER)
- `content` (string, 필수): 메시지 내용
- `context` (object, 필수): 문제 컨텍스트
  - `problemId` (integer): 문제 ID
  - `specVersion` (integer): 스펙 버전

---

### 3. Response Body 변경

#### 기존
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

#### 변경 후
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

**변경 포인트**:
- `userMessage` 제거 (백엔드에서 저장하므로 불필요)
- `session` 필드 제거 (`aiMessage`에 통합)
- `aiMessage`에 `totalToken` 추가 (전체 누적 토큰)
- 메시지 ID 제거 (Worker가 저장하지 않으므로)

**필드 설명**:
- `session_id` (integer): 세션 ID
- `turn` (integer): AI 응답 턴 (이전 대화 Turn + 1)
- `role` (string): "AI"
- `content` (string): LLM이 생성한 응답
- `tokenCount` (integer): 현재 AI 응답 생성에 사용된 토큰
- `totalToken` (integer): 전체 누적 토큰 (세션 토큰)

---

### 4. 역할 및 책임 변경

#### 기존 (Worker가 처리하던 것)
- ✅ 세션 생성 (`get_or_create_session`)
- ✅ 사용자 메시지 저장 (PostgreSQL)
- ✅ AI 응답 생성 (LangGraph)
- ✅ AI 응답 저장 (PostgreSQL)
- ✅ 세션 토큰 업데이트 (PostgreSQL)
- ✅ 평가 결과 저장 (`prompt_evaluations`)

#### 변경 후 (Worker가 처리하는 것)
- ❌ 세션 생성 (백엔드에서 처리)
- ❌ 사용자 메시지 저장 (백엔드에서 처리)
- ✅ AI 응답 생성 (LangGraph) - **핵심 역할**
- ❌ AI 응답 저장 (백엔드에서 처리)
- ❌ 세션 토큰 업데이트 (백엔드에서 처리)
- ✅ 평가 결과 저장 (`prompt_evaluations`) - **유지**

**결론**: Worker는 "AI 응답 생성기" 역할로 전환

---

### 5. 처리 흐름 변경

#### 기존 흐름
```
1. Request 수신
2. 세션 조회 또는 생성 (get_or_create_session)
3. 사용자 메시지 저장 (PostgreSQL)
4. LangGraph 실행 (AI 응답 생성)
5. AI 응답 저장 (PostgreSQL)
6. 세션 토큰 업데이트 (PostgreSQL)
7. Response 반환
```

#### 변경 후 흐름
```
1. Request 수신 (sessionId 포함)
2. 세션 존재 확인 (get_session_by_id) - 없으면 404
3. LangGraph 실행 (AI 응답 생성)
4. 토큰 계산 (이전 토큰 + 현재 토큰)
5. Response 반환 (aiMessage만 반환)
```

---

### 6. 코드 변경 포인트

#### 제거할 코드
1. `POST /api/session/start` 엔드포인트
2. `get_or_create_session()` 메서드 호출
3. `MessageStorageService.save_message()` 호출
4. 세션 토큰 업데이트 로직 (`session.total_tokens` 업데이트)
5. 사용자 메시지 저장 로직
6. **WebSocket 엔드포인트** (`WS /api/chat/ws`)
7. **SSE (Server-Sent Events) 관련 코드**

#### 변경할 코드
1. 세션 조회: `get_or_create_session()` → `get_session_by_id()` (존재 확인만)
2. 에러 처리: 세션이 없으면 404 반환
3. Response 구조: `aiMessage`만 반환, `totalToken` 포함

#### 유지할 코드
1. LangGraph 실행: AI 응답 생성
2. 토큰 계산: 이전 토큰 조회 + 현재 토큰 계산
3. 평가 결과 저장: `prompt_evaluations` 테이블 저장 (제출 시)

---

### 7. 토큰 계산 로직

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

### 8. Turn 계산 로직

```python
# Redis에서 마지막 턴 조회 또는 Request의 turnId 사용
last_turn = await redis_client.get_last_turn(session_id)
# 또는
last_turn = request.turnId  # 사용자 턴

# AI 응답 턴 = 사용자 턴 + 1
ai_turn = last_turn + 1
```

---

## 📝 변경 예정 사항

### 1. Submit API 변경

#### 엔드포인트 변경
- 기존: `POST /api/chat/submit` 또는 `POST /api/session/{sessionId}/submit`
- 변경 후: `POST /api/session/submit`

#### Request Body
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

**필드 설명**:
- `problemId` (integer, 필수): 문제 ID
- `specVersion` (integer, 필수): 스펙 버전
- `examParticipantId` (integer, 필수): 참가자 식별값
- `finalCode` (string, 필수): 제출 코드
- `language` (string, 필수): 프로그래밍 언어 (예: python3.11)
- `submissionId` (integer, 필수): 제출 ID (백엔드에서 생성)

#### Response Body
```json
{
  "submissionId": 88001,
  "status": "successed"
}
```

**필드 설명**:
- `submissionId` (integer): 제출 ID
- `status` (string): 처리 상태 (`successed` 또는 `failed`)

#### 처리 방식
- **비동기 처리**: 백엔드 서버를 잡아두지 않고 비동기로 처리
- **DB 저장**: 평가 완료 후 DB에 저장
- **완료 메시지**: 저장 완료 후 Response 반환
- **실패 처리**: 실패 시 `status: "failed"` 반환

#### 평가 결과 저장
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

### 2. 레거시 API 제거
- `POST /api/chat/message` 제거 예정
- `POST /api/session/{sessionId}/messages` 제거 예정
- 마이그레이션 완료 후 제거

---

## ⚠️ 주의사항

1. **세션 존재 확인 필수**: Request의 `sessionId`로 세션이 존재하는지 확인
2. **에러 처리**: 세션이 없으면 404 반환
3. **토큰 계산**: 이전 토큰을 정확히 조회해야 함
4. **Turn 계산**: 이전 대화의 Turn을 정확히 계산해야 함

---

## 🔗 관련 문서

- [API Specification](./API_Specification.md) - 전체 API 명세
- [Database Changes Summary](./Database_Changes_Summary.md) - DB 변경사항

---

## 📅 변경 이력

| 날짜 | 변경사항 |
|------|---------|
| 2024-12-07 | API 구조 변경 계획 수립 |
| 2024-12-07 | Request/Response 구조 변경 결정 |
| 2024-12-07 | 역할 및 책임 분리 결정 |
| 2024-12-07 | Submit API 변경사항 추가 |
| 2024-12-07 | WebSocket/SSE 미사용 결정 (RESTful API만 사용) |

