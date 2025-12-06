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

## 테스트 설정 가이드

### 테스트 진행 순서

1. **Docker 컨테이너 확인**
2. **PostgreSQL 연결 확인**
3. **Redis 연결 확인**
4. **DB 스키마 초기화**
5. **테스트 데이터 준비**
6. **Python 연결 테스트**

### 1단계: Docker 컨테이너 확인

```powershell
# 모든 컨테이너 상태 확인
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# docker-compose로 실행 중인 서비스 확인
docker-compose -f docker-compose.dev.yml ps
```

**예상 결과:**
- `ai_vibe_postgres_dev`: Up (healthy)
- `ai_vibe_redis_dev`: Up (healthy)

### 2단계: PostgreSQL 연결 확인

```powershell
# PostgreSQL 버전 확인
docker exec ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "SELECT version();"

# 현재 데이터베이스 및 스키마 확인
docker exec ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "SELECT current_database(), current_schema();"
```

### 3단계: Redis 연결 확인

```powershell
# Redis 연결 테스트
docker exec ai_vibe_redis_dev redis-cli ping

# Redis 버전 확인
docker exec ai_vibe_redis_dev redis-cli INFO server | Select-String -Pattern "redis_version"
```

**예상 결과:**
- `PONG` 응답
- Redis 7.x 버전

### 4단계: DB 스키마 초기화

```powershell
# init-db.sql 실행 (스키마 생성)
Get-Content scripts/init-db.sql | docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test
```

### 5단계: 테스트 데이터 준비

```powershell
# 테스트 데이터 삽입 (참조 테이블 포함)
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c @"
SET search_path TO ai_vibe_coding_test;

-- 참조 테이블 생성
INSERT INTO exams (id, title, state, version) VALUES (1, '테스트 시험', 'WAITING', 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO participants (id, name) VALUES (1, '테스트 참가자') ON CONFLICT (id) DO NOTHING;
INSERT INTO problems (id, title, difficulty, status) VALUES (1, '테스트 문제', 'MEDIUM', 'PUBLISHED') ON CONFLICT (id) DO NOTHING;
INSERT INTO problem_specs (spec_id, problem_id, version, content_md) VALUES (10, 1, 1, '테스트 스펙') ON CONFLICT (spec_id) DO NOTHING;

-- exam_participants 삽입
INSERT INTO exam_participants (exam_id, participant_id, spec_id, state, token_limit, token_used) 
VALUES (1, 1, 10, 'REGISTERED', 20000, 0) 
ON CONFLICT (exam_id, participant_id) DO NOTHING;
"@
```

---

## 웹 API 테스트 가이드

### 사전 준비

#### 1. Docker 컨테이너 실행 확인
```powershell
# PostgreSQL 확인
docker ps --filter "name=postgres"

# Redis 확인
docker ps --filter "name=redis"
```

#### 2. 환경 변수 확인
`.env` 파일에 다음 변수가 설정되어 있는지 확인:
- `POSTGRES_HOST=localhost`
- `POSTGRES_PORT=5435`
- `POSTGRES_DB=ai_vibe_coding_test`
- `POSTGRES_USER=postgres`
- `POSTGRES_PASSWORD=postgres`
- `REDIS_HOST=localhost`
- `REDIS_PORT=6379`
- `GEMINI_API_KEY=your_api_key`

### 서버 실행

```powershell
# 개발 서버 실행
uv run python scripts/run_dev.py
```

**서버 확인:**
- **API 문서**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

### 전체 플로우 테스트

#### 1단계: 세션 시작

```powershell
curl -X POST "http://localhost:8000/api/session/start" `
  -H "Content-Type: application/json" `
  -d '{
    "examId": 1,
    "participantId": 100,
    "specId": 20
  }'
```

#### 2단계: 메시지 전송

```powershell
curl -X POST "http://localhost:8000/api/session/18/messages" `
  -H "Content-Type: application/json" `
  -d '{
    "role": "USER",
    "content": "문제 조건을 다시 설명해줘."
  }'
```

#### 3단계: 코드 제출

```powershell
curl -X POST "http://localhost:8000/api/session/18/submit" `
  -H "Content-Type: application/json" `
  -d '{
    "code": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)",
    "lang": "python"
  }'
```

---

## 웹 제출 플로우 테스트

### 실행 방법

#### 1. 서버 실행
```bash
# FastAPI 서버 실행
uvicorn app.main:app --reload
```

#### 2. Judge0 Worker 실행 (별도 터미널)
```bash
# Judge0 Worker 실행
python -m app.application.workers.judge_worker
```

#### 3. 웹 인터페이스 접속
브라우저에서 접속:
```
http://localhost:8000
```

### 테스트 절차

1. **세션 시작**: 웹 페이지 접속, 자동으로 세션 ID 생성
2. **채팅 (선택사항)**: 채팅 입력창에 질문 입력, AI 응답 확인
3. **코드 제출**: 코드 입력창에 코드 입력, "코드 제출" 버튼 클릭
4. **결과 확인**: 채팅창과 최종 점수 섹션에서 결과 확인

---

## 테스트 케이스 구조

### 테스트 케이스 위치

**파일**: `app/domain/langgraph/utils/problem_info.py`

**구조**: `HARDCODED_PROBLEM_SPEC[10]` 딕셔너리 내부

### 테스트 케이스 형식

```python
"test_cases": [
    {
        "input": "4\n0 10 15 20\n5 0 9 10\n6 13 0 12\n8 8 9 0\n",
        "expected": "35",
        "description": "기본 케이스: 4개 도시"
    },
    # ... 총 10개
]
```

### 필드 설명

- **input**: 테스트 케이스 입력 (stdin 형식)
- **expected**: 예상 출력
- **description**: 테스트 케이스 설명 (선택사항)

### 채점 기준 구조

```python
"rubric": {
    "correctness": {
        "weight": 0.5,
        "description": "정확성 점수 (테스트 케이스 통과율)",
        "criteria": {
            "all_passed": {"score": 100, ...},
            "partial_passed": {"score_formula": "...", ...},
            "none_passed": {"score": 0, ...}
        }
    },
    "performance": {
        "weight": 0.25,
        "description": "성능 점수 (실행 시간 및 메모리 사용량)",
        "criteria": {
            "time_score": {"weight": 0.6, ...},
            "memory_score": {"weight": 0.4, ...}
        }
    }
}
```

### 가중치

- **정확성 (Correctness)**: 50%
- **성능 (Performance)**: 25%
- **프롬프트 점수 (Prompt Score)**: 25%

---

## 언어 정보

### 언어 이름 → Judge0 ID 매핑

**위치**: `app/infrastructure/judge0/client.py`

```python
LANGUAGE_IDS = {
    "python": 71,
    "python3": 71,
    "java": 62,
    "cpp": 54,
    "c++": 54,
    "c": 50,
    "javascript": 63,
    "nodejs": 63,
    "go": 60,
    "rust": 73,
}
```

### API 요청에서 언어 지정

```json
{
  "code": "def fibonacci(n): ...",
  "lang": "python"
}
```

**기본값**: `"python"`

---

## 📚 관련 문서

- [Database Changes Summary](./Database_Changes_Summary.md)
- [Docker PostgreSQL Setup Guide](./Docker_PostgreSQL_Setup_Guide.md)


