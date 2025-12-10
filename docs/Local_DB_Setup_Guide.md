# 로컬 PostgreSQL 초기 설정 가이드 (Spring Boot Backend용)

## 📋 개요

데이터 없이 스키마만 생성하여 Spring Boot Backend가 사용할 수 있도록 로컬 PostgreSQL을 설정합니다.

## 🚀 빠른 시작

### 방법 1: 자동 스크립트 사용 (권장)

```powershell
# 기본 설정으로 실행 (postgres/postgres 관리자 사용)
.\scripts\setup_local_db.ps1

# 또는 관리자 비밀번호 지정
.\scripts\setup_local_db.ps1 -AdminPassword "your_admin_password"
```

### 방법 2: 수동 설정

#### 1단계: 데이터베이스 및 사용자 생성

```powershell
# PostgreSQL 관리자로 접속
psql -U postgres
```

```sql
-- 데이터베이스 생성
CREATE DATABASE ai_vibe_coding_test;

-- 사용자 생성 (Spring Boot 설정에 맞춤)
CREATE USER "user" WITH PASSWORD 'user123';

-- 권한 부여
GRANT ALL PRIVILEGES ON DATABASE ai_vibe_coding_test TO "user";
```

#### 2단계: 스키마 생성

```powershell
# init-db.sql 실행
psql -U postgres -d ai_vibe_coding_test -f scripts/init-db.sql
```

#### 3단계: 스키마 권한 부여

```sql
-- ai_vibe_coding_test 데이터베이스에 접속
\c ai_vibe_coding_test

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

## ⚙️ Spring Boot 설정

### application.yml

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/ai_vibe_coding_test
    username: user
    password: user123
    driver-class-name: org.postgresql.Driver
  jpa:
    hibernate:
      ddl-auto: update  # 또는 validate (스키마는 init-db.sql로 관리)
    show-sql: false
    properties:
      hibernate:
        dialect: org.hibernate.dialect.PostgreSQLDialect
        format_sql: true
        default_schema: ai_vibe_coding_test  # 스키마 지정
```

### application.properties (대안)

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

## ✅ 확인

### 1. 연결 테스트

```powershell
# PostgreSQL 직접 연결 테스트
psql -h localhost -p 5432 -U user -d ai_vibe_coding_test
# 비밀번호: user123
```

### 2. 스키마 및 테이블 확인

```sql
-- 스키마 목록 확인
\dn

-- 테이블 목록 확인
\dt ai_vibe_coding_test.*

-- 특정 테이블 구조 확인
\d ai_vibe_coding_test.prompt_sessions
```

### 3. Spring Boot 연결 테스트

Spring Boot 애플리케이션을 실행하여 연결이 정상적으로 되는지 확인합니다.

## 🔧 Python/FastAPI 설정 (참고)

로컬 DB를 사용하려면 `.env` 파일도 수정:

```env
# PostgreSQL 설정 (로컬 DB)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=user
POSTGRES_PASSWORD=user123
POSTGRES_DB=ai_vibe_coding_test
```

## 📝 주의사항

1. **포트 충돌**: 로컬 PostgreSQL이 기본 포트 5432를 사용하는지 확인
2. **권한 문제**: `user` 사용자에게 충분한 권한 부여 확인
3. **스키마 이름**: `ai_vibe_coding_test` 스키마 사용 확인
4. **Spring Boot JPA**: `ddl-auto: update` 사용 시 테이블 자동 생성됨 (주의)
5. **사용자 이름**: Spring Boot 설정에서 `user`는 따옴표 필요 (`"user"`)

## 🐛 문제 해결

### 사용자 생성 오류

```sql
-- 사용자가 이미 존재하는 경우
DROP USER IF EXISTS "user";
CREATE USER "user" WITH PASSWORD 'user123';
```

### 권한 오류

```sql
-- 권한 재부여
GRANT ALL PRIVILEGES ON DATABASE ai_vibe_coding_test TO "user";
\c ai_vibe_coding_test
GRANT ALL ON SCHEMA ai_vibe_coding_test TO "user";
```

### 스키마가 없는 경우

```sql
-- 스키마 수동 생성
CREATE SCHEMA IF NOT EXISTS ai_vibe_coding_test;
GRANT ALL ON SCHEMA ai_vibe_coding_test TO "user";
```

## 📚 관련 문서

- [init-db.sql](../scripts/init-db.sql) - 스키마 초기화 스크립트
- [Local_DB_Migration_Guide.md](./Local_DB_Migration_Guide.md) - 데이터 마이그레이션 가이드








