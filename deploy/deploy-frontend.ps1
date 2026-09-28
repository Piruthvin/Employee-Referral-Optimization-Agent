<#
.SYNOPSIS
    Build and Deploy Referral Agent Frontend to Azure Static Web Apps
#>

[CmdletBinding()]
param (
    [string]$AppName = "referral-agent-frontend",
    [string]$ResourceGroup = "ReferralAgentRG",
    [string]$Location = "southindia",
    [string]$DeploymentToken = $env:SWA_CLI_DEPLOYMENT_TOKEN
)

$ErrorActionPreference = "Stop"

$frontendDir = (Resolve-Path "$PSScriptRoot/../frontend").Path

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Azure Static Web Apps Frontend Deployment" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Build Production Bundle
Write-Host "[1/3] Building production bundle (vite + tsc)..." -ForegroundColor Yellow
Push-Location $frontendDir
try {
    npm run build
} finally {
    Pop-Location
}

# 2. Check Azure CLI & ensure SWA exists
if (Get-Command az -ErrorAction SilentlyContinue) {
    Write-Host "[2/3] Checking Static Web App ($AppName)..." -ForegroundColor Yellow
    $swaExists = az staticwebapp show --name $AppName --resource-group $ResourceGroup --query "name" -o tsv 2>$null
    if (-not $swaExists) {
        Write-Host "Creating Static Web App ($AppName)..." -ForegroundColor Yellow
        az staticwebapp create `
            --name $AppName `
            --resource-group $ResourceGroup `
            --location $Location `
            --sku Standard `
            --output none
    }

    if ([string]::IsNullOrWhiteSpace($DeploymentToken)) {
        Write-Host "Retrieving deployment token..." -ForegroundColor Yellow
        $DeploymentToken = az staticwebapp secrets list --name $AppName --resource-group $ResourceGroup --query "properties.apiKey" -o tsv
    }
}

# 3. Deploy via SWA CLI
Write-Host "[3/3] Deploying dist/ to Azure Static Web Apps..." -ForegroundColor Yellow
Push-Location $frontendDir
try {
    if ($DeploymentToken) {
        npx -y @azure/static-web-apps-cli deploy ./dist `
            --env production `
            --deployment-token $DeploymentToken
    } else {
        npx -y @azure/static-web-apps-cli deploy ./dist `
            --env production
    }
} finally {
    Pop-Location
}

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  SUCCESS! Frontend deployed to Azure Static Web Apps" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
