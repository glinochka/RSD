# Проверка инструментов на ПК
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$nuclei = Join-Path $ProjectRoot "security-tools\nuclei\nuclei.exe"

$tools = @(
    @{ Name = "nmap"; Cmd = "nmap --version" },
    @{ Name = "rg"; Cmd = "rg --version" },
    @{ Name = "gitleaks"; Cmd = "gitleaks version" },
    @{ Name = "python"; Cmd = "python --version" },
    @{ Name = "bandit"; Cmd = "bandit --version" },
    @{ Name = "pip-audit"; Cmd = "pip-audit --version" },
    @{ Name = "node"; Cmd = "node --version" },
    @{ Name = "npm"; Cmd = "npm --version" },
    @{ Name = "curl"; Cmd = "curl.exe -V" },
    @{ Name = "git"; Cmd = "git --version" },
    @{ Name = "nuclei"; Cmd = "& `"$nuclei`" -version" },
    @{ Name = "wscat"; Cmd = "wscat -V" }
)

Write-Host "=== Проверка инструментов ПК ===" -ForegroundColor Cyan
foreach ($t in $tools) {
    try {
        $out = Invoke-Expression $t.Cmd 2>&1 | Select-Object -First 1
        Write-Host ("[OK]  {0,-12} {1}" -f $t.Name, $out) -ForegroundColor Green
    } catch {
        Write-Host ("[FAIL]{0,-12}" -f $t.Name) -ForegroundColor Red
    }
}
$testssl = Join-Path $ProjectRoot "security-tools\testssl.sh\testssl.sh"
if (Test-Path $testssl) {
    Write-Host "[OK]  testssl.sh   (запуск через Git Bash)" -ForegroundColor Green
} else {
    Write-Host "[FAIL]testssl.sh" -ForegroundColor Red
}
