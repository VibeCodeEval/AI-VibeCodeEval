# Docker PostgreSQL → Local PostgreSQL 마이그레이션
# PowerShell 스크립트

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
    Write-Host "💡 로컬 PostgreSQL이 실행 중인지, 사용자 권한이 올바른지 확인하세요." -ForegroundColor Yellow
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








