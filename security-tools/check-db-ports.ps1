# Stage 1 section 1.3 - external DB and internal service ports (PowerShell 5.1)

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_ps-common.ps1"

$VpsIp = if ($env:RSD_VPS_IP) { $env:RSD_VPS_IP } else { "195.133.26.134" }
$LogFile = Join-Path (Get-LogDir) "03_external_db_ports.txt"

$ports = @(5432, 6379, 6333, 8000, 8090, 8100, 8200, 3000)

Write-Section "1.3 External ports ($VpsIp)"

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("1.3 external ports - $(Get-AuditTimestamp)")
$lines.Add("VPS: $VpsIp")
$lines.Add("")

foreach ($port in $ports) {
    $result = Test-NetConnection -ComputerName $VpsIp -Port $port -WarningAction SilentlyContinue
    $isClosed = -not $result.TcpTestSucceeded
    $status = if ($result.TcpTestSucceeded) { "OPEN" } else { "closed" }
    $line = "Port ${port}: $status (TcpTestSucceeded=$($result.TcpTestSucceeded))"
    if (-not $isClosed) {
        Write-Host $line -ForegroundColor Red
    } else {
        Write-Host $line -ForegroundColor Green
    }
    $lines.Add($line)
}

$lines | Out-File -FilePath $LogFile -Encoding utf8
Write-Host ""
Write-Host "Saved: $LogFile" -ForegroundColor Green
