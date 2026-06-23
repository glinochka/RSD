# Установка инструментов Этапа 1 на Windows (ПК)
# Запуск: powershell -ExecutionPolicy Bypass -File security-tools\install-pc.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$ToolsDir = Join-Path $ProjectRoot "security-tools"

Write-Host "=== RSD Security Tools: установка на ПК ===" -ForegroundColor Cyan

function Ensure-WingetPackage {
    param([string]$Id, [string]$Name)
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id $Id -e --accept-package-agreements --accept-source-agreements 2>$null
        Write-Host "[OK] $Name" -ForegroundColor Green
    } else {
        Write-Host "[SKIP] winget не найден — установите $Name вручную" -ForegroundColor Yellow
    }
}

Ensure-WingetPackage "Insecure.Nmap" "Nmap"
Ensure-WingetPackage "BurntSushi.ripgrep.GNU" "ripgrep"
Ensure-WingetPackage "Gitleaks.Gitleaks" "Gitleaks"
Ensure-WingetPackage "OpenJS.NodeJS.LTS" "Node.js LTS"
Ensure-WingetPackage "ZAP.ZAP" "OWASP ZAP"

Write-Host "`n--- Python-инструменты ---" -ForegroundColor Cyan
python -m pip install bandit pip-audit --trusted-host pypi.org --trusted-host files.pythonhosted.org

Write-Host "`n--- nuclei (бинарник в security-tools) ---" -ForegroundColor Cyan
$nucleiDir = Join-Path $ToolsDir "nuclei"
if (-not (Test-Path (Join-Path $nucleiDir "nuclei.exe"))) {
    $zip = Join-Path $ToolsDir "nuclei.zip"
    Invoke-WebRequest -Uri "https://github.com/projectdiscovery/nuclei/releases/download/v3.6.0/nuclei_3.6.0_windows_amd64.zip" -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $nucleiDir -Force
    Remove-Item $zip
}
& (Join-Path $nucleiDir "nuclei.exe") -update-templates 2>$null

Write-Host "`n--- testssl.sh (нужен Git Bash) ---" -ForegroundColor Cyan
$testsslDir = Join-Path $ToolsDir "testssl.sh"
if (-not (Test-Path $testsslDir)) {
    git clone --depth 1 https://github.com/drwetter/testssl.sh.git $testsslDir
}

Write-Host "`n--- wscat (WebSocket) ---" -ForegroundColor Cyan
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
npm install -g wscat

Write-Host "`n=== Готово. Перезапустите терминал. ===" -ForegroundColor Green
Write-Host "Проверка: powershell -File security-tools\verify-pc.ps1"
