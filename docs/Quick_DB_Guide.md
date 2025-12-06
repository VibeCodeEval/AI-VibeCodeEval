# 데이터베이스 빠른 가이드

## 🔍 스키마 사용 정책

PostgreSQL에서 **스키마(Schema)**는 테이블을 그룹화하는 논리적 공간입니다.

### 현재 상황

```
데이터베이스: ai_vibe_coding_test
└── ai_vibe_coding_test 스키마 (18개 테이블) ← Python/LangGraph 전용
    ├── exam_participants
    ├── prompt_sessions
    ├── prompt_messages
    ├── prompt_evaluations
    ├── submissions
    ├── scores
    └── ... (기타 테이블들)
```

**스키마 정책**
- `ai_vibe_coding_test`: Python/LangGraph에서 **단독 사용**
- `public`: **사용하지 않음** (연결 끊음)

**참고**: `public` 스키마에 `exam_participants` 테이블이 존재할 수 있지만, Python 코드에서는 사용하지 않습니다.

---

## 📋 테이블 확인 방법

### 1. 모든 테이블 목록 보기

```powershell
# PowerShell에서 실행
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "SELECT schemaname, tablename FROM pg_tables WHERE schemaname IN ('public', 'ai_vibe_coding_test') ORDER BY schemaname, tablename;"
```

### 2. 특정 테이블이 어느 스키마에 있는지 확인

```powershell
# exam_participants 테이블 위치 확인
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "SELECT schemaname, tablename FROM pg_tables WHERE tablename = 'exam_participants';"
```

### 3. 특정 스키마의 테이블만 보기

```powershell
# ai_vibe_coding_test 스키마의 테이블만
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "SELECT tablename FROM pg_tables WHERE schemaname = 'ai_vibe_coding_test' ORDER BY tablename;"
```

---

## 📊 데이터 확인 방법

### 1. 특정 스키마의 테이블 데이터 확인

```powershell
# ai_vibe_coding_test 스키마의 prompt_sessions 확인
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "SELECT * FROM ai_vibe_coding_test.prompt_sessions LIMIT 5;"

# public 스키마의 exam_participants 확인
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "SELECT * FROM public.exam_participants LIMIT 5;"
```

### 2. 두 스키마의 exam_participants 비교

```powershell
# public 스키마
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "SELECT 'public' as schema, COUNT(*) as count FROM public.exam_participants;"

# ai_vibe_coding_test 스키마
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "SELECT 'ai_vibe_coding_test' as schema, COUNT(*) as count FROM ai_vibe_coding_test.exam_participants;"
```

---

## 💾 데이터 삽입 방법

### ⚠️ 중요: Foreign Key 제약조건

`prompt_sessions` 테이블은 다음 Foreign Key를 가지고 있습니다:

```sql
FOREIGN KEY (exam_id, participant_id) 
REFERENCES ai_vibe_coding_test.exam_participants(exam_id, participant_id)
```

**따라서 `ai_vibe_coding_test.exam_participants`에 데이터가 있어야 합니다!**

### 1. 필요한 참조 데이터 먼저 삽입

```powershell
# SQL 파일로 한 번에 실행
Get-Content scripts/init-db.sql | docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test
```

### 2. 수동으로 테스트 데이터 삽입

```powershell
# 1단계: exams 테이블에 데이터 삽입
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "INSERT INTO ai_vibe_coding_test.exams (id, title, state, version) VALUES (1, '테스트 시험', 'WAITING', 1) ON CONFLICT (id) DO NOTHING;"

# 2단계: participants 테이블에 데이터 삽입
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "INSERT INTO ai_vibe_coding_test.participants (id, name) VALUES (1, '테스트 참가자') ON CONFLICT (id) DO NOTHING;"

# 3단계: problems 테이블에 데이터 삽입
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "INSERT INTO ai_vibe_coding_test.problems (id, title, difficulty, status) VALUES (1, '테스트 문제', 'MEDIUM', 'PUBLISHED') ON CONFLICT (id) DO NOTHING;"

# 4단계: problem_specs 테이블에 데이터 삽입
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "INSERT INTO ai_vibe_coding_test.problem_specs (spec_id, problem_id, version, content_md) VALUES (10, 1, 1, '테스트 스펙') ON CONFLICT (spec_id) DO NOTHING;"

# 5단계: exam_participants 테이블에 데이터 삽입 (중요!)
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "INSERT INTO ai_vibe_coding_test.exam_participants (exam_id, participant_id, spec_id, state, token_limit, token_used) VALUES (1, 1, 10, 'REGISTERED', 20000, 0) ON CONFLICT (exam_id, participant_id) DO NOTHING;"
```

### 3. 확인

```powershell
# exam_participants 데이터 확인
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "SELECT * FROM ai_vibe_coding_test.exam_participants WHERE exam_id = 1 AND participant_id = 1;"
```

---

## 🎯 실전 예제: 테스트 데이터 준비

### 한 번에 실행하는 스크립트

```powershell
# PowerShell에서 실행
$sql = @"
SET search_path TO ai_vibe_coding_test, public;

-- 참조 테이블 생성 (없으면)
INSERT INTO exams (id, title, state, version) VALUES (1, '테스트 시험', 'WAITING', 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO participants (id, name) VALUES (1, '테스트 참가자') ON CONFLICT (id) DO NOTHING;
INSERT INTO problems (id, title, difficulty, status) VALUES (1, '테스트 문제', 'MEDIUM', 'PUBLISHED') ON CONFLICT (id) DO NOTHING;
INSERT INTO problem_specs (spec_id, problem_id, version, content_md) VALUES (10, 1, 1, '테스트 스펙') ON CONFLICT (spec_id) DO NOTHING;

-- exam_participants 삽입 (중요!)
INSERT INTO exam_participants (exam_id, participant_id, spec_id, state, token_limit, token_used) 
VALUES (1, 1, 10, 'REGISTERED', 20000, 0) 
ON CONFLICT (exam_id, participant_id) DO NOTHING;

-- 확인
SELECT 'exam_participants 데이터 확인' as info;
SELECT * FROM exam_participants WHERE exam_id = 1 AND participant_id = 1;
"@

$sql | docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test
```

---

## 📝 요약

### 스키마가 2개인 이유
- **`public`**: Spring Boot 기본 스키마
- **`ai_vibe_coding_test`**: Python/LangGraph 전용 스키마
- 같은 이름의 테이블(`exam_participants`)이 두 스키마에 모두 존재할 수 있음

### 테이블 확인
```powershell
# ai_vibe_coding_test 스키마의 테이블만 확인
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "SELECT tablename FROM pg_tables WHERE schemaname = 'ai_vibe_coding_test' ORDER BY tablename;"
```

### 데이터 확인
```powershell
# search_path 설정 후 조회 (스키마 명시 불필요)
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "SET search_path TO ai_vibe_coding_test; SELECT * FROM prompt_sessions LIMIT 5;"
```

### 데이터 삽입
```powershell
# search_path 설정 후 삽입 (스키마 명시 불필요)
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "SET search_path TO ai_vibe_coding_test; INSERT INTO exam_participants (...) VALUES (...);"
```

---

## DB 데이터 빠르게 보는 방법

### 방법 1: Adminer (웹 브라우저) - 가장 빠름!

#### 실행
```powershell
docker run -d --name adminer -p 8080:8080 --add-host=host.docker.internal:host-gateway adminer
```

#### 접속
1. 브라우저에서: **http://localhost:8080**
2. 로그인 정보 입력:
   ```
   시스템: PostgreSQL
   서버: host.docker.internal:5435
   사용자명: postgres
   비밀번호: postgres
   데이터베이스: ai_vibe_coding_test
   ```
3. 로그인 후 왼쪽에서 테이블 선택하면 데이터 보임!

#### 종료
```powershell
docker stop adminer
docker rm adminer
```

---

### 방법 2: DBeaver (GUI 프로그램) - 추천!

#### 다운로드
https://dbeaver.io/download/ (Community Edition)

#### 연결 설정
```
Host: localhost
Port: 5435
Database: ai_vibe_coding_test
Username: postgres
Password: postgres
```

#### 스키마 선택
- 왼쪽 트리: `ai_vibe_coding_test` → `Schemas` → `ai_vibe_coding_test`
- 테이블 더블클릭하면 데이터 보임!

#### 상세 설정 가이드

1. **새 연결 생성**
   - 상단 메뉴: `Database` → `New Database Connection`
   - 또는 왼쪽 상단 `+` 버튼 클릭

2. **PostgreSQL 선택**
   - 데이터베이스 목록에서 `PostgreSQL` 선택
   - `Next` 클릭

3. **연결 정보 입력**
   ```
   Host: localhost
   Port: 5435
   Database: ai_vibe_coding_test
   Username: postgres
   Password: postgres
   ```
   
   - **중요**: `Show all databases` 체크 해제
   - `Test Connection` 클릭하여 연결 테스트
   - 성공하면 `Finish` 클릭

4. **스키마 선택**
   - 연결 후 왼쪽 트리에서:
     - `ai_vibe_coding_test` → `Schemas` → `ai_vibe_coding_test` 선택
   - 또는 SQL 편집기에서:
     ```sql
     SET search_path TO ai_vibe_coding_test;
     ```

5. **데이터 조회**
   - 왼쪽 트리: `ai_vibe_coding_test` → `Schemas` → `ai_vibe_coding_test` → `Tables`
   - 테이블 더블클릭하면 데이터 자동 조회

---

### 방법 3: 명령어 (터미널)

```powershell
# Docker 컨테이너 내부에서 psql 실행
docker exec -it ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test

# 또는 한 줄 명령어로 실행
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "SELECT * FROM prompt_sessions LIMIT 5;"
```

#### 주요 명령어

```sql
-- 스키마 설정
SET search_path TO ai_vibe_coding_test;

-- 테이블 목록 보기
\dt

-- 특정 테이블 구조 보기
\d prompt_sessions

-- 데이터 조회
SELECT * FROM prompt_sessions LIMIT 10;

-- 종료
\q
```

---

## 로컬 PostgreSQL 연결

### 환경 설정

#### .env 파일 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 설정을 추가하세요:

```env
# PostgreSQL 설정
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=ai_vibe_coding_test
```

**참고:**
- `POSTGRES_HOST`: 로컬 PostgreSQL 호스트 (기본값: `localhost`)
- `POSTGRES_PORT`: PostgreSQL 포트 (기본값: `5432`)
- `POSTGRES_USER`: PostgreSQL 사용자명 (기본값: `postgres`)
- `POSTGRES_PASSWORD`: PostgreSQL 비밀번호
- `POSTGRES_DB`: 데이터베이스 이름 (기본값: `ai_vibe_coding_test`)

#### 데이터베이스 생성

로컬 PostgreSQL에 데이터베이스를 생성하세요:

```bash
# PostgreSQL 접속
psql -U postgres

# 데이터베이스 생성
CREATE DATABASE ai_vibe_coding_test;

# 스키마 생성 (선택사항)
\c ai_vibe_coding_test
CREATE SCHEMA IF NOT EXISTS ai_vibe_coding_test;
```

---

## Docker에서 로컬 DB 연결

### 방법 1: Docker에서 로컬 DB 연결

Docker 컨테이너에서 호스트의 로컬 PostgreSQL에 직접 연결하는 방법입니다.

#### docker-compose.yml 수정

```yaml
services:
  ai_worker:
    # ... 기존 설정 ...
    environment:
      - POSTGRES_HOST=host.docker.internal  # Windows/Mac
      # 또는
      - POSTGRES_HOST=172.17.0.1  # Linux
      - POSTGRES_PORT=5432  # 로컬 PostgreSQL 포트
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=your_local_password
      - POSTGRES_DB=ai_vibe_coding_test
    extra_hosts:
      - "host.docker.internal:host-gateway"  # Windows/Mac용
```

#### .env 파일 수정

```env
# Docker 컨테이너에서 사용할 설정
POSTGRES_HOST=host.docker.internal  # 또는 172.17.0.1 (Linux)
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_local_password
POSTGRES_DB=ai_vibe_coding_test
```

---

## 스키마 상세 설명

### 스키마가 2개인 이유

PostgreSQL에서 **스키마(Schema)**는 데이터베이스 내의 논리적 네임스페이스입니다. 현재 프로젝트에서는 **2개의 스키마**를 사용하고 있습니다:

#### 1. `public` 스키마 (기본 스키마)
- **용도**: Spring Boot에서 관리하는 기본 테이블들
- **테이블 예시**: 
  - `exam_participants` (public 스키마)
  - `exams`
  - `participants`
  - `problems`
  - `problem_specs`

#### 2. `ai_vibe_coding_test` 스키마 (Python 전용)
- **용도**: Python/LangGraph에서 관리하는 테이블들
- **테이블 예시**:
  - `prompt_sessions`
  - `prompt_messages`
  - `prompt_evaluations`
  - `submissions`
  - `submission_runs`
  - `scores`
  - `exam_participants` (ai_vibe_coding_test 스키마에도 존재)

### 스키마 우선순위

`search_path`를 설정하면:
- `ai_vibe_coding_test` 스키마를 먼저 검색
- 없으면 `public` 스키마를 검색

```sql
SET search_path TO ai_vibe_coding_test, public;
-- 이제 exam_participants라고 하면 ai_vibe_coding_test.exam_participants를 먼저 찾음
```

### Python 코드에서의 스키마 처리

**파일**: `app/infrastructure/persistence/session.py`

```python
# 각 세션마다 search_path 설정
async def _set_search_path(session: AsyncSession):
    """세션마다 search_path 설정"""
    from sqlalchemy import text
    await session.execute(text("SET search_path TO ai_vibe_coding_test, public"))
```

이렇게 하면:
- Python 코드에서 `PromptSession`을 사용하면 자동으로 `ai_vibe_coding_test.prompt_sessions`를 찾음
- 스키마를 명시하지 않아도 됨

---

## PostgreSQL과 Redis 사용 현황

### PostgreSQL 사용 현황

**역할**: 영구 저장소 (Spring Boot와 테이블 공유)

**현재 사용 위치**:
- `app/infrastructure/persistence/session.py`: SQLAlchemy Async 세션 관리
- `app/infrastructure/persistence/models/`: Entity 모델 정의
  - `problems.py`: 문제 관련 (Problem, ProblemSpec)
  - `sessions.py`: 대화 세션 (PromptSession, PromptMessage)
  - `submissions.py`: 제출 관련 (Submission, SubmissionRun, Score)
  - `exams.py`: 시험 관련
  - `participants.py`: 참가자 관련

**연결 설정**:
```python
# app/core/config.py
POSTGRES_HOST=localhost  # Docker: postgres
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=ai_vibe_coding_test
```

### Redis 사용 현황

**역할**: 임시 상태 저장소 (LangGraph 상태, 세션 관리)

**현재 사용 위치**:
- `app/infrastructure/cache/redis_client.py`: Redis 클라이언트 래퍼

**저장되는 데이터**:

#### 1. LangGraph 상태
```
키: langgraph:state:{session_id}
값: MainGraphState (JSON)
TTL: 24시간 (86400초)
```

#### 2. 체크포인트
```
키: langgraph:checkpoint:{session_id}:{checkpoint_id}
값: 체크포인트 데이터 (JSON)
TTL: 24시간
```

#### 3. 활성 세션
```
키: session:active:{exam_id}:{participant_id}
값: session_id (문자열)
TTL: 24시간
```

#### 4. 턴별 평가 로그
```
키: turn_logs:{session_id}:{turn}
값: 턴 평가 로그 (JSON)
TTL: 24시간
```

#### 5. 턴-메시지 매핑
```
키: turn_mapping:{session_id}
값: {"1": {"start_msg_idx": 0, "end_msg_idx": 1}, ...}
TTL: 24시간
```

#### 6. Judge0 큐 (Redis Queue Adapter)
```
큐: judge_queue:pending (Redis List)
결과: judge_result:{task_id}
상태: judge_status:{task_id}
TTL: 24시간
```

**연결 설정**:
```python
# app/core/config.py
REDIS_HOST=localhost  # Docker: redis
REDIS_PORT=6379
REDIS_PASSWORD=None
REDIS_DB=0
```

### 데이터 흐름

#### 입력 → Redis → PostgreSQL

```
1. 사용자 메시지 도착
   ↓
2. LangGraph 실행 (Redis에 상태 저장)
   ↓
3. 평가 완료 후 PostgreSQL에 저장
   - prompt_sessions
   - prompt_messages
   - submissions
   - scores
```

### Redis vs PostgreSQL 역할 분리

| 항목 | Redis | PostgreSQL |
|------|-------|------------|
| **LangGraph State** | ✅ 저장 | ❌ 저장 안 함 |
| **턴 평가 로그** | ✅ 임시 저장 | ✅ 영구 저장 (prompt_evaluations) |
| **대화 메시지** | ✅ 임시 (State 내) | ✅ 영구 저장 |
| **제출 코드** | ❌ 저장 안 함 | ✅ 영구 저장 |
| **점수** | ✅ 임시 (State 내) | ✅ 영구 저장 |
| **Judge0 큐** | ✅ 큐 관리 | ❌ 저장 안 함 |

---

## 🔗 관련 문서

- [Database Changes Summary](./Database_Changes_Summary.md) - DB 변경사항
- [Test Execution Guide](./Test_Execution_Guide.md) - 테스트 실행 가이드

