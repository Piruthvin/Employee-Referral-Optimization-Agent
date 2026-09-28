<#
.SYNOPSIS
    Deploy Referral Agent Backend to Azure Container Apps (ACR Cloud Build + Managed Identity)
.DESCRIPTION
    Automates resource group creation, Azure Container Registry, ACR cloud image build,
    Container Apps Environment, secret provisioning, and container deployment.
#>

[CmdletBinding()]
param (
    [string]$ResourceGroup = "ReferralAgentRG",
    [string]$Location = "southindia",
    [string]$AcrName = "",
    [string]$EnvironmentName = "referral-agent-env",
    [string]$AppName = "referral-agent-backend",
    [string]$BackendEnvFile = "$PSScriptRoot/../backend/.env"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Azure Container Apps Backend Deployment: $AppName" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Validate Prerequisites
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Error "Azure CLI (az) is not installed or not in PATH. Please install Azure CLI."
}

if (-not (Test-Path $BackendEnvFile)) {
    Write-Error "Backend environment file not found at: $BackendEnvFile"
}

# 2. Generate unique ACR name if unset
if ([string]::IsNullOrWhiteSpace($AcrName)) {
    $randomSuffix = (Get-Random -Minimum 1000 -Maximum 9999).ToString()
    $AcrName = "referralacr$randomSuffix"
}
$AcrName = $AcrName.ToLower() -replace '[^a-z0-9]', ''

$ImageTag = (Get-Date -Format "yyyyMMdd-HHmmss")
$FullImage = "$AcrName.azurecr.io/${AppName}:${ImageTag}"

Write-Host "[1/7] Target Configuration:" -ForegroundColor Yellow
Write-Host "  Resource Group : $ResourceGroup"
Write-Host "  Location       : $Location"
Write-Host "  ACR Name       : $AcrName"
Write-Host "  Container App  : $AppName"
Write-Host "  Image Tag      : $ImageTag"

# 3. Read secrets safely from backend/.env without echoing values
Write-Host "[2/7] Parsing configuration from $BackendEnvFile..." -ForegroundColor Yellow
$envVars = @{}
Get-Content $BackendEnvFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $val = $parts[1].Trim()
        $envVars[$key] = $val
    }
}

# 4. Create Resource Group
Write-Host "[3/7] Creating Resource Group ($ResourceGroup)..." -ForegroundColor Yellow
az group create --name $ResourceGroup --location $Location --output none

# 5. Create Azure Container Registry (Admin disabled, Managed Identity access)
Write-Host "[4/7] Ensuring Azure Container Registry ($AcrName)..." -ForegroundColor Yellow
az acr create --resource-group $ResourceGroup --name $AcrName --sku Basic --admin-enabled false --output none

# 6. Cloud build in ACR (No local Docker daemon required!)
Write-Host "[5/7] Submitting cloud build to ACR (context: backend/)..." -ForegroundColor Yellow
$backendDir = (Resolve-Path "$PSScriptRoot/../backend").Path
az acr build --registry $AcrName --image "${AppName}:${ImageTag}" $backendDir

# 7. Create Container App Environment
Write-Host "[6/7] Ensuring Container Apps Environment ($EnvironmentName)..." -ForegroundColor Yellow
az containerapp env create `
    --name $EnvironmentName `
    --resource-group $ResourceGroup `
    --location $Location `
    --output none

# 8. Create / Update Container App with Managed Identity and Secrets
Write-Host "[7/7] Deploying Container App ($AppName)..." -ForegroundColor Yellow

# Prepare secrets arguments
$secretArgs = @(
    "jwt-secret=$($envVars['JWT_SECRET_KEY'])",
    "agent-api-key=$($envVars['AGENT_API_KEY'])",
    "zoho-client-id=$($envVars['ZOHO_CLIENT_ID'])",
    "zoho-client-secret=$($envVars['ZOHO_CLIENT_SECRET'])",
    "zoho-refresh-token=$($envVars['ZOHO_REFRESH_TOKEN'])",
    "ms-tenant-id=$($envVars['MS_TENANT_ID'])",
    "ms-client-id=$($envVars['MS_CLIENT_ID'])",
    "ms-client-secret=$($envVars['MS_CLIENT_SECRET'])",
    "ms-organizer-upn=$($envVars['MS_ORGANIZER_UPN'])",
    "ms-sender-upn=$($envVars['MS_SENDER_UPN'])",
    "igentic-executor-url=$($envVars['IGENTIC_EXECUTOR_URL'])",
    "igentic-app-id=$($envVars['IGENTIC_APP_ID'])",
    "igentic-api-key=$($envVars['IGENTIC_API_KEY'])",
    "igentic-bearer-token=$($envVars['IGENTIC_BEARER_TOKEN'])",
    "igentic-username=$($envVars['IGENTIC_USERNAME'])",
    "igentic-parser-url=$($envVars['IGENTIC_PARSER_EXECUTOR_URL'])",
    "igentic-parser-app-id=$($envVars['IGENTIC_PARSER_APP_ID'])"
)

# Prepare environment variable arguments
$appEnvArgs = @(
    "APP_ENV=production",
    "AUTH_MODE=otp",
    "ZOHO_ACCOUNTS_BASE_URL=$($envVars['ZOHO_ACCOUNTS_BASE_URL'])",
    "ZOHO_RECRUIT_BASE_URL=$($envVars['ZOHO_RECRUIT_BASE_URL'])",
    "RESUME_PARSER_MODE=$($envVars['RESUME_PARSER_MODE'])",
    "MIN_ASSOCIATE_MATCH=$($envVars['MIN_ASSOCIATE_MATCH'])",
    "POINTS_PER_REFERRAL=$($envVars['POINTS_PER_REFERRAL'])",
    "MAX_RESUME_MB=$($envVars['MAX_RESUME_MB'])",
    "JWT_EXPIRY_HOURS=$($envVars['JWT_EXPIRY_HOURS'])",
    "JWT_SECRET_KEY=secretref:jwt-secret",
    "AGENT_API_KEY=secretref:agent-api-key",
    "ZOHO_CLIENT_ID=secretref:zoho-client-id",
    "ZOHO_CLIENT_SECRET=secretref:zoho-client-secret",
    "ZOHO_REFRESH_TOKEN=secretref:zoho-refresh-token",
    "MS_TENANT_ID=secretref:ms-tenant-id",
    "MS_CLIENT_ID=secretref:ms-client-id",
    "MS_CLIENT_SECRET=secretref:ms-client-secret",
    "MS_ORGANIZER_UPN=secretref:ms-organizer-upn",
    "MS_SENDER_UPN=secretref:ms-sender-upn",
    "IGENTIC_EXECUTOR_URL=secretref:igentic-executor-url",
    "IGENTIC_APP_ID=secretref:igentic-app-id",
    "IGENTIC_API_KEY=secretref:igentic-api-key",
    "IGENTIC_BEARER_TOKEN=secretref:igentic-bearer-token",
    "IGENTIC_USERNAME=secretref:igentic-username",
    "IGENTIC_PARSER_EXECUTOR_URL=secretref:igentic-parser-url",
    "IGENTIC_PARSER_APP_ID=secretref:igentic-parser-app-id"
)

az containerapp create `
    --name $AppName `
    --resource-group $ResourceGroup `
    --environment $EnvironmentName `
    --image $FullImage `
    --target-port 8000 `
    --ingress external `
    --min-replicas 1 `
    --max-replicas 3 `
    --cpu 0.5 `
    --memory 1.0Gi `
    --secrets $secretArgs `
    --env-vars $appEnvArgs `
    --output none

# Assign ACR Pull permission via Managed Identity
Write-Host "Configuring AcrPull managed identity permissions..." -ForegroundColor Yellow
$spId = az containerapp identity show --name $AppName --resource-group $ResourceGroup --query principalId -o tsv
$acrId = az acr show --name $AcrName --resource-group $ResourceGroup --query id -o tsv
if ($spId -and $acrId) {
    az role assignment create --assignee $spId --role "AcrPull" --scope $acrId --output none
}

# Fetch FQDN
$fqdn = az containerapp show --name $AppName --resource-group $ResourceGroup --query properties.configuration.ingress.fqdn -o tsv

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  SUCCESS! Backend deployed to Azure Container Apps" -ForegroundColor Green
Write-Host "  FQDN: https://$fqdn" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "Next Step: Run deploy/post-deploy-checklist.md to configure CORS and iGentic tools."
