<#
.SYNOPSIS
    Smoke test live deployment of Referral Agent Backend
#>

[CmdletBinding()]
param (
    [string]$BaseUrl = "http://localhost:8000"
)

$BaseUrl = $BaseUrl.TrimEnd('/')

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Referral Agent Backend Smoke Tests: $BaseUrl" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$results = @()

# Test 1: Liveness Probe (/health)
try {
    $res = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get -TimeoutSec 10
    if ($res.status -eq "healthy") {
        $results += [PSCustomObject]@{ Test = "Liveness Probe (/health)"; Status = "PASS"; Details = "healthy (Python $($res.python))" }
    } else {
        $results += [PSCustomObject]@{ Test = "Liveness Probe (/health)"; Status = "FAIL"; Details = "Unexpected status: $($res.status)" }
    }
} catch {
    $results += [PSCustomObject]@{ Test = "Liveness Probe (/health)"; Status = "FAIL"; Details = $_.Exception.Message }
}

# Test 2: Readiness Probe (/ready)
try {
    $res = Invoke-RestMethod -Uri "$BaseUrl/ready" -Method Get -TimeoutSec 10
    if ($res.status -eq "ready") {
        $results += [PSCustomObject]@{ Test = "Readiness Probe (/ready)"; Status = "PASS"; Details = "ready (Env: $($res.environment))" }
    } else {
        $results += [PSCustomObject]@{ Test = "Readiness Probe (/ready)"; Status = "FAIL"; Details = "Unexpected status: $($res.status)" }
    }
} catch {
    $results += [PSCustomObject]@{ Test = "Readiness Probe (/ready)"; Status = "FAIL"; Details = $_.Exception.Message }
}

# Test 3: OTP Login Request (/api/v1/auth/login/request)
try {
    $body = @{ email = "smoke.test@company.com" } | ConvertTo-Json
    $res = Invoke-RestMethod -Uri "$BaseUrl/api/v1/auth/login/request" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 10
    if ($res.challenge_token) {
        $results += [PSCustomObject]@{ Test = "OTP Challenge Endpoint"; Status = "PASS"; Details = "Challenge token issued successfully" }
    } else {
        $results += [PSCustomObject]@{ Test = "OTP Challenge Endpoint"; Status = "FAIL"; Details = "No challenge_token in response" }
    }
} catch {
    $results += [PSCustomObject]@{ Test = "OTP Challenge Endpoint"; Status = "FAIL"; Details = $_.Exception.Message }
}

Write-Host ""
$results | Format-Table -AutoSize

$failed = $results | Where-Object { $_.Status -eq "FAIL" }
if ($failed) {
    Write-Host "Smoke tests completed with failures." -ForegroundColor Red
    exit 1
} else {
    Write-Host "All smoke tests PASSED successfully!" -ForegroundColor Green
    exit 0
}
