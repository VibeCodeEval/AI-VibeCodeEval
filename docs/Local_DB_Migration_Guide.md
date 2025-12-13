# Local DB 마이그레이션 가이드 (Spring Boot Backend용)

## 📋 개요

Docker PostgreSQL에서 로컬에 직접 설치된 PostgreSQL로 마이그레이션하는 방법입니다.

## 🔧 사전 준비

### 1. 로컬 PostgreSQL 설치 확인

```powershell
# PostgreSQL 버전 확인
psql --version

# PostgreSQL 서비스 상태 확인
Get-Service -Name postgresql*
```

### 2. 로컬 PostgreSQL 설정

로컬 PostgreSQL에 다음 설정으로 데이터베이스와 사용자를 생성합니다:

```sql
-- PostgreSQL에 접속 (postgres 사용자로)
psql -U postgres

-- 데이터베이스 생성
CREATE DATABASE ai_vibe_coding_test;

-- 사용자 생성 (Spring Boot 설정에 맞춤)
CREATE USER "user" WITH PASSWORD 'user123';

-- 권한 부여
GRANT ALL PRIVILEGES ON DATABASE ai_vibe_coding_test TO "user";

-- 스키마 권한 부여
\c ai_vibe_coding_test
GRANT ALL ON SCHEMA ai_vibe_coding_test TO "user";
GRANT ALL ON ALL TABLES IN SCHEMA ai_vibe_coding_test TO "user";
GRANT ALL ON ALL SEQUENCES IN SCHEMA ai_vibe_coding_test TO "user";

-- 기본 권한 설정 (앞으로 생성되는 테이블에도 자동 권한 부여)
ALTER DEFAULT PRIVILEGES IN SCHEMA ai_vibe_coding_test 
GRANT ALL ON TABLES TO "user";
ALTER DEFAULT PRIVILEGES IN SCHEMA ai_vibe_coding_test 
GRANT ALL ON SEQUENCES TO "user";
```

## 📦 데이터 마이그레이션

### 방법 1: pg_dump/pg_restore 사용 (권장)

```powershell
# 1. Docker PostgreSQL에서 덤프 생성
$env:PGPASSWORD = "postgres"
pg_dump -h localhost -p 5435 -U postgres -d ai_vibe_coding_test `
    --schema=ai_vibe_coding_test `
    --format=custom `
    -f ai_vibe_coding_test_backup.dump

# 2. 로컬 PostgreSQL로 복원
$env:PGPASSWORD = "user123"
pg_restore -h localhost -p 5432 -U user -d ai_vibe_coding_test `
    --schema=ai_vibe_coding_test `
    ai_vibe_coding_test_backup.dump
```

### 방법 2: SQL 스크립트 사용

```powershell
# 1. Docker PostgreSQL에서 SQL 덤프 생성
$env:PGPASSWORD = "postgres"
pg_dump -h localhost -p 5435 -U postgres -d ai_vibe_coding_test `
    --schema=ai_vibe_coding_test `
    --format=plain `
    -f ai_vibe_coding_test_backup.sql

# 2. 로컬 PostgreSQL로 복원
$env:PGPASSWORD = "user123"
psql -h localhost -p 5432 -U user -d ai_vibe_coding_test `
    -f ai_vibe_coding_test_backup.sql
```

### 방법 3: init-db.sql 사용 (초기 설정)

```powershell
# 로컬 PostgreSQL에 스키마만 생성 (데이터 없음)
$env:PGPASSWORD = "user123"
psql -h localhost -p 5432 -U user -d ai_vibe_coding_test `
    -f scripts/init-db.sql
```

## ⚙️ 설정 변경

### 1. Python/FastAPI 설정 (`.env` 파일)

```env
# PostgreSQL 설정 (로컬 DB)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=user
POSTGRES_PASSWORD=user123
POSTGRES_DB=ai_vibe_coding_test
```

### 2. Spring Boot 설정 (`application.yml`)

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

## ✅ 마이그레이션 확인

### 1. 연결 테스트

```powershell
# Python/FastAPI 연결 테스트
python -c "from app.core.config import settings; print(settings.POSTGRES_URL)"

# PostgreSQL 직접 연결 테스트
psql -h localhost -p 5432 -U user -d ai_vibe_coding_test
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

### 3. 데이터 확인

```sql
-- 데이터 개수 확인
SELECT COUNT(*) FROM ai_vibe_coding_test.prompt_sessions;
SELECT COUNT(*) FROM ai_vibe_coding_test.submissions;
```

## 🔄 롤백 방법 (필요시)

Docker로 다시 돌아가려면:

```powershell
# .env 파일 수정
POSTGRES_HOST=localhost
POSTGRES_PORT=5435  # Docker 포트
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

## 📝 주의사항

1. **포트 충돌**: 로컬 PostgreSQL이 기본 포트 5432를 사용하는지 확인
2. **권한 문제**: `user` 사용자에게 충분한 권한 부여 확인
3. **스키마 이름**: `ai_vibe_coding_test` 스키마 사용 확인
4. **Spring Boot JPA**: `ddl-auto: update` 사용 시 테이블 자동 생성됨 (주의)
5. **데이터 백업**: 마이그레이션 전 반드시 백업

## 🚀 자동화 스크립트

PowerShell 스크립트로 자동화:

```powershell
# scripts/migrate_docker_to_local.ps1
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

Write-Host "=================================================================================" -ForegroundColor Cyan
Write-Host "Docker PostgreSQL → Local PostgreSQL 마이그레이션" -ForegroundColor Cyan
Write-Host "=================================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Docker PostgreSQL에서 덤프 생성
Write-Host "📦 Docker PostgreSQL에서 덤프 생성 중..." -ForegroundColor Yellow
$dumpFile = "ai_vibe_coding_test_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"

$env:PGPASSWORD = $DockerPassword
pg_dump -h $DockerHost -p $DockerPort -U $DockerUser -d $DbName `
    --schema=$Schema `
    --format=plain `
    -f $dumpFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 덤프 실패!" -ForegroundColor Red
    exit 1
}

Write-Host "✅ 덤프 완료: $dumpFile" -ForegroundColor Green
Write-Host ""

# 2. 로컬 PostgreSQL로 복원
Write-Host "📥 로컬 PostgreSQL로 복원 중..." -ForegroundColor Yellow
$env:PGPASSWORD = $LocalPassword
psql -h $LocalHost -p $LocalPort -U $LocalUser -d $DbName -f $dumpFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 복원 실패!" -ForegroundColor Red
    exit 1
}

Write-Host "✅ 복원 완료" -ForegroundColor Green
Write-Host ""

# 3. 확인
Write-Host "📊 테이블 목록 확인 중..." -ForegroundColor Yellow
$env:PGPASSWORD = $LocalPassword
psql -h $LocalHost -p $LocalPort -U $LocalUser -d $DbName -c "SELECT table_name FROM information_schema.tables WHERE table_schema = '$Schema' ORDER BY table_name;"

Write-Host ""
Write-Host "=================================================================================" -ForegroundColor Cyan
Write-Host "✅ 마이그레이션 완료!" -ForegroundColor Green
Write-Host "=================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "덤프 파일: $dumpFile" -ForegroundColor Gray
Write-Host ""
Write-Host "다음 단계:" -ForegroundColor Yellow
Write-Host "1. .env 파일에서 POSTGRES_PORT를 5432로 변경" -ForegroundColor Gray
Write-Host "2. Spring Boot application.yml 설정 확인" -ForegroundColor Gray
Write-Host ""
```














