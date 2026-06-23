# Stage 1 section 1.6 - CORS preflight (PowerShell 5.1)

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_ps-common.ps1"

$LogFile = Join-Path (Get-LogDir) "06_cors.txt"

$tests = @(
    @{
        Name = "rsd-ai.ru /api/users/me (credentialed path)"
        Uri  = "https://rsd-ai.ru/api/users/me"
    },
    @{
        Name = "api.rsd-ai.ru /api/users/me"
        Uri  = "https://api.rsd-ai.ru/api/users/me"
    }
)

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("1.6 CORS - $(Get-AuditTimestamp)")
$lines.Add("")

foreach ($test in $tests) {
    Write-Section $test.Name
    $lines.Add($test.Name)

    $headers = Get-HttpResponseHeaders -Uri $test.Uri -Method OPTIONS -Headers @{
        "Origin"                        = "https://evil.example"
        "Access-Control-Request-Method" = "GET"
    }

    if ($null -eq $headers) {
        $msg = "  OPTIONS blocked or failed - OK for credentialed path"
        Write-Host $msg -ForegroundColor Green
        $lines.Add($msg)
        $lines.Add("")
        continue
    }

    $allowOrigin = $headers["Access-Control-Allow-Origin"]
    $allowCreds  = $headers["Access-Control-Allow-Credentials"]

    $msgOrigin = "  access-control-allow-origin: $allowOrigin"
    $msgCreds  = "  access-control-allow-credentials: $allowCreds"
    Write-Host $msgOrigin
    Write-Host $msgCreds
    $lines.Add($msgOrigin)
    $lines.Add($msgCreds)

    if ($allowOrigin -eq "https://evil.example" -and $allowCreds -eq "true") {
        $warn = "  [WARN] Reflecting evil origin WITH credentials"
        Write-Host $warn -ForegroundColor Yellow
        $lines.Add($warn)
    }
    elseif ($allowOrigin -eq "https://evil.example") {
        $info = "  [INFO] Reflecting origin without credentials"
        Write-Host $info
        $lines.Add($info)
    }
    else {
        $ok = "  [OK] evil.example not reflected with credentials"
        Write-Host $ok -ForegroundColor Green
        $lines.Add($ok)
    }
    $lines.Add("")
}

$lines | Out-File -FilePath $LogFile -Encoding utf8
Write-Host ""
Write-Host "Saved: $LogFile" -ForegroundColor Green
