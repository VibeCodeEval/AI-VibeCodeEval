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

## 🔗 관련 문서

- [Database Schema Explanation](./Database_Schema_Explanation.md) - 상세 설명
- [Database Changes Summary](./Database_Changes_Summary.md) - DB 변경사항
- [Test Execution Guide](./Test_Execution_Guide.md) - 테스트 실행 가이드

