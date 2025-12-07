# 전체 플로우 테스트 실행 가이드

## ⚠️ 테스트 전 필수 사항

### 1. PostgreSQL 서버 실행

```bash
# Docker Compose로 PostgreSQL 실행
docker-compose -f docker-compose.dev.yml up -d postgres

# 또는 로컬 PostgreSQL 사용 시
# PostgreSQL이 실행 중인지 확인
```

### 2. DB 스키마 초기화

```bash
# Docker PostgreSQL에 스키마 초기화
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test < scripts/init-db.sql

# 또는 로컬 PostgreSQL 사용 시
psql -U postgres -d ai_vibe_coding_test < scripts/init-db.sql
```

**필수 테이블:**
- `exam_participants` (ENUM 타입 포함)
- `prompt_sessions`
- `prompt_messages`
- `prompt_evaluations`
- `submissions`
- `scores`

### 3. Redis 서버 실행

```bash
# Docker Compose로 Redis 실행
docker-compose -f docker-compose.dev.yml up -d redis

# 또는 로컬 Redis 사용 시
# Redis가 실행 중인지 확인
```

---

## 🧪 테스트 실행

### 방법 1: 서버를 통한 전체 플로우 테스트

**전제 조건:**
- FastAPI 서버 실행 중
- Judge0 Worker 실행 중 (제출 테스트용)

```bash
# 서버 실행 (터미널 1)
uv run uvicorn app.main:app --reload

# Worker 실행 (터미널 2)
uv run python -m app.application.workers.judge_worker

# 테스트 실행 (터미널 3)
uv run python test_scripts/test_full_flow_complete.py
```

**테스트 내용:**
1. 메시지 저장 API 호출
2. 채팅 플로우 테스트
3. 코드 제출 테스트
4. 평가 결과 확인

### 방법 2: DB/Redis 직접 테스트 (서버 불필요)

```bash
# 테스트 실행
uv run python test_scripts/test_full_flow_db_redis.py
```

**테스트 내용:**
1. 메시지 저장 (PostgreSQL + Redis)
2. 평가 저장 (prompt_evaluations)
3. 제출 및 점수 저장 (Submission + Score)
4. Redis TTL 확인

---

## ❌ 테스트 실패 시 확인 사항

### 1. PostgreSQL 연결 실패

**에러:**
```
ConnectionRefusedError: [WinError 1225] 원격 컴퓨터가 네트워크 연결을 거부했습니다
```

**해결:**
- PostgreSQL 서버가 실행 중인지 확인
- `.env` 파일의 `POSTGRES_HOST`, `POSTGRES_PORT` 확인
- Docker 컨테이너 상태 확인: `docker ps`

### 2. 테이블이 존재하지 않음

**에러:**
```
UndefinedTableError: relation "exam_participants" does not exist
```

**해결:**
- `scripts/init-db.sql` 실행
- 또는 테스트 스크립트가 자동으로 생성하도록 수정 (현재 구현됨)

### 3. ENUM 타입 불일치

**에러:**
```
InvalidTextRepresentationError: invalid input value for enum
```

**해결:**
- 기존 ENUM 타입 삭제 후 재생성
- 또는 `scripts/init-db.sql`로 전체 스키마 재생성

### 4. Redis 연결 실패

**에러:**
```
Redis connection failed
```

**해결:**
- Redis 서버가 실행 중인지 확인
- `.env` 파일의 `REDIS_HOST`, `REDIS_PORT` 확인
- Docker 컨테이너 상태 확인: `docker ps`

---

## ✅ 테스트 성공 시 예상 출력

```
################################################################################
# 전체 플로우 DB/Redis 직접 테스트 (서버 없이)
# TTL 설정: 86400초 (24.00시간)
################################################################################

================================================================================
[1단계] 메시지 저장 테스트 (PostgreSQL + Redis)
================================================================================
✅ 새 세션 생성: session_id=1
✅ 메시지 저장: message_id=1, turn=1
✅ Redis 체크포인트 업데이트: session_id=session_1

================================================================================
[2단계] 평가 저장 테스트 (prompt_evaluations)
================================================================================
✅ 턴 평가 저장: id=1, turn=1, score=85.5
✅ Holistic Flow 평가 저장: id=2, score=90.0

================================================================================
[3단계] 제출 및 점수 저장 테스트 (Submission + Score)
================================================================================
✅ Submission 생성: id=1, lang=python
✅ Submission 상태 업데이트: status=DONE
✅ Score 저장:
   prompt_score: 85.5
   perf_score: 90.0
   correctness_score: 95.0
   total_score: 91.25
✅ 세션 종료: ended_at 설정됨

================================================================================
[4단계] Redis TTL 확인
================================================================================
✅ Redis TTL 확인:
   키: graph_state:session_1
   TTL: 86400초 (24.00시간)
   설정값: 86400초 (24.00시간)
✅ TTL이 설정값과 일치합니다!

================================================================================
✅ 전체 플로우 테스트 완료!
================================================================================

📋 테스트 요약:
   - Session ID: 1
   - Submission ID: 1
   - 메시지 저장: ✅
   - 평가 저장: ✅
   - 제출 완료: ✅
   - Redis TTL: ✅
```

---

## 📝 테스트 체크리스트

- [ ] PostgreSQL 서버 실행 확인
- [ ] Redis 서버 실행 확인
- [ ] DB 스키마 초기화 완료
- [ ] `.env` 파일 설정 확인
- [ ] 테스트 스크립트 실행
- [ ] 모든 단계 성공 확인

---

## 🔍 테스트 실패 시 디버깅

### 1. DB 연결 확인

```bash
# Docker PostgreSQL 연결 테스트
docker exec -it ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test

# 테이블 목록 확인
\dt ai_vibe_coding_test.*

# 특정 테이블 확인
SELECT * FROM ai_vibe_coding_test.prompt_sessions LIMIT 5;
```

### 2. Redis 연결 확인

```bash
# Docker Redis 연결 테스트
docker exec -it ai_vibe_redis_dev redis-cli

# 키 목록 확인
KEYS *

# 특정 키 확인
GET graph_state:session_1
TTL graph_state:session_1
```

### 3. 로그 확인

```bash
# FastAPI 서버 로그
# 터미널에서 확인

# Worker 로그
# 별도 터미널에서 확인
```

---

## 📚 관련 문서

- [Database Changes Summary](./Database_Changes_Summary.md)
- [Implementation Complete Summary](./Implementation_Complete_Summary.md)
- [Docker PostgreSQL Setup Guide](./Docker_PostgreSQL_Setup_Guide.md)


