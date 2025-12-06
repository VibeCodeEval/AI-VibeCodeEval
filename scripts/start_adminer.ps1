# Adminer 웹 기반 DB 관리 도구 실행 스크립트

Write-Host "Adminer 컨테이너 시작 중..." -ForegroundColor Green

# 기존 Adminer 컨테이너가 있으면 제거
docker stop adminer 2>$null
docker rm adminer 2>$null

# Docker 네트워크 확인
$network = docker network ls --filter "name=ai_vibe" --format "{{.Name}}" | Select-Object -First 1

if (-not $network) {
    Write-Host "Docker 네트워크를 찾을 수 없습니다. docker-compose.dev.yml을 먼저 실행하세요." -ForegroundColor Red
    exit 1
}

# Adminer 실행
docker run -d `
    --name adminer `
    --network $network `
    -p 8080:8080 `
    adminer

Write-Host "✅ Adminer가 시작되었습니다!" -ForegroundColor Green
Write-Host ""
Write-Host "웹 브라우저에서 접속하세요:" -ForegroundColor Yellow
Write-Host "  URL: http://localhost:8080" -ForegroundColor Cyan
Write-Host ""
Write-Host "로그인 정보:" -ForegroundColor Yellow
Write-Host "  시스템: PostgreSQL" -ForegroundColor Cyan
Write-Host "  서버: ai_vibe_postgres_dev" -ForegroundColor Cyan
Write-Host "  사용자명: postgres" -ForegroundColor Cyan
Write-Host "  비밀번호: postgres" -ForegroundColor Cyan
Write-Host "  데이터베이스: ai_vibe_coding_test" -ForegroundColor Cyan
Write-Host ""
Write-Host "종료하려면: docker stop adminer" -ForegroundColor Gray


