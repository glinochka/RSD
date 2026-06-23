# Shared helpers for security audit scripts (PowerShell 5.1+)

function Get-HttpStatusCode {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [ValidateSet("GET", "POST", "OPTIONS", "HEAD")]
        [string]$Method = "GET",
        [hashtable]$Headers = @{},
        [string]$Body = $null
    )

    try {
        $params = @{
            Uri             = $Uri
            Method          = $Method
            UseBasicParsing = $true
            ErrorAction     = "Stop"
        }
        if ($Headers.Count -gt 0) {
            $params.Headers = $Headers
        }
        if ($Body -ne $null) {
            $params.Body = $Body
        }
        $response = Invoke-WebRequest @params
        return [int]$response.StatusCode
    }
    catch {
        $resp = $_.Exception.Response
        if ($resp) {
            return [int]$resp.StatusCode
        }
        return -1
    }
}

function Get-HttpResponseHeaders {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [ValidateSet("GET", "POST", "OPTIONS", "HEAD")]
        [string]$Method = "GET",
        [hashtable]$Headers = @{}
    )

    try {
        $params = @{
            Uri             = $Uri
            Method          = $Method
            UseBasicParsing = $true
            ErrorAction     = "Stop"
        }
        if ($Headers.Count -gt 0) {
            $params.Headers = $Headers
        }
        $response = Invoke-WebRequest @params
        return $response.Headers
    }
    catch {
        if ($_.Exception.Response) {
            return $_.Exception.Response.Headers
        }
        return $null
    }
}

function Write-Section {
    param([string]$Title)
    $line = "=" * 72
    Write-Output ""
    Write-Output $line
    Write-Output $Title
    Write-Output $line
    Write-Output ""
}

function Get-ProjectRoot {
    return Split-Path $PSScriptRoot -Parent
}

function Get-LogDir {
    $dir = Join-Path (Get-ProjectRoot) "security-audit-logs"
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    return $dir
}

function Get-AuditTimestamp {
    return Get-Date -Format "yyyy-MM-dd HH:mm"
}
