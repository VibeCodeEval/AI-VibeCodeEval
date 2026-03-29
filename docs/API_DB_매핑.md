# API와 DB 필드명 매핑 분석 (2024-12-07)

> **최종 정리일**: 2026-03-27

## 📋 개요

현재 구현된 API의 필드명과 DB 테이블 컬럼명 간의 매핑 상태를 분석한 문서입니다.

---

## 🔍 매핑 분석 결과

### 1. POST /api/chat/messages

#### Request 필드 → DB 컬럼 매핑

| API 필드 | DB 테이블 | DB 컬럼 | 매핑 상태 | 비고 |
|---------|----------|---------|----------|------|
| `sessionId` | `prompt_sessions` | `id` | ⚠️ **불일치** | API: camelCase, DB: `id` |
| `examParticipantId` | `exam_participants` | `id` | ⚠️ **불일치** | API: camelCase, DB: `id` |
| `turnId` | `prompt_messages` | `turn` | ⚠️ **불일치** | API: camelCase, DB: `turn` |
| `role` | `prompt_messages` | `role` | ✅ 일치 | - |
| `content` | `prompt_messages` | `content` | ✅ 일치 | - |
| `context.problemId` | `problem_specs` | `problem_id` | ⚠️ **불일치** | API: camelCase, DB: snake_case |
| `context.specVersion` | `problem_specs` | `version` | ⚠️ **불일치** | API: camelCase, DB: `version` |

#### Response 필드 → DB 컬럼 매핑

| API 필드 | DB 테이블 | DB 컬럼 | 매핑 상태 | 비고 |
|---------|----------|---------|----------|------|
| `aiMessage.session_id` | `prompt_sessions` | `id` | ⚠️ **불일치** | API: snake_case, DB: `id` |
| `aiMessage.turn` | `prompt_messages` | `turn` | ✅ 일치 | - |
| `aiMessage.role` | `prompt_messages` | `role` | ✅ 일치 | - |
| `aiMessage.content` | `prompt_messages` | `content` | ✅ 일치 | - |
| `aiMessage.tokenCount` | `prompt_messages` | `token_count` | ⚠️ **불일치** | API: camelCase, DB: snake_case |
| `aiMessage.totalToken` | `prompt_sessions` | `total_tokens` | ⚠️ **불일치** | API: camelCase, DB: snake_case |

---

### 2. POST /api/session/submit

#### Request 필드 → DB 컬럼 매핑

| API 필드 | DB 테이블 | DB 컬럼 | 매핑 상태 | 비고 |
|---------|----------|---------|----------|------|
| `problemId` | `problem_specs` | `problem_id` | ⚠️ **불일치** | API: camelCase, DB: snake_case |
| `specVersion` | `problem_specs` | `version` | ⚠️ **불일치** | API: camelCase, DB: `version` |
| `examParticipantId` | `exam_participants` | `id` | ⚠️ **불일치** | API: camelCase, DB: `id` |
| `finalCode` | `submissions` | `code` | ⚠️ **불일치** | API: camelCase, DB: `code` |
| `language` | `submissions` | `language` | ✅ 일치 | - |
| `submissionId` | `submissions` | `id` 또는 `submission_id` | ⚠️ **불일치** | 확인 필요 |

#### Response 필드 → DB 컬럼 매핑

| API 필드 | DB 테이블 | DB 컬럼 | 매핑 상태 | 비고 |
|---------|----------|---------|----------|------|
| `submissionId` | `submissions` | `id` 또는 `submission_id` | ⚠️ **불일치** | 확인 필요 |
| `status` | `submissions` | `status` | ✅ 일치 (가정) | - |

---

## ⚠️ 발견된 문제점

### 1. 네이밍 컨벤션 불일치

#### 문제
- **API**: camelCase (`sessionId`, `examParticipantId`, `tokenCount`, `totalToken`)
- **DB**: snake_case (`session_id`, `exam_id`, `participant_id`, `token_count`, `total_tokens`)
- **Response**: 혼합 (일부 snake_case `session_id`, 일부 camelCase `tokenCount`)

#### 영향
- 코드에서 필드명 변환이 필요함
- 혼란 가능성
- 일관성 부족

### 2. 필드명 의미 불일치

#### 문제
- `sessionId` → DB의 `prompt_sessions.id` (명확함)
- `examParticipantId` → DB의 `exam_participants.id` (명확함)
- `turnId` → DB의 `prompt_messages.turn` (명확함)
- `specVersion` → DB의 `problem_specs.version` (명확함)
- `problemId` → DB의 `problem_specs.problem_id` (명확함)

#### 영향
- 의미는 명확하지만 네이밍이 다름

### 3. Response 필드명 혼합

#### 문제
- `aiMessage.session_id` (snake_case)
- `aiMessage.tokenCount` (camelCase)
- `aiMessage.totalToken` (camelCase)

#### 영향
- 일관성 부족
- 클라이언트에서 혼란 가능

---

## 📊 DB 테이블 구조 참고

### prompt_sessions
```sql
id BIGSERIAL PRIMARY KEY
exam_id BIGINT
participant_id BIGINT
spec_id BIGINT
total_tokens INTEGER
started_at TIMESTAMPTZ
ended_at TIMESTAMPTZ
```

### prompt_messages
```sql
id BIGSERIAL PRIMARY KEY
session_id BIGINT
turn INTEGER
role prompt_role_enum
content TEXT
token_count INTEGER
meta JSONB
created_at TIMESTAMPTZ
```

### exam_participants
```sql
id BIGSERIAL PRIMARY KEY
exam_id BIGINT
participant_id BIGINT
spec_id BIGINT
state VARCHAR(20)
token_limit INTEGER
token_used INTEGER
joined_at TIMESTAMPTZ
```

### problem_specs
```sql
spec_id BIGSERIAL PRIMARY KEY
problem_id BIGINT
version INTEGER
content_md TEXT
checker_json JSONB
rubric_json JSONB
...
```

### submissions
```sql
id BIGSERIAL PRIMARY KEY
submission_id BIGINT (확인 필요)
exam_id BIGINT
participant_id BIGINT
problem_id BIGINT
spec_id BIGINT
code TEXT
language VARCHAR(50)
status VARCHAR(20)
...
```

---

## 💡 권장 사항

### 옵션 1: API를 DB 컬럼명에 맞추기 (snake_case 통일)

**장점:**
- DB와 일치하여 매핑 간단
- Python 컨벤션과 일치

**단점:**
- JavaScript/TypeScript 클라이언트에서 camelCase 선호
- 기존 API와 불일치 가능

### 옵션 2: DB를 API 필드명에 맞추기 (camelCase 통일)

**장점:**
- JavaScript/TypeScript 클라이언트 친화적
- RESTful API 일반적 관례

**단점:**
- DB 스키마 변경 필요 (비현실적)
- Python/SQL 컨벤션과 불일치

### 옵션 3: Pydantic alias 사용 (현재 부분 적용)

**장점:**
- API는 camelCase 유지
- 내부 코드는 snake_case 사용
- 변환 자동화 가능

**단점:**
- alias 설정 필요
- 복잡도 증가

### 옵션 4: Response만 snake_case로 통일

**장점:**
- Response 일관성 확보
- DB와 직접 매핑 가능

**단점:**
- Request와 Response 네이밍 불일치
- 클라이언트 혼란 가능

---

## 🔧 수정이 필요한 필드

### Request (POST /api/chat/messages)
- ✅ `sessionId` → `session_id` (alias 사용 중)
- ✅ `examParticipantId` → `exam_participant_id` (alias 필요)
- ✅ `turnId` → `turn_id` (alias 필요)
- ✅ `context.problemId` → `problem_id` (alias 사용 중)
- ✅ `context.specVersion` → `spec_version` (alias 사용 중)

### Response (POST /api/chat/messages)
- ⚠️ `aiMessage.session_id` → 일관성 유지 또는 `sessionId`로 변경
- ⚠️ `aiMessage.tokenCount` → `token_count`로 변경 또는 일관성 유지
- ⚠️ `aiMessage.totalToken` → `total_token`로 변경 또는 일관성 유지

### Request (POST /api/session/submit)
- ✅ `problemId` → `problem_id` (alias 필요)
- ✅ `specVersion` → `spec_version` (alias 필요)
- ✅ `examParticipantId` → `exam_participant_id` (alias 필요)
- ✅ `finalCode` → `final_code` (alias 필요)
- ✅ `submissionId` → `submission_id` (alias 필요)

### Response (POST /api/session/submit)
- ⚠️ `submissionId` → `submission_id`로 변경 또는 일관성 유지

---

## 📝 다음 단계

1. **네이밍 컨벤션 결정**: camelCase vs snake_case 통일
2. **Pydantic alias 설정**: Request 필드에 alias 추가
3. **Response 필드명 통일**: 일관된 네이밍 적용
4. **코드 수정**: 필드명 매핑 로직 수정
5. **테스트**: API 호출 및 DB 저장 확인

---

## 🔗 관련 문서

- [API Current Implementation](./API_Current_Implementation.md) - 현재 API 명세
- [API Changes 2024-12-07](./API_Changes_2024-12-07.md) - API 변경사항
- [Database Changes Summary](./Database_Changes_Summary.md) - DB 변경사항

