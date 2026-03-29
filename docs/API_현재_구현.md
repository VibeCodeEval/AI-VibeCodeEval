# 현재 구현된 API 명세 (2024-12-07)

> **최종 정리일**: 2026-03-27

## 📋 개요

현재 LangGraph Worker에서 활성화된 API 엔드포인트와 Request/Response 형식을 정리한 문서입니다.

**Base URL**: `http://localhost:8000`

---

## 1. POST /api/chat/messages

**메시지 전송 및 AI 응답 받기**

### 호출 방법

```http
POST /api/chat/messages
Content-Type: application/json
```

### Request Body

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

#### 필드 설명

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `sessionId` | integer | ✅ | 세션 ID |
| `examParticipantId` | integer | ✅ | 참가자 식별값 (exam_participants.id) |
| `turnId` | integer | ✅ | DB의 `prompt_messages.turn` (사용자 메시지 턴) |
| `role` | string | ✅ | 역할 (USER) |
| `content` | string | ✅ | 메시지 내용 |
| `context` | object | ✅ | 문제 컨텍스트 |
| `context.problemId` | integer | ✅ | 문제 ID |
| `context.specVersion` | integer | ✅ | 스펙 버전 |

### Response Body (200 OK)

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

#### 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `aiMessage` | object | AI 응답 메시지 |
| `aiMessage.session_id` | integer | 세션 ID |
| `aiMessage.turn` | integer | AI 응답 턴 (이전 대화 Turn + 1) |
| `aiMessage.role` | string | 역할 ("AI") |
| `aiMessage.content` | string | LLM이 생성한 응답 |
| `aiMessage.tokenCount` | integer | 현재 AI 응답 생성에 사용된 토큰 |
| `aiMessage.totalToken` | integer | 전체 누적 토큰 (세션 토큰) |

### Error Response (404 Not Found)

```json
{
  "error": true,
  "error_code": "SESSION_NOT_FOUND",
  "error_message": "세션을 찾을 수 없습니다. (session_id: 1)"
}
```

### Error Response (504 Gateway Timeout)

```json
{
  "error": true,
  "error_code": "TIMEOUT",
  "error_message": "요청 처리 시간이 초과되었습니다. (2분 타임아웃) - LLM API 응답 지연 또는 Quota 제한 가능"
}
```

### Error Response (500 Internal Server Error)

```json
{
  "error": true,
  "error_code": "LANGGRAPH_ERROR",
  "error_message": "LangGraph 실행 중 오류가 발생했습니다."
}
```

---

## 2. POST /api/session/submit

**코드 제출 및 평가**

### 호출 방법

```http
POST /api/session/submit
Content-Type: application/json
```

### Request Body

```json
{
  "problemId": 1,
  "specVersion": 1,
  "examParticipantId": 9001,
  "finalCode": "def solve():\n    print('hello')",
  "language": "python3.11",
  "submissionId": 88001
}
```

#### 필드 설명

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `problemId` | integer | ✅ | 문제 ID |
| `specVersion` | integer | ✅ | 스펙 버전 |
| `examParticipantId` | integer | ✅ | 참가자 식별값 (exam_participants.id) |
| `finalCode` | string | ✅ | 제출 코드 |
| `language` | string | ✅ | 프로그래밍 언어 (예: python3.11) |
| `submissionId` | integer | ✅ | 제출 ID (백엔드에서 생성) |

### Response Body (200 OK)

```json
{
  "submissionId": 88001,
  "status": "successed"
}
```

#### 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `submissionId` | integer | 제출 ID |
| `status` | string | 처리 상태 (`successed` 또는 `failed`) |

### Error Response (404 Not Found)

#### examParticipantId 없음

```json
{
  "error": true,
  "error_code": "EXAM_PARTICIPANT_NOT_FOUND",
  "error_message": "시험 참가자 정보를 찾을 수 없습니다. (examParticipantId: 9001)"
}
```

#### 세션 없음

```json
{
  "error": true,
  "error_code": "SESSION_NOT_FOUND",
  "error_message": "진행 중인 세션을 찾을 수 없습니다. (exam_id: 1, participant_id: 100)"
}
```

### Error Response (500 Internal Server Error)

```json
{
  "submissionId": 88001,
  "status": "failed"
}
```

---

## 📝 참고사항

### 1. 메시지 저장

- **Worker는 메시지를 저장하지 않습니다.**
- 메시지 저장은 백엔드(Spring Boot)에서 처리합니다.
- Worker는 AI 응답 생성만 담당합니다.

### 2. 세션 생성

- **Worker는 세션을 생성하지 않습니다.**
- 세션 생성은 백엔드에서 처리합니다.
- Worker는 기존 세션을 조회만 합니다.

### 3. 비동기 처리

- **Submit API는 비동기로 처리됩니다.**
- 백엔드 서버를 잡아두지 않고 즉시 Response를 반환합니다.
- 평가 결과는 백그라운드에서 처리되어 DB에 저장됩니다.

### 4. 토큰 계산

- `tokenCount`: 현재 AI 응답 생성에 사용된 토큰
- `totalToken`: 전체 누적 토큰 (이전 토큰 + 현재 토큰)

### 5. Turn 계산

- `turnId`: Request의 사용자 메시지 턴
- `aiMessage.turn`: AI 응답 턴 (turnId + 1)

---

## 🔗 관련 문서

- [API Specification](./API_Specification.md) - 전체 API 명세
- [API Changes 2024-12-07](./API_Changes_2024-12-07.md) - API 변경사항
- [Database Changes Summary](./Database_Changes_Summary.md) - DB 변경사항

---

## 📅 업데이트 이력

| 날짜 | 변경사항 |
|------|---------|
| 2024-12-07 | 신규 API 명세 작성 |
| 2024-12-07 | POST /api/chat/messages 구현 |
| 2024-12-07 | POST /api/session/submit 구현 |

