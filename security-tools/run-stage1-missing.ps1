# Stage 1 missing checks (PowerShell 5.1)
# Run: powershell -ExecutionPolicy Bypass -File security-tools\run-stage1-missing.ps1

$ErrorActionPreference = "Continue"
$ScriptDir = $PSScriptRoot
$RepoRoot = Split-Path $ScriptDir -Parent

Set-Location $RepoRoot

Write-Host "=== RSD: stage 1 missing checks ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"
Write-Host ""

$scripts = @(
    "check-db-ports.ps1",
    "check-public-paths.ps1",
    "check-cors.ps1",
    "check-webhook-ws.ps1"
)

foreach ($name in $scripts) {
    $path = Join-Path $ScriptDir $name
    if (Test-Path $path) {
        Write-Host ">>> $name" -ForegroundColor Cyan
        & powershell -ExecutionPolicy Bypass -File $path
        Write-Host ""
    }
}

Write-Host "=== gitleaks (if installed) ===" -ForegroundColor Cyan
$gitleaksLog = Join-Path $RepoRoot "security-audit-logs\09_gitleaks.txt"
if (Get-Command gitleaks -ErrorAction SilentlyContinue) {
    $gitleaksOut = & gitleaks detect --source $RepoRoot --no-banner --redact 2>&1
    $gitleaksOut | Out-File -FilePath $gitleaksLog -Encoding utf8
    $gitleaksOut | ForEach-Object { Write-Host $_ }
    $leakLine = $gitleaksOut | Where-Object { $_ -match "leaks found" } | Select-Object -Last 1
    if ($leakLine -match "leaks found: (\d+)") {
        $count = $Matches[1]
        if ([int]$count -gt 0) {
            Write-Host "[WARN] gitleaks: $count potential secrets in git history - see $gitleaksLog" -ForegroundColor Yellow
            Write-Host "       Run: gitleaks detect --source . --verbose" -ForegroundColor Yellow
        } else {
            Write-Host "[OK] gitleaks: no leaks" -ForegroundColor Green
        }
    }
} else {
    Write-Host "[SKIP] gitleaks not installed" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done. Logs in security-audit-logs" -ForegroundColor Green
