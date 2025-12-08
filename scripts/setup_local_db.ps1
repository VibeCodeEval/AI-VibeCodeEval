# 로컬 PostgreSQL 초기 설정 (Spring Boot Backend용)
# 데이터 없이 스키마만 생성

param(
    [string]$Host = "localhost",
    [int]$Port = 5432,
    [string]$AdminUser = "postgres",
    [string]$AdminPassword = "",
    [string]$DbUser = "user",
    [string]$DbPassword = "user123",
    [string]$DbName = "ai_vibe_coding_test"
)

$ErrorActionPreference = "Stop"

Write-Host "=================================================================================" -ForegroundColor Cyan
Write-Host "로컬 PostgreSQL 초기 설정 (Spring Boot Backend용)" -ForegroundColor Cyan
Write-Host "=================================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. 데이터베이스 생성
Write-Host "📦 데이터베이스 생성 중..." -ForegroundColor Yellow
if ($AdminPassword) {
    $env:PGPASSWORD = $AdminPassword
}

# 데이터베이스가 없으면 생성
$dbCheck = psql -h $Host -p $Port -U $AdminUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DbName'" 2>$null
if (-not $dbCheck) {
    psql -h $Host -p $Port -U $AdminUser -d postgres -c "CREATE DATABASE $DbName;" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ 데이터베이스 생성 완료" -ForegroundColor Green
    } else {
        Write-Host "⚠️  데이터베이스 생성 중 오류 발생 (이미 존재할 수 있음)" -ForegroundColor Yellow
    }
} else {
    Write-Host "ℹ️  데이터베이스가 이미 존재합니다" -ForegroundColor Gray
}

Write-Host ""

# 2. 사용자 생성 및 권한 부여
Write-Host "👤 사용자 생성 및 권한 부여 중..." -ForegroundColor Yellow
if ($AdminPassword) {
    $env:PGPASSWORD = $AdminPassword
}

$userSql = @"
-- 사용자 생성 (없으면)
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DbUser') THEN
        CREATE USER "$DbUser" WITH PASSWORD '$DbPassword';
    ELSE
        ALTER USER "$DbUser" WITH PASSWORD '$DbPassword';
    END IF;
END
\$\$;

-- 권한 부여
GRANT ALL PRIVILEGES ON DATABASE $DbName TO "$DbUser";
"@

$userSql | psql -h $Host -p $Port -U $AdminUser -d postgres 2>&1 | Out-Null

Write-Host "✅ 사용자 생성 및 권한 부여 완료" -ForegroundColor Green
Write-Host ""

# 3. 스키마 생성 (init-db.sql 실행)
Write-Host "📋 스키마 생성 중 (init-db.sql 실행)..." -ForegroundColor Yellow
if ($AdminPassword) {
    $env:PGPASSWORD = $AdminPassword
}

$initScript = Join-Path $PSScriptRoot "init-db.sql"
if (Test-Path $initScript) {
    # 스키마 생성은 admin 사용자로 실행
    Get-Content $initScript | psql -h $Host -p $Port -U $AdminUser -d $DbName 2>&1 | Out-Null
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠️  스키마 생성 중 일부 오류 발생 (이미 존재하는 객체일 수 있음)" -ForegroundColor Yellow
    }
    
    # 스키마 권한 부여
    $schemaSql = @"
-- 스키마 권한 부여
GRANT ALL ON SCHEMA $DbName TO "$DbUser";
GRANT ALL ON ALL TABLES IN SCHEMA $DbName TO "$DbUser";
GRANT ALL ON ALL SEQUENCES IN SCHEMA $DbName TO "$DbUser";
GRANT ALL ON ALL FUNCTIONS IN SCHEMA $DbName TO "$DbUser";

-- 앞으로 생성되는 테이블에도 자동 권한 부여
ALTER DEFAULT PRIVILEGES IN SCHEMA $DbName GRANT ALL ON TABLES TO "$DbUser";
ALTER DEFAULT PRIVILEGES IN SCHEMA $DbName GRANT ALL ON SEQUENCES TO "$DbUser";
ALTER DEFAULT PRIVILEGES IN SCHEMA $DbName GRANT ALL ON FUNCTIONS TO "$DbUser";
"@
    
    $schemaSql | psql -h $Host -p $Port -U $AdminUser -d $DbName 2>&1 | Out-Null
    
    Write-Host "✅ 스키마 생성 완료" -ForegroundColor Green
} else {
    Write-Host "❌ init-db.sql 파일을 찾을 수 없습니다: $initScript" -ForegroundColor Red
    exit 1
}

Write-Host ""

# 4. 확인
Write-Host "📊 설정 확인 중..." -ForegroundColor Yellow
if ($AdminPassword) {
    $env:PGPASSWORD = $AdminPassword
}

Write-Host ""
Write-Host "테이블 목록:" -ForegroundColor Cyan
psql -h $Host -p $Port -U $AdminUser -d $DbName -c "SELECT table_name FROM information_schema.tables WHERE table_schema = '$DbName' ORDER BY table_name;"

Write-Host ""
Write-Host "=================================================================================" -ForegroundColor Cyan
Write-Host "✅ 초기 설정 완료!" -ForegroundColor Green
Write-Host "=================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "데이터베이스: $DbName" -ForegroundColor Gray
Write-Host "사용자: $DbUser" -ForegroundColor Gray
Write-Host "포트: $Port" -ForegroundColor Gray
Write-Host ""
Write-Host "Spring Boot application.yml 설정:" -ForegroundColor Yellow
Write-Host "  spring.datasource.url=jdbc:postgresql://localhost:$Port/$DbName" -ForegroundColor Gray
Write-Host "  spring.datasource.username=$DbUser" -ForegroundColor Gray
Write-Host "  spring.datasource.password=$DbPassword" -ForegroundColor Gray
Write-Host ""

