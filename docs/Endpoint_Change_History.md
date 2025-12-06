# 엔드포인트 변경 이력

## 개요

API 엔드포인트 수정 및 변경 사항을 기록한 문서입니다.

---

## 주요 변경 사항

### 1. `/api/chat/message` → `/api/session/{sessionId}/messages`

**변경 일자**: 2025-12-06

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
- ✅ 세션 자동 생성/조회
- ✅ 사용자 메시지 즉시 저장
- ✅ AI 응답 저장
- ✅ Turn 번호 미리 계산 (UPDATE 제거)

---

### 2. `/api/chat/submit` → `/api/session/{sessionId}/submit`

**변경 일자**: 2025-12-06

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
- ✅ `sessionId`를 Path Parameter로 이동
- ✅ `examId`, `participantId`, `specId`는 세션에서 자동 조회
- ✅ Response에 Submission 정보 추가

---

### 3. 세션 생성 API 추가

**변경 일자**: 2025-12-06

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

---

## 기술적 변경 사항

### 1. `get_db_context` → `get_db` 변경

**파일**: `app/presentation/api/routes/chat.py`

**변경 내용:**
- `send_message` 함수: `get_db_context` → `get_db`
- `get_problem_info` 함수: `get_db_context` → `get_db`
- `save_chat_message` 함수: `get_db_context` → `get_db`

**이유:**
- FastAPI의 의존성 주입 패턴에 맞춤
- 세션 관리 자동화

---

### 2. 전역 예외 핸들러 추가

**파일**: `app/main.py`

**변경 내용:**
- 모든 예외를 캡처하여 로깅
- JSON 형식으로 에러 응답 반환
- 에러 타입, 메시지, 경로 정보 포함

---

### 3. 세션 생성 및 Turn 번호 계산 로직 추가

**파일**: `app/presentation/api/routes/chat.py`

**변경 내용:**
- `SessionRepository.get_or_create_session()` 호출
- `SessionRepository.get_next_turn_number()` 호출
- 사용자 메시지 즉시 저장
- AI 응답 저장

---

## 데이터 플로우 변경

### 변경 전

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
- ❌ 세션 생성 안 함
- ❌ 메시지 저장 안 함

### 변경 후

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
[3] 사용자 메시지 저장 (PostgreSQL) ✅
  ↓
[4] LangGraph 실행 (Redis)
  ↓
[5] AI 응답 저장 (PostgreSQL) ✅
  ↓
[응답 반환]
```

**PostgreSQL 저장:**
- ✅ 세션 자동 생성
- ✅ 사용자 메시지 저장
- ✅ AI 응답 저장

---

## 핵심 개선 사항

### 1. 자동화
- ✅ 세션 자동 생성/조회
- ✅ 메시지 자동 저장
- ✅ Spring Boot는 한 번만 호출

### 2. 성능 최적화
- ✅ UPDATE 제거
- ✅ INSERT만 사용
- ✅ Turn 번호 미리 계산

### 3. 데이터 안정성
- ✅ 사용자 메시지 즉시 저장
- ✅ AI 응답 생성 실패해도 사용자 메시지 보존
- ✅ 각 메시지가 독립적으로 저장

### 4. RESTful 설계
- ✅ 리소스 중심 경로 구조
- ✅ Path Parameter 활용
- ✅ 명확한 엔드포인트 분리

---

## 추가된 함수

### `SessionRepository.get_next_turn_number()`

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

## Session ID 매핑

**매핑:**
- PostgreSQL: `session.id` (int, 예: `123`)
- Redis: `"session_{id}"` (str, 예: `"session_123"`)

**이유:**
- LangGraph는 문자열 session_id 사용
- PostgreSQL은 정수 ID 사용
- 자동 변환으로 일관성 유지

---

## 수정된 파일 목록

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

## 테스트 체크리스트

1. ✅ 세션 자동 생성 확인
2. ✅ 사용자 메시지 저장 확인
3. ✅ AI 응답 저장 확인
4. ✅ Turn 번호 정확성 확인
5. ✅ Session ID 매핑 확인
6. ✅ 에러 처리 확인

---

## 참고 문서

- `docs/API_Specification.md` - 현재 API 명세서
- `docs/Message_Storage_Implementation.md` - 메시지 저장 구현 내용

