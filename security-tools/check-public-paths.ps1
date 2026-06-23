# Stage 1 section 1.6 - public API paths (PowerShell 5.1)

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_ps-common.ps1"

$LogFile = Join-Path (Get-LogDir) "06_public_paths.txt"

$paths = @(
    "/api/users/me", "/api/admin/", "/api/agents/", "/api/payments/",
    "/api/telephony/", "/api/referrals/", "/api/websites/",
    "/webhook/test", "/webhook/voximplant/fake-id",
    "/.env", "/.git/config", "/wp-admin", "/phpmyadmin",
    "/docs", "/openapi.json"
)

$bases = @("https://rsd-ai.ru", "https://api.rsd-ai.ru")

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("1.6 public paths - $(Get-AuditTimestamp)")
$lines.Add("")

foreach ($base in $bases) {
    foreach ($p in $paths) {
        $uri = "${base}${p}"
        $code = Get-HttpStatusCode -Uri $uri -Method GET
        $line = "${uri} -> ${code}"
        $lines.Add($line)
        Write-Host $line
    }
}

$lines | Out-File -FilePath $LogFile -Encoding utf8
Write-Host ""
Write-Host "Saved: $LogFile" -ForegroundColor Green
