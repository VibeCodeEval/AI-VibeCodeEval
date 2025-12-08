# API 테스트 스크립트 - PowerShell
# 사용법: .\test_api.ps1

$apiBase = "http://localhost:8000/api"
$url = "$apiBase/chat/messages"

# 테스트 데이터
$body = @{
    sessionId = 1
    participantId = 1
    turnId = 1
    role = "USER"
    content = "안녕하세요"
    context = @{
        problemId = 1
        specVersion = 10
    }
} | ConvertTo-Json

Write-Host ("=" * 80)
Write-Host "API 테스트: POST /api/chat/messages"
Write-Host ("=" * 80)
Write-Host "요청 URL: $url"
Write-Host "요청 데이터:"
Write-Host $body
Write-Host ("-" * 80)

try {
    $response = Invoke-WebRequest -Uri $url -Method POST -Body $body -ContentType "application/json" -TimeoutSec 120
    
    Write-Host "`n응답 상태 코드: $($response.StatusCode)"
    Write-Host "응답 본문:"
    Write-Host $response.Content
    
    $result = $response.Content | ConvertFrom-Json
    if ($result.aiMessage) {
        Write-Host "`n" + ("=" * 80)
        Write-Host "✅ 성공!"
        Write-Host ("=" * 80)
        Write-Host "AI 응답 턴: $($result.aiMessage.turn)"
        Write-Host "AI 응답 내용: $($result.aiMessage.content.Substring(0, [Math]::Min(200, $result.aiMessage.content.Length)))..."
        Write-Host "토큰 사용량 (현재 턴): $($result.aiMessage.tokenCount)"
        Write-Host "토큰 사용량 (전체 누적): $($result.aiMessage.totalToken)"
    }
} catch {
    Write-Host "`n❌ 오류 발생:"
    Write-Host $_.Exception.Message
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "응답 본문: $responseBody"
    }
}

