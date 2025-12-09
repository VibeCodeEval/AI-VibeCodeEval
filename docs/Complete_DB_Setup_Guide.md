# 전체 DB 실행 가이드

## 📋 개요

로컬 PostgreSQL과 Docker Redis를 사용하는 환경 설정 가이드입니다.

## 🗄️ 데이터베이스 구성

- **PostgreSQL**: 로컬 설치 (localhost:5432)
- **Redis**: Docker Compose로 실행 (localhost:6379)

## 🚀 1단계: 로컬 PostgreSQL 설정

### 1.1 PostgreSQL 설치 확인

```powershell
# PostgreSQL 버전 확인
psql --version

# PostgreSQL 서비스 상태 확인
Get-Service -Name postgresql*
```

### 1.2 데이터베이스 및 사용자 생성

```powershell
# PostgreSQL 관리자로 접속
psql -U postgres
```

```sql
-- 데이터베이스 생성
CREATE DATABASE ai_vibe_coding_test;

-- 사용자 생성 (Backend 설정에 맞춤)
CREATE USER "user" WITH PASSWORD 'user123';

-- 권한 부여
GRANT ALL PRIVILEGES ON DATABASE ai_vibe_coding_test TO "user";

-- 데이터베이스에 접속하여 스키마 권한 부여
\c ai_vibe_coding_test

-- 스키마 생성 (없으면)
CREATE SCHEMA IF NOT EXISTS ai_vibe_coding_test;

-- 스키마 권한 부여
GRANT ALL ON SCHEMA ai_vibe_coding_test TO "user";
GRANT ALL ON ALL TABLES IN SCHEMA ai_vibe_coding_test TO "user";
GRANT ALL ON ALL SEQUENCES IN SCHEMA ai_vibe_coding_test TO "user";
GRANT ALL ON ALL FUNCTIONS IN SCHEMA ai_vibe_coding_test TO "user";

-- 앞으로 생성되는 테이블에도 자동 권한 부여
ALTER DEFAULT PRIVILEGES IN SCHEMA ai_vibe_coding_test 
GRANT ALL ON TABLES TO "user";
ALTER DEFAULT PRIVILEGES IN SCHEMA ai_vibe_coding_test 
GRANT ALL ON SEQUENCES TO "user";
ALTER DEFAULT PRIVILEGES IN SCHEMA ai_vibe_coding_test 
GRANT ALL ON FUNCTIONS TO "user";
```

### 1.3 연결 테스트

```powershell
# 사용자로 접속 테스트
psql -h localhost -p 5432 -U user -d ai_vibe_coding_test
# 비밀번호: user123
```

## 🐳 2단계: Docker Redis 실행

### 2.1 Redis 실행

```powershell
# docker-compose.dev.yml로 Redis만 실행
docker-compose -f docker-compose.dev.yml up -d redis
```

### 2.2 Redis 확인

```powershell
# Redis 컨테이너 상태 확인
docker ps --filter "name=ai_vibe_redis_dev"

# Redis 연결 테스트
docker exec -it ai_vibe_redis_dev redis-cli ping
# 응답: PONG
```

## 🔧 3단계: Backend 설정

### 3.1 로컬에서 실행하는 경우 (기본 설정)

**application.yml:**
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
  redis:
    host: localhost
    port: 6379
```

### 3.2 Docker로 실행하는 경우

#### 방법 1: 환경 변수 사용 (권장)

**application.yml:**
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

**docker-compose.yml (Backend):**
```yaml
version: '3.8'

services:
  spring_boot:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ai_vibe_spring
    environment:
      # PostgreSQL: 로컬 DB 접근 (Windows/Mac)
      - SPRING_DATASOURCE_URL=jdbc:postgresql://host.docker.internal:5432/ai_vibe_coding_test
      # Linux의 경우: jdbc:postgresql://172.17.0.1:5432/ai_vibe_coding_test
      - SPRING_DATASOURCE_USERNAME=user
      - SPRING_DATASOURCE_PASSWORD=user123
      # Redis: 호스트의 Redis 접근
      - SPRING_REDIS_HOST=host.docker.internal  # Windows/Mac
      # Linux의 경우: 172.17.0.1
      - SPRING_REDIS_PORT=6379
    ports:
      - "8080:8080"
    restart: unless-stopped
```

#### 방법 2: 같은 Docker Compose 네트워크 사용

**docker-compose.dev.yml에 Backend 추가:**
```yaml
version: '3.8'

services:
  # Redis
  redis:
    image: redis:7-alpine
    container_name: ai_vibe_redis_dev
    ports:
      - "6379:6379"
    # ... 기존 설정 ...

  # Spring Boot Backend
  spring_boot:
    build:
      context: ../spring-backend  # Backend 프로젝트 경로
      dockerfile: Dockerfile
    container_name: ai_vibe_spring_dev
    environment:
      # PostgreSQL: 로컬 DB 접근
      - SPRING_DATASOURCE_URL=jdbc:postgresql://host.docker.internal:5432/ai_vibe_coding_test
      - SPRING_DATASOURCE_USERNAME=user
      - SPRING_DATASOURCE_PASSWORD=user123
      # Redis: 같은 네트워크의 redis 서비스
      - SPRING_REDIS_HOST=redis
      - SPRING_REDIS_PORT=6379
    ports:
      - "8080:8080"
    depends_on:
      - redis
    restart: unless-stopped
```

## 📝 설정 변경 요약

### 로컬 실행 → Docker 실행 변경

| 항목 | 로컬 실행 | Docker 실행 |
|------|----------|------------|
| **PostgreSQL URL** | `localhost:5432` | `host.docker.internal:5432` (Windows/Mac)<br>`172.17.0.1:5432` (Linux) |
| **Redis Host** | `localhost` | `host.docker.internal` (Windows/Mac)<br>`172.17.0.1` (Linux)<br>또는 `redis` (같은 네트워크) |

### application.yml 변경 예시

**변경 전 (로컬 실행):**
```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/ai_vibe_coding_test
  redis:
    host: localhost
```

**변경 후 (Docker 실행):**
```yaml
spring:
  datasource:
    url: jdbc:postgresql://host.docker.internal:5432/ai_vibe_coding_test
  redis:
    host: host.docker.internal
```

또는 환경 변수 사용:
```yaml
spring:
  datasource:
    url: ${SPRING_DATASOURCE_URL:jdbc:postgresql://localhost:5432/ai_vibe_coding_test}
  redis:
    host: ${SPRING_REDIS_HOST:localhost}
```

## 🚀 전체 실행 순서

### 1. PostgreSQL 확인

```powershell
# PostgreSQL 서비스 시작 (필요시)
Start-Service postgresql-x64-15  # 버전에 맞게 수정

# 연결 테스트
psql -h localhost -p 5432 -U user -d ai_vibe_coding_test
```

### 2. Redis 실행

```powershell
# Redis 실행
docker-compose -f docker-compose.dev.yml up -d redis

# 확인
docker ps --filter "name=redis"
docker exec -it ai_vibe_redis_dev redis-cli ping
```

### 3. Backend 실행

#### 로컬 실행:
```powershell
# Backend 프로젝트에서
./mvnw spring-boot:run
# 또는
java -jar target/backend-0.0.1-SNAPSHOT.jar
```

#### Docker 실행:
```powershell
# Backend 프로젝트에서
docker-compose up -d spring_boot

# 또는 docker-compose.dev.yml에 추가한 경우
docker-compose -f docker-compose.dev.yml up -d spring_boot
```

### 4. 확인

```powershell
# Backend 로그 확인
docker logs -f ai_vibe_spring

# PostgreSQL 테이블 확인
psql -h localhost -p 5432 -U user -d ai_vibe_coding_test -c "\dt"

# Redis 데이터 확인
docker exec -it ai_vibe_redis_dev redis-cli
> KEYS *
```

## 🔍 문제 해결

### PostgreSQL 연결 실패

**문제**: Docker에서 `localhost`로 접속 불가

**해결**:
- Windows/Mac: `host.docker.internal` 사용
- Linux: `172.17.0.1` 또는 `--network host` 사용

```yaml
# Windows/Mac
url: jdbc:postgresql://host.docker.internal:5432/ai_vibe_coding_test

# Linux
url: jdbc:postgresql://172.17.0.1:5432/ai_vibe_coding_test
```

### Redis 연결 실패

**문제**: Docker에서 `localhost`로 Redis 접속 불가

**해결**:
- 같은 네트워크 사용: `redis` (서비스 이름)
- 호스트 접근: `host.docker.internal` (Windows/Mac)

```yaml
# 같은 네트워크
host: redis

# 호스트 접근
host: host.docker.internal
```

### 권한 오류

**문제**: `user` 사용자가 테이블 생성 불가

**해결**:
```sql
-- 권한 재부여
\c ai_vibe_coding_test
GRANT ALL ON SCHEMA ai_vibe_coding_test TO "user";
ALTER DEFAULT PRIVILEGES IN SCHEMA ai_vibe_coding_test 
GRANT ALL ON TABLES TO "user";
```

## 📚 관련 파일

- `docker-compose.dev.yml` - Redis 및 Adminer 설정
- `scripts/init-db.sql` - 스키마 초기화 스크립트 (참고용)
- `docs/Backend_Docker_Setup_Guide.md` - Backend Docker 상세 가이드

## ✅ 체크리스트

- [ ] 로컬 PostgreSQL 설치 및 실행 확인
- [ ] 데이터베이스 `ai_vibe_coding_test` 생성
- [ ] 사용자 `user` 생성 및 권한 부여
- [ ] Docker Redis 실행 확인
- [ ] Backend application.yml 설정 확인
- [ ] Backend 실행 및 테이블 자동 생성 확인
- [ ] PostgreSQL 테이블 목록 확인
- [ ] Redis 연결 확인







