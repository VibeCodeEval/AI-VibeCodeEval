# DB 설정 가이드

> **최종 통합일**: 2026-03-27 | **원본**: Complete_DB_Setup_Guide.md, Local_DB_Setup_Guide.md, Local_DB_Migration_Guide.md, Quick_DB_Guide.md

---

## 목차

1. [빠른 참조](#1-빠른-참조)
2. [전체 설정: PostgreSQL(로컬) + Redis(Docker) + Backend](#2-전체-설정-postgresql로컬--redisdocker--backend)
3. [로컬 PostgreSQL: 스키마만 (Spring Boot)](#3-로컬-postgresql-스키마만-spring-boot)
4. [Docker PostgreSQL → 로컬 마이그레이션](#4-docker-postgresql--로컬-마이그레이션)

---

## 1. 빠른 참조

### 1.1 구성 한눈에

| 구성 요소 | 방식 | 주소·포트 |
|-----------|------|-----------|
| PostgreSQL | 로컬 설치 | `localhost:5432` |
| Redis | Docker Compose (`docker-compose.dev.yml`) | `localhost:6379` |
| Docker에서 쓰던 PostgreSQL(마이그레이션 원본) | 예시 | `localhost:5435` |

- **DB 이름**: `ai_vibe_coding_test`
- **앱 사용자**: `user` / `user123` (SQL에서는 `"user"`로 따옴표)

### 1.2 스키마 사용 정책

PostgreSQL **스키마**는 테이블을 묶는 논리 공간입니다.

```
데이터베이스: ai_vibe_coding_test
└── ai_vibe_coding_test 스키마 (다수 테이블) ← Python/LangGraph·앱 코드 기준
```

- **`ai_vibe_coding_test` 스키마**: **BE(Spring Boot)와 AI 서버(Python/LangGraph) 모두 이 스키마를 사용**. 두 서버가 동일한 데이터를 공유.
- **`public`**: 이 프로젝트 흐름에서는 **사용하지 않음** (2026-04-09 이전에는 BE가 `public`에 썼으나 수정됨).

BE는 `application-secret.yml`에 `hibernate.default_schema: ai_vibe_coding_test`를 설정해 Hibernate가 `ai_vibe_coding_test` 스키마를 사용하도록 강제합니다. AI 서버는 세션마다 `SET search_path TO ai_vibe_coding_test`를 실행합니다(§3 참고).

### 1.3 테이블·데이터 확인 (Docker PG vs 로컬 PG)

**Docker 컨테이너 `ai_vibe_postgres_dev`가 있을 때** (Quick 가이드와 동일):

```powershell
# public / ai_vibe_coding_test 테이블 목록
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "SELECT schemaname, tablename FROM pg_tables WHERE schemaname IN ('public', 'ai_vibe_coding_test') ORDER BY schemaname, tablename;"

# 특정 테이블이 어느 스키마에 있는지
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "SELECT schemaname, tablename FROM pg_tables WHERE tablename = 'exam_participants';"

# ai_vibe_coding_test 스키마만
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "SELECT tablename FROM pg_tables WHERE schemaname = 'ai_vibe_coding_test' ORDER BY tablename;"
```

**로컬 PostgreSQL만 쓸 때**는 컨테이너 대신:

```powershell
psql -h localhost -p 5432 -U user -d ai_vibe_coding_test -c "SELECT tablename FROM pg_tables WHERE schemaname = 'ai_vibe_coding_test' ORDER BY tablename;"
```

(psql 안에서 `\dn`, `\dt ai_vibe_coding_test.*`, `\d ai_vibe_coding_test.prompt_sessions` 도 동일하게 사용 가능합니다.)

### 1.4 Foreign Key·데이터 삽입 시 주의

`prompt_sessions`는 다음 FK를 가집니다.

```sql
FOREIGN KEY (exam_id, participant_id)
REFERENCES ai_vibe_coding_test.exam_participants(exam_id, participant_id)
```

따라서 **`ai_vibe_coding_test.exam_participants`에 행이 있어야** `prompt_sessions` 등을 넣을 수 있습니다.

**Docker PG에서 `init-db.sql` 적용 예:**

```powershell
Get-Content scripts/init-db.sql | docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test
```

**로컬 PG:**

```powershell
psql -U postgres -d ai_vibe_coding_test -f scripts/init-db.sql
```

수동 삽입 예시는 Docker 기준이며, 로컬에서는 `docker exec ... psql` 대신 `psql -h localhost -p 5432 -U postgres -d ai_vibe_coding_test -c "..."` 형태로 치환하면 됩니다.

### 1.5 search_path·요약 명령

```powershell
# Docker: search_path 후 조회
docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test -c "SET search_path TO ai_vibe_coding_test; SELECT * FROM prompt_sessions LIMIT 5;"
```

한 번에 실행하는 PowerShell here-string 예시(컨테이너 기준):

```powershell
$sql = @"
SET search_path TO ai_vibe_coding_test, public;
INSERT INTO exams (id, title, state, version) VALUES (1, '테스트 시험', 'WAITING', 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO participants (id, name) VALUES (1, '테스트 참가자') ON CONFLICT (id) DO NOTHING;
INSERT INTO problems (id, title, difficulty, status) VALUES (1, '테스트 문제', 'MEDIUM', 'PUBLISHED') ON CONFLICT (id) DO NOTHING;
INSERT INTO problem_specs (spec_id, problem_id, version, content_md) VALUES (10, 1, 1, '테스트 스펙') ON CONFLICT (spec_id) DO NOTHING;
INSERT INTO exam_participants (exam_id, participant_id, spec_id, state, token_limit, token_used)
VALUES (1, 1, 10, 'REGISTERED', 20000, 0) ON CONFLICT (exam_id, participant_id) DO NOTHING;
SELECT * FROM exam_participants WHERE exam_id = 1 AND participant_id = 1;
"@
$sql | docker exec -i ai_vibe_postgres_dev psql -U postgres -d ai_vibe_coding_test
```

### 1.6 최소 체크리스트

- [ ] 로컬 PostgreSQL 동작(또는 Docker PG 원본) 확인
- [ ] DB `ai_vibe_coding_test`·사용자 `user`·스키마 `ai_vibe_coding_test` 권한
- [ ] Redis 컨테이너 기동 및 `PONG`
- [ ] Backend `application.yml`(또는 환경 변수)·Python `.env`의 호스트/포트 일치
- [ ] 테이블 목록·필요 시 샘플 데이터(FK 순서) 확인

### 1.7 관련 문서(빠른 링크)

- [Database Schema Explanation](./Database_Schema_Explanation.md)
- [Database Changes Summary](./Database_Changes_Summary.md)
- [Test Execution Guide](./Test_Execution_Guide.md)
- [Backend Docker · DB](./Backend_Docker_And_DB_Guide.md) (Spring / Compose / FastAPI)

---

## 2. 전체 설정: PostgreSQL(로컬) + Redis(Docker) + Backend

로컬 PostgreSQL과 Docker Redis를 함께 쓰는 기본 흐름입니다.

### 2.1 로컬 PostgreSQL

**설치·서비스 확인**

```powershell
psql --version
Get-Service -Name postgresql*
```

**DB·사용자·스키마·권한**

```powershell
psql -U postgres
```

```sql
CREATE DATABASE ai_vibe_coding_test;

CREATE USER "user" WITH PASSWORD 'user123';

GRANT ALL PRIVILEGES ON DATABASE ai_vibe_coding_test TO "user";

\c ai_vibe_coding_test

CREATE SCHEMA IF NOT EXISTS ai_vibe_coding_test;

GRANT ALL ON SCHEMA ai_vibe_coding_test TO "user";
GRANT ALL ON ALL TABLES IN SCHEMA ai_vibe_coding_test TO "user";
GRANT ALL ON ALL SEQUENCES IN SCHEMA ai_vibe_coding_test TO "user";
GRANT ALL ON ALL FUNCTIONS IN SCHEMA ai_vibe_coding_test TO "user";

ALTER DEFAULT PRIVILEGES IN SCHEMA ai_vibe_coding_test
GRANT ALL ON TABLES TO "user";
ALTER DEFAULT PRIVILEGES IN SCHEMA ai_vibe_coding_test
GRANT ALL ON SEQUENCES TO "user";
ALTER DEFAULT PRIVILEGES IN SCHEMA ai_vibe_coding_test
GRANT ALL ON FUNCTIONS TO "user";
```

**연결 테스트**

```powershell
psql -h localhost -p 5432 -U user -d ai_vibe_coding_test
# 비밀번호: user123
```

### 2.2 Docker Redis

```powershell
docker-compose -f docker-compose.dev.yml up -d redis
```

```powershell
docker ps --filter "name=ai_vibe_redis_dev"
docker exec -it ai_vibe_redis_dev redis-cli ping
# PONG
```

### 2.3 Backend 설정

**로컬에서 Spring Boot 실행(기본)**

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/ai_vibe_coding_test
    username: user
    password: user123
    driver-class-name: org.postgresql.Driver
  jpa:
    hibernate:
      ddl-auto: update
    show-sql: false
    properties:
      hibernate:
        dialect: org.hibernate.dialect.PostgreSQLDialect
        format_sql: true
        default_schema: ai_vibe_coding_test   # AI 서버와 동일한 스키마 사용 (필수)
  redis:
    host: localhost
    port: 6379
```

**Docker에서 Backend 실행 — 환경 변수(권장)**

`application.yml` 예:

```yaml
spring:
  datasource:
    url: ${SPRING_DATASOURCE_URL:jdbc:postgresql://localhost:5432/ai_vibe_coding_test}
    username: ${SPRING_DATASOURCE_USERNAME:user}
    password: ${SPRING_DATASOURCE_PASSWORD:user123}
    driver-class-name: ${SPRING_DATASOURCE_DRIVER-CLASS-NAME:org.postgresql.Driver}
  jpa:
    hibernate:
      ddl-auto: ${SPRING_JPA_HIBERNATE_DDL-AUTO:update}
    show-sql: ${SPRING_JPA_SHOW-SQL:false}
    properties:
      hibernate:
        dialect: ${SPRING_JPA_PROPERTIES_HIBERNATE_DIALECT:org.hibernate.dialect.PostgreSQLDialect}
        format_sql: ${SPRING_JPA_PROPERTIES_HIBERNATE_FORMAT_SQL:true}
  redis:
    host: ${SPRING_REDIS_HOST:localhost}
    port: ${SPRING_REDIS_PORT:6379}
```

`docker-compose.yml` (Backend) 예시:

```yaml
version: '3.8'

services:
  spring_boot:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ai_vibe_spring
    environment:
      - SPRING_DATASOURCE_URL=jdbc:postgresql://host.docker.internal:5432/ai_vibe_coding_test
      - SPRING_DATASOURCE_USERNAME=user
      - SPRING_DATASOURCE_PASSWORD=user123
      - SPRING_REDIS_HOST=host.docker.internal
      - SPRING_REDIS_PORT=6379
    ports:
      - "8080:8080"
    restart: unless-stopped
```

- Windows/Mac: DB·Redis는 `host.docker.internal`
- Linux: `172.17.0.1` 등 호스트 게이트웨이 또는 `--network host` 검토

**같은 Compose 네트워크에 Redis가 있을 때** (`docker-compose.dev.yml`에 Backend 추가하는 경우):

```yaml
  spring_boot:
    build:
      context: ../spring-backend
      dockerfile: Dockerfile
    container_name: ai_vibe_spring_dev
    environment:
      - SPRING_DATASOURCE_URL=jdbc:postgresql://host.docker.internal:5432/ai_vibe_coding_test
      - SPRING_DATASOURCE_USERNAME=user
      - SPRING_DATASOURCE_PASSWORD=user123
      - SPRING_REDIS_HOST=redis
      - SPRING_REDIS_PORT=6379
    ports:
      - "8080:8080"
    depends_on:
      - redis
    restart: unless-stopped
```

### 2.4 로컬 실행 ↔ Docker 실행 비교

| 항목 | 로컬 실행 | Docker(Backend 컨테이너) |
|------|-----------|---------------------------|
| PostgreSQL URL | `localhost:5432` | `host.docker.internal:5432`(Win/Mac) 또는 `172.17.0.1:5432`(Linux) |
| Redis | `localhost` | `host.docker.internal` / `172.17.0.1` 또는 서비스명 `redis` |

`application.yml`만 바꿀 때 예:

```yaml
# 로컬
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/ai_vibe_coding_test
  redis:
    host: localhost

# 컨테이너에서 호스트 PG/Redis
spring:
  datasource:
    url: jdbc:postgresql://host.docker.internal:5432/ai_vibe_coding_test
  redis:
    host: host.docker.internal
```

### 2.5 전체 실행 순서

1. **PostgreSQL**  
   `Start-Service postgresql-x64-15` (설치 버전에 맞게) 후 `psql -h localhost -p 5432 -U user -d ai_vibe_coding_test`

2. **Redis**  
   `docker-compose -f docker-compose.dev.yml up -d redis` → `docker exec -it ai_vibe_redis_dev redis-cli ping`

3. **Backend**  
   - 로컬: `./mvnw spring-boot:run` 또는 `java -jar target/backend-0.0.1-SNAPSHOT.jar`  
   - Docker: `docker-compose up -d spring_boot` 또는 dev Compose에 맞게 `up -d spring_boot`

4. **확인**  
   `docker logs -f ai_vibe_spring`  
   `psql ... -c "\dt"`  
   `docker exec -it ai_vibe_redis_dev redis-cli` → `KEYS *`

### 2.6 문제 해결

**컨테이너에서 `localhost`로 PG 접속 불가**

```yaml
# Windows/Mac
url: jdbc:postgresql://host.docker.internal:5432/ai_vibe_coding_test
# Linux
url: jdbc:postgresql://172.17.0.1:5432/ai_vibe_coding_test
```

**Redis 연결 실패**

- 같은 Compose: `host: redis`
- 호스트의 Redis: `host: host.docker.internal`(Win/Mac)

**`user` 권한 오류**

```sql
\c ai_vibe_coding_test
GRANT ALL ON SCHEMA ai_vibe_coding_test TO "user";
ALTER DEFAULT PRIVILEGES IN SCHEMA ai_vibe_coding_test
GRANT ALL ON TABLES TO "user";
```

### 2.7 관련 파일

- `docker-compose.dev.yml` — Redis, Adminer 등
- `scripts/init-db.sql` — 스키마 초기화(참고·적용용)

### 2.8 체크리스트(전체 스택)

- [ ] 로컬 PostgreSQL 설치·실행
- [ ] DB·사용자·스키마·권한(§2.1)
- [ ] Docker Redis 기동·`PONG`
- [ ] `application.yml` / 환경 변수
- [ ] Backend 기동 후 테이블 생성·연결 확인
- [ ] PG 테이블·Redis 키 확인

---

## 3. 로컬 PostgreSQL: 스키마만 (Spring Boot)

데이터 없이 **스키마만** 맞추고 Spring Boot가 붙도록 할 때의 절차입니다. DB·사용자·권한 SQL은 §2.1과 동일합니다. 여기서는 **init-db·JPA 스키마 지정**을 덧붙입니다.

### 3.1 자동 스크립트(권장)

```powershell
.\scripts\setup_local_db.ps1
.\scripts\setup_local_db.ps1 -AdminPassword "your_admin_password"
```

### 3.2 수동: DB·사용자·권한 후 init-db

1. **§2.1**에서 `CREATE DATABASE`·`CREATE USER`·스키마·`GRANT`·`ALTER DEFAULT PRIVILEGES`까지 완료합니다.
2. 스키마 객체를 SQL로 채웁니다.

```powershell
psql -U postgres -d ai_vibe_coding_test -f scripts/init-db.sql
```

`init-db.sql`이 스키마·테이블을 만들면, §2.1에서 이미 부여한 기본 권한으로 이후 객체도 커버되는지 환경에 따라 확인합니다. 권한 오류가 나면 §2.6·§3.7을 참고합니다.

### 3.3 Spring Boot: 스키마 명시

`application.yml`:

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/ai_vibe_coding_test
    username: user
    password: user123
    driver-class-name: org.postgresql.Driver
  jpa:
    hibernate:
      ddl-auto: update
    show-sql: false
    properties:
      hibernate:
        dialect: org.hibernate.dialect.PostgreSQLDialect
        format_sql: true
        default_schema: ai_vibe_coding_test
```

`application.properties` 대안:

```properties
spring.datasource.url=jdbc:postgresql://localhost:5432/ai_vibe_coding_test
spring.datasource.username=user
spring.datasource.password=user123
spring.datasource.driver-class-name=org.postgresql.Driver
spring.jpa.hibernate.ddl-auto=update
spring.jpa.show-sql=false
spring.jpa.properties.hibernate.dialect=org.hibernate.dialect.PostgreSQLDialect
spring.jpa.properties.hibernate.format_sql=true
spring.jpa.properties.hibernate.default_schema=ai_vibe_coding_test
```

### 3.4 Python/FastAPI `.env` (로컬 DB)

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=user
POSTGRES_PASSWORD=user123
POSTGRES_DB=ai_vibe_coding_test
```

### 3.5 확인

```powershell
psql -h localhost -p 5432 -U user -d ai_vibe_coding_test
```

```sql
\dn
\dt ai_vibe_coding_test.*
\d ai_vibe_coding_test.prompt_sessions
```

Spring Boot를 띄워 연결을 확인합니다.

### 3.6 주의사항

1. 포트 **5432** 충돌 여부  
2. `user` 권한·스키마 이름 `ai_vibe_coding_test`  
3. `ddl-auto: update`는 테이블 자동 변경이 일어남 — 운영 정책에 맞게 `validate` 등 검토  
4. PostgreSQL에서 로그인 사용자명 `user`는 `"user"`로 생성

### 3.7 문제 해결

**사용자 이미 존재**

```sql
DROP USER IF EXISTS "user";
CREATE USER "user" WITH PASSWORD 'user123';
```

**스키마 없음**

```sql
CREATE SCHEMA IF NOT EXISTS ai_vibe_coding_test;
GRANT ALL ON SCHEMA ai_vibe_coding_test TO "user";
```

---

## 4. Docker PostgreSQL → 로컬 마이그레이션

Docker로 띄운 PostgreSQL(예: 호스트 포트 **5435**)에서 **로컬 5432**로 옮기는 절차입니다.

### 4.1 사전 준비

- §2.1 또는 §3에 따라 **로컬**에 DB·사용자·스키마·권한이 갖춰져 있어야 합니다.
- Docker 쪽 접속 정보(호스트·포트·사용자·비밀번호)는 환경에 맞게 조정합니다. 아래 예는 `localhost:5435`, 사용자 `postgres` / 비밀번호 `postgres` 입니다.

### 4.2 방법 1: `pg_dump` + `pg_restore` (권장)

```powershell
$env:PGPASSWORD = "postgres"
pg_dump -h localhost -p 5435 -U postgres -d ai_vibe_coding_test `
    --schema=ai_vibe_coding_test `
    --format=custom `
    -f ai_vibe_coding_test_backup.dump

$env:PGPASSWORD = "user123"
pg_restore -h localhost -p 5432 -U user -d ai_vibe_coding_test `
    --schema=ai_vibe_coding_test `
    ai_vibe_coding_test_backup.dump
```

### 4.3 방법 2: 평문 SQL 덤프

```powershell
$env:PGPASSWORD = "postgres"
pg_dump -h localhost -p 5435 -U postgres -d ai_vibe_coding_test `
    --schema=ai_vibe_coding_test `
    --format=plain `
    -f ai_vibe_coding_test_backup.sql

$env:PGPASSWORD = "user123"
psql -h localhost -p 5432 -U user -d ai_vibe_coding_test -f ai_vibe_coding_test_backup.sql
```

### 4.4 방법 3: 데이터 없이 스키마만 (`init-db.sql`)

```powershell
$env:PGPASSWORD = "user123"
psql -h localhost -p 5432 -U user -d ai_vibe_coding_test -f scripts/init-db.sql
```

### 4.5 애플리케이션 설정

마이그레이션 후 로컬을 쓰도록 **`.env`** 및 **`application.yml`**은 §3.3·§3.4와 같게 맞춥니다(요약: `localhost:5432`, 사용자 `user`).

### 4.6 마이그레이션 확인

```powershell
python -c "from app.core.config import settings; print(settings.POSTGRES_URL)"
psql -h localhost -p 5432 -U user -d ai_vibe_coding_test
```

```sql
\dn
\dt ai_vibe_coding_test.*
\d ai_vibe_coding_test.prompt_sessions
SELECT COUNT(*) FROM ai_vibe_coding_test.prompt_sessions;
SELECT COUNT(*) FROM ai_vibe_coding_test.submissions;
```

### 4.7 롤백(Docker로 되돌리기)

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5435
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

(Spring·기타 구성도 Docker PG에 맞게 되돌립니다.)

### 4.8 주의사항

- 마이그레이션 전 **백업**  
- 포트·권한·스키마 이름 일관성  
- `ddl-auto: update`와 덤프 복원 순서·정책 충돌 여부 검토

### 4.9 자동화 스크립트 예시 (`scripts/migrate_docker_to_local.ps1`)

아래는 평문 SQL 덤프 후 로컬 `psql`로 복원하는 예시입니다. 실제 파일로 두고 실행해도 되고, 내용만 참고해도 됩니다.

```powershell
param(
    [string]$DockerHost = "localhost",
    [int]$DockerPort = 5435,
    [string]$DockerUser = "postgres",
    [string]$DockerPassword = "postgres",
    [string]$LocalHost = "localhost",
    [int]$LocalPort = 5432,
    [string]$LocalUser = "user",
    [string]$LocalPassword = "user123",
    [string]$DbName = "ai_vibe_coding_test",
    [string]$Schema = "ai_vibe_coding_test"
)

$ErrorActionPreference = "Stop"

Write-Host "Docker PostgreSQL → Local PostgreSQL 마이그레이션" -ForegroundColor Cyan

$dumpFile = "ai_vibe_coding_test_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"
$env:PGPASSWORD = $DockerPassword
pg_dump -h $DockerHost -p $DockerPort -U $DockerUser -d $DbName `
    --schema=$Schema --format=plain -f $dumpFile
if ($LASTEXITCODE -ne 0) { Write-Host "덤프 실패"; exit 1 }

$env:PGPASSWORD = $LocalPassword
psql -h $LocalHost -p $LocalPort -U $LocalUser -d $DbName -f $dumpFile
if ($LASTEXITCODE -ne 0) { Write-Host "복원 실패"; exit 1 }

psql -h $LocalHost -p $LocalPort -U $LocalUser -d $DbName -c "SELECT table_name FROM information_schema.tables WHERE table_schema = '$Schema' ORDER BY table_name;"

Write-Host "완료. 덤프: $dumpFile"
Write-Host "다음: .env 의 POSTGRES_PORT=5432, Spring 설정 확인"
```

---

## 부록: 관련 스크립트·문서

| 항목 | 경로 |
|------|------|
| 로컬 DB 설정 스크립트 | `scripts/setup_local_db.ps1` |
| 스키마 초기화 SQL | `scripts/init-db.sql` |
| 스키마·FK·운영 참고 | §1, [Database_Schema_Explanation](./Database_Schema_Explanation.md) |
