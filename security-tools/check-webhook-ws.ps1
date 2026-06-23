# Stage 1 section 1.7 - webhooks and WebSocket (PowerShell 5.1)

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_ps-common.ps1"

$LogFile = Join-Path (Get-LogDir) "07_webhooks_ws.txt"

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("1.7 webhooks ws - $(Get-AuditTimestamp)")
$lines.Add("")

Write-Section "Telegram webhook (fake path)"
$tgCode = Get-HttpStatusCode -Uri "https://rsd-ai.ru/webhook/FAKE_PATH" -Method POST
$tgLine = "POST https://rsd-ai.ru/webhook/FAKE_PATH -> $tgCode"
Write-Host $tgLine
$lines.Add($tgLine)

Write-Section "Voximplant webhook (fake UUID)"
$voxCode = Get-HttpStatusCode `
    -Uri "https://rsd-ai.ru/webhook/voximplant/00000000-0000-0000-0000-000000000000" `
    -Method POST `
    -Headers @{ "Content-Type" = "application/json" } `
    -Body "{}"
$voxLine = "POST voximplant fake-id -> $voxCode"
Write-Host $voxLine
$lines.Add($voxLine)

Write-Section "WebSocket handshake (wss://rsd-ai.ru/ws)"
$wscatCmd = Get-Command wscat.cmd -ErrorAction SilentlyContinue
if (-not $wscatCmd) {
    $wscatCmd = Get-Command wscat -ErrorAction SilentlyContinue
}

if ($wscatCmd) {
    $wsOut = & $wscatCmd.Source -c "wss://rsd-ai.ru/ws" 2>&1 | Select-Object -First 5
    $wsText = ($wsOut | Out-String).Trim()
    Write-Host $wsText
    $lines.Add("wscat output:")
    $lines.Add($wsText)
}
else {
    $msg = "wscat not found - run: npm install -g wscat"
    Write-Host $msg -ForegroundColor Yellow
    $lines.Add($msg)
}

$lines | Out-File -FilePath $LogFile -Encoding utf8
Write-Host ""
Write-Host "Saved: $LogFile" -ForegroundColor Green
