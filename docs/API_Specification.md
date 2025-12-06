# API 명세서

## 개요

AI Vibe Coding Test Worker의 REST API 명세서입니다.

- **Base URL**: `http://localhost:8000`
- **API 버전**: `v1`
- **문서 URL**: `/docs` (Swagger UI), `/redoc` (ReDoc)

---

## 인증

현재 인증은 구현되지 않았습니다. 향후 추가 예정입니다.

---

## 공통 사항

### HTTP 상태 코드

- `200 OK`: 성공
- `400 Bad Request`: 잘못된 요청
- `404 Not Found`: 리소스를 찾을 수 없음
- `500 Internal Server Error`: 서버 내부 오류
- `504 Gateway Timeout`: 요청 처리 시간 초과

### Content-Type

- Request: `application/json`
- Response: `application/json`

### 타임아웃

- 메시지 제출: 120초 (2분)
- 코드 제출: 300초 (5분)

### 공통 응답 형식

#### 성공 응답

```json
{
  "error": false,
  "data": { ... }
}
```

#### 에러 응답

```json
{
  "error": true,
  "error_code": "ERROR_CODE",
  "error_message": "에러 메시지",
  "details": { ... }
}
```

---

## 1. POST /api/session/start

**응시자 채팅 세션 시작**

새로운 채팅 세션을 시작하고 세션 정보를 반환합니다.

### Request Body

```json
{
  "examId": 1,
  "participantId": 100,
  "specId": 20
}
```

#### 필드 설명

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `examId` | integer | ✅ | 시험 ID |
| `participantId` | integer | ✅ | 참가자 ID |
| `specId` | integer | ✅ | 문제 스펙 ID |

> **참고**: 향후 Authorization 토큰에서 `participantId`를 추출하도록 변경 예정입니다.

### Response Body (200 OK)

```json
{
  "id": 18,
  "examId": 1,
  "participantId": 100,
  "specId": 20,
  "startedAt": "2025-12-06T15:24:52.828000",
  "endedAt": null,
  "totalTokens": 0
}
```

#### 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | integer | 생성된 세션 ID |
| `examId` | integer | 시험 ID |
| `participantId` | integer | 참가자 ID |
| `specId` | integer | 문제 스펙 ID |
| `startedAt` | string \| null | 세션 시작 시간 (ISO 8601) |
| `endedAt` | string \| null | 세션 종료 시간 (ISO 8601, null이면 진행 중) |
| `totalTokens` | integer | 총 토큰 사용량 (초기값: 0) |

### Error Response (400 Bad Request)

```json
{
  "error": true,
  "error_code": "SESSION_START_FAILED",
  "error_message": "시험 참가자 정보 없음: exam_id=1, participant_id=100"
}
```

### Error Response (500 Internal Server Error)

```json
{
  "error": true,
  "error_code": "INTERNAL_ERROR",
  "error_message": "세션 시작 중 오류가 발생했습니다: ..."
}
```

---

## 2. POST /api/session/{sessionId}/messages

**사용자 메시지 전송 & AI 응답**

사용자 메시지를 전송하고 AI 응답을 받습니다.

### Path Parameters

- `sessionId` (integer, required): 세션 ID

### Request Body

```json
{
  "role": "USER",
  "content": "문제 조건을 다시 설명해줘."
}
```

#### 필드 설명

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `role` | string | ✅ | 역할 (USER만 가능) |
| `content` | string | ✅ | 메시지 내용 |

### Response Body (200 OK)

```json
{
  "userMessage": {
    "id": 3001,
    "turn": 1,
    "role": "USER",
    "content": "문제 조건을 다시 설명해줘.",
    "tokenCount": null
  },
  "aiMessage": {
    "id": 3002,
    "turn": 2,
    "role": "AI",
    "content": "다음은 문제 조건입니다...",
    "tokenCount": 120
  },
  "session": {
    "id": 2001,
    "totalTokens": 135
  }
}
```

#### 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `userMessage` | object | 저장된 사용자 메시지 정보 |
| `userMessage.id` | integer | 메시지 ID |
| `userMessage.turn` | integer | 턴 번호 |
| `userMessage.role` | string | 역할 (USER) |
| `userMessage.content` | string | 메시지 내용 |
| `userMessage.tokenCount` | integer \| null | 토큰 사용량 (사용자 메시지는 null) |
| `aiMessage` | object \| null | 저장된 AI 응답 메시지 정보 |
| `aiMessage.id` | integer | 메시지 ID |
| `aiMessage.turn` | integer | 턴 번호 |
| `aiMessage.role` | string | 역할 (AI) |
| `aiMessage.content` | string | AI 응답 내용 |
| `aiMessage.tokenCount` | integer \| null | 토큰 사용량 |
| `session` | object | 업데이트된 세션 정보 |
| `session.id` | integer | 세션 ID |
| `session.totalTokens` | integer | 총 토큰 사용량 |

### Error Response (404 Not Found)

```json
{
  "error": true,
  "error_code": "SESSION_NOT_FOUND",
  "error_message": "세션을 찾을 수 없습니다. (session_id: 18)"
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

---

## 3. POST /api/session/{sessionId}/submit

**응시자 코드 제출 및 평가**

응시자가 코드를 제출하고 평가 결과를 받습니다.

### Path Parameters

- `sessionId` (integer, required): 세션 ID

### Request Body

```json
{
  "code": "import sys\n\ndef fibonacci(n):\n    if n <= 1:\n        return n\n    a, b = 0, 1\n    for i in range(2, n + 1):\n        a, b = b, a + b\n    return b\n\nif __name__ == \"__main__\":\n    n = int(sys.stdin.readline())\n    print(fibonacci(n))",
  "lang": "python"
}
```

#### 필드 설명

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `code` | string | ✅ | 제출 코드 |
| `lang` | string | ❌ | 프로그래밍 언어 (기본값: "python") |

### Response Body (200 OK)

```json
{
  "session_id": "session_18",
  "submission": {
    "id": 13,
    "examId": 1,
    "participantId": 100,
    "specId": 20,
    "lang": "python",
    "status": "DONE",
    "codeSha256": "a1b2c3d4e5f6...",
    "codeBytes": 231,
    "codeLoc": 15,
    "createdAt": "2025-12-06T15:27:06.796000",
    "updatedAt": "2025-12-06T15:27:06.796000"
  },
  "is_submitted": true,
  "final_scores": {
    "prompt_score": 65.96,
    "performance_score": 0.0,
    "correctness_score": 100.0,
    "total_score": 66.49,
    "grade": "D"
  },
  "turn_scores": {
    "turn_1": {
      "turn_score": 35.0
    },
    "turn_2": {
      "turn_score": 44.0
    },
    "turn_3": {
      "turn_score": 73.0
    }
  },
  "feedback": {
    "holistic_flow_analysis": "체이닝 전략에 대한 상세 분석..."
  },
  "chat_tokens": {
    "prompt_tokens": 150,
    "completion_tokens": 200,
    "total_tokens": 350
  },
  "eval_tokens": {
    "prompt_tokens": 300,
    "completion_tokens": 400,
    "total_tokens": 700
  },
  "error": false,
  "error_message": null
}
```

#### 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `session_id` | string | 세션 ID (Redis 형식: "session_{id}") |
| `submission` | object \| null | 제출 정보 |
| `submission.id` | integer | 제출 ID |
| `submission.examId` | integer | 시험 ID |
| `submission.participantId` | integer | 참가자 ID |
| `submission.specId` | integer | 문제 스펙 ID |
| `submission.lang` | string | 프로그래밍 언어 |
| `submission.status` | string | 제출 상태 (QUEUED, RUNNING, DONE, FAILED) |
| `submission.codeSha256` | string \| null | 코드 SHA256 해시 |
| `submission.codeBytes` | integer \| null | 코드 바이트 수 |
| `submission.codeLoc` | integer \| null | 코드 라인 수 |
| `submission.createdAt` | string | 생성 시간 (ISO 8601) |
| `submission.updatedAt` | string \| null | 최종 업데이트 시간 (ISO 8601) |
| `is_submitted` | boolean | 제출 완료 여부 |
| `final_scores` | object \| null | 최종 점수 |
| `final_scores.prompt_score` | float | 프롬프트 점수 (0-100, 가중치 25%) |
| `final_scores.performance_score` | float | 성능 점수 (0-100, 가중치 25%) |
| `final_scores.correctness_score` | float | 정확성 점수 (0-100, 가중치 50%) |
| `final_scores.total_score` | float | 총점 (0-100) |
| `final_scores.grade` | string | 등급 (A/B/C/D/F) |
| `turn_scores` | object \| null | 턴별 점수 |
| `turn_scores.turn_{N}` | object | 턴 N의 점수 정보 |
| `turn_scores.turn_{N}.turn_score` | float | 턴 N의 점수 (0-100) |
| `feedback` | object \| null | 평가 피드백 |
| `feedback.holistic_flow_analysis` | string \| null | 체이닝 전략에 대한 상세 분석 |
| `chat_tokens` | object \| null | 채팅 토큰 사용량 (Intent Analyzer, Writer LLM) |
| `chat_tokens.prompt_tokens` | integer | 프롬프트 토큰 수 |
| `chat_tokens.completion_tokens` | integer | 완성 토큰 수 |
| `chat_tokens.total_tokens` | integer | 총 토큰 수 |
| `eval_tokens` | object \| null | 평가 토큰 사용량 (Turn Evaluator, Holistic Evaluator) |
| `eval_tokens.prompt_tokens` | integer | 프롬프트 토큰 수 |
| `eval_tokens.completion_tokens` | integer | 완성 토큰 수 |
| `eval_tokens.total_tokens` | integer | 총 토큰 수 |
| `error` | boolean | 에러 발생 여부 |
| `error_message` | string \| null | 에러 메시지 |

### Error Response (404 Not Found)

```json
{
  "error": true,
  "error_code": "SESSION_NOT_FOUND",
  "error_message": "세션을 찾을 수 없습니다. (session_id: 18)"
}
```

### Error Response (504 Gateway Timeout)

```json
{
  "error": true,
  "error_code": "TIMEOUT",
  "error_message": "요청 처리 시간이 초과되었습니다. (5분 타임아웃)"
}
```

### Error Response (500 Internal Server Error)

```json
{
  "error": true,
  "error_code": "INTERNAL_ERROR",
  "error_message": "코드 제출 중 오류가 발생했습니다: ..."
}
```

---

## 에러 코드

| 에러 코드 | 설명 |
|-----------|------|
| `SESSION_NOT_FOUND` | 세션을 찾을 수 없음 |
| `SESSION_START_FAILED` | 세션 시작 실패 |
| `SUBMISSION_NOT_FOUND` | 제출 정보를 찾을 수 없음 |
| `SCORES_NOT_FOUND` | 점수 정보를 찾을 수 없음 |
| `INTERNAL_ERROR` | 서버 내부 오류 |
| `TIMEOUT` | 요청 타임아웃 |
| `VALIDATION_ERROR` | 요청 검증 실패 |

---

## 참고 사항

### 세션 ID 형식

- **Redis 세션 ID**: `"session_123"` (문자열)
- **PostgreSQL 세션 ID**: `123` (정수)

### 데이터 흐름

1. **메시지 저장**: `submissions` → `submission_runs` → `scores`
2. **평가 흐름**: Turn 평가 → Holistic 평가 → Performance 평가 → Correctness 평가 → 최종 점수

### 토큰 사용량

- `chat_tokens`: Intent Analyzer + Writer LLM
- `eval_tokens`: Turn Evaluator + Holistic Evaluator
- `total_tokens`: chat_tokens + eval_tokens (Core 전달용)

---

## API 테스트 시 데이터 플로우

### 핵심 정리

#### 일반 채팅 API (`POST /api/session/{sessionId}/messages`)

**PostgreSQL 저장 여부:**
- ✅ `prompt_sessions` 테이블에 세션 생성
- ✅ `prompt_messages` 테이블에 메시지 저장
- ✅ 평가 결과는 백그라운드에서 PostgreSQL 저장

**Redis 저장:**
- ✅ State 저장 (TTL 24시간)
- ✅ 턴 로그 저장

#### 제출 API (`POST /api/session/{sessionId}/submit`)

**PostgreSQL 저장:**
- ✅ `submissions` 테이블에 제출 정보 저장
- ✅ `scores` 테이블에 점수 저장
- ✅ `prompt_evaluations` 테이블에 평가 결과 저장

**Redis 저장:**
- ✅ State 업데이트
- ✅ 턴 로그 저장

### 전체 데이터 플로우

#### 1. 메시지 전송 플로우

```
[클라이언트 요청]
  ↓
[1] 세션 조회/생성 (PostgreSQL)
  ↓
[2] 사용자 메시지 저장 (PostgreSQL)
  ↓
[3] LangGraph 실행 (Redis State 사용)
  ↓
[4] AI 응답 저장 (PostgreSQL)
  ↓
[5] Redis State 업데이트
  ↓
[6] 백그라운드 평가 (선택적 PostgreSQL 저장)
  ↓
[응답 반환]
```

#### 2. 코드 제출 플로우

```
[클라이언트 요청]
  ↓
[1] Redis에서 State 로드
  ↓
[2] LangGraph 실행 (제출 플로우)
  ↓
[3] PostgreSQL에 저장 (동기)
  - Submission 생성
  - Score 생성
  - PromptEvaluation 저장
  ↓
[4] Redis State 업데이트
  ↓
[응답 반환]
```

### 데이터 저장 비교

| 항목 | 메시지 전송 | 코드 제출 |
|------|-----------|----------|
| **State** | ✅ Redis | ✅ Redis |
| **메시지** | ✅ PostgreSQL | ✅ PostgreSQL |
| **평가 결과** | ⚠️ 선택적 PostgreSQL | ✅ PostgreSQL |
| **점수** | ❌ | ✅ PostgreSQL |
| **제출 정보** | ❌ | ✅ PostgreSQL |

---

## API 키 위치 및 설정

### 설정 파일 (정의)

**파일**: `app/core/config.py`

```python
class Settings(BaseSettings):
    # LLM API 설정
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    
    # Judge0 설정
    JUDGE0_API_KEY: Optional[str] = None
    
    # Spring Boot 콜백 설정
    SPRING_API_KEY: Optional[str] = None
    
    # LangSmith 설정
    LANGCHAIN_API_KEY: Optional[str] = None
```

### 환경 변수 파일 (실제 값)

**파일**: `.env`

```env
# LLM API 설정
GEMINI_API_KEY=your_gemini_api_key_here

# Judge0 설정
JUDGE0_API_URL=https://judge0-ce.p.rapidapi.com
JUDGE0_API_KEY=your_rapidapi_key_here
JUDGE0_USE_RAPIDAPI=true

# Spring Boot 콜백 설정
SPRING_CALLBACK_URL=http://localhost:8080/api/ai/callback
SPRING_API_KEY=your_spring_api_key_here

# LangSmith 설정
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=your_langsmith_api_key_here
```

### 각 API 키 사용 위치

| API KEY | 사용 위치 | 설명 |
|---------|----------|------|
| **GEMINI_API_KEY** | LLM 노드들 | Gemini API 호출 |
| **JUDGE0_API_KEY** | `app/infrastructure/judge0/client.py` | Judge0 API 호출 |
| **SPRING_API_KEY** | `app/application/services/callback_service.py` | Spring Boot 콜백 인증 |
| **LANGCHAIN_API_KEY** | LangSmith 추적 | LangSmith 추적 활성화 시 |
| **OPENAI_API_KEY** | `app/domain/langgraph/utils/llm_factory.py` | OpenAI 사용 시 (선택) |

### 설정 방법

1. **`.env` 파일 생성**
   ```bash
   cp env.example .env
   ```

2. **API KEY 입력**
   ```env
   GEMINI_API_KEY=your_actual_api_key_here
   JUDGE0_API_KEY=your_judge0_api_key_here
   ```

3. **환경 변수로도 설정 가능**
   ```bash
   export GEMINI_API_KEY=your_api_key_here
   ```

### 주의사항

1. **`.env` 파일은 `.gitignore`에 포함되어야 함**
2. **프로덕션 환경에서는 환경 변수로 설정 권장**
3. **API KEY는 절대 코드에 하드코딩하지 말 것**

---

## [DEPRECATED] 레거시 엔드포인트

### POST /api/chat/message

⚠️ **이 API는 더 이상 사용되지 않습니다.**

**대신 사용하세요:** `POST /api/session/{sessionId}/messages`

### POST /api/chat/submit

⚠️ **이 API는 더 이상 사용되지 않습니다.**

**대신 사용하세요:** `POST /api/session/{sessionId}/submit`
