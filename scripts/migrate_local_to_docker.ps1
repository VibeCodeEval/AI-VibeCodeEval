# 로컬 PostgreSQL DB를 Docker PostgreSQL로 마이그레이션
# PowerShell 스크립트

param(
    [string]$LocalHost = "localhost",
    [int]$LocalPort = 5432,
    [string]$LocalUser = "postgres",
    [string]$LocalPassword = "postgres",
    [string]$LocalDb = "ai_vibe_coding_test",
    [string]$DockerContainer = "ai_vibe_postgres",
    [string]$DockerUser = "postgres",
    [string]$DockerPassword = "postgres",
    [string]$DockerDb = "ai_vibe_coding_test",
    [string]$Schema = "ai_vibe_coding_test"
)

$ErrorActionPreference = "Stop"

Write-Host "=================================================================================" -ForegroundColor Cyan
Write-Host "로컬 PostgreSQL → Docker PostgreSQL 마이그레이션" -ForegroundColor Cyan
Write-Host "=================================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. 로컬 DB 스키마 덤프
Write-Host "📦 로컬 DB 스키마 덤프 중..." -ForegroundColor Yellow
$dumpFile = "schema_dump_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"

$env:PGPASSWORD = $LocalPassword
pg_dump -h $LocalHost -p $LocalPort -U $LocalUser -d $LocalDb `
    --schema-only `
    --schema=$Schema `
    -f $dumpFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 덤프 실패!" -ForegroundColor Red
    exit 1
}

Write-Host "✅ 덤프 완료: $dumpFile" -ForegroundColor Green
Write-Host ""

# 2. Docker PostgreSQL 시작
Write-Host "🐳 Docker PostgreSQL 시작 중..." -ForegroundColor Yellow
docker-compose up -d postgres

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker 시작 실패!" -ForegroundColor Red
    exit 1
}

Write-Host "⏳ PostgreSQL 준비 대기 중..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 3. Docker 컨테이너에 덤프 파일 복사
Write-Host "📥 Docker 컨테이너로 파일 복사 중..." -ForegroundColor Yellow
docker cp $dumpFile "${DockerContainer}:/tmp/schema_dump.sql"

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 파일 복사 실패!" -ForegroundColor Red
    exit 1
}

# 4. Docker PostgreSQL로 복원
Write-Host "📥 Docker PostgreSQL로 복원 중..." -ForegroundColor Yellow
$env:PGPASSWORD = $DockerPassword
docker exec -i $DockerContainer psql -U $DockerUser -d $DockerDb < $dumpFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 복원 실패!" -ForegroundColor Red
    exit 1
}

Write-Host ""

# 5. 확인
Write-Host "📊 테이블 목록 확인 중..." -ForegroundColor Yellow
docker exec -it $DockerContainer psql -U $DockerUser -d $DockerDb -c "SELECT table_name FROM information_schema.tables WHERE table_schema = '$Schema' ORDER BY table_name;"

Write-Host ""
Write-Host "=================================================================================" -ForegroundColor Cyan
Write-Host "✅ 마이그레이션 완료!" -ForegroundColor Green
Write-Host "=================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "덤프 파일: $dumpFile" -ForegroundColor Gray
Write-Host ""


