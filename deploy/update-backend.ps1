<#
.SYNOPSIS
    Update existing Referral Agent Backend Container App with new image build.
#>

[CmdletBinding()]
param (
    [string]$ResourceGroup = "ReferralAgentRG",
    [string]$AcrName = "",
    [string]$AppName = "referral-agent-backend"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($AcrName)) {
    Write-Host "Fetching ACR registry from resource group..." -ForegroundColor Yellow
    $AcrName = az acr list --resource-group $ResourceGroup --query "[0].name" -o tsv
    if (-not $AcrName) {
        Write-Error "No ACR registry found in resource group $ResourceGroup. Please specify -AcrName."
    }
}

$ImageTag = (Get-Date -Format "yyyyMMdd-HHmmss")
$FullImage = "$AcrName.azurecr.io/${AppName}:${ImageTag}"

Write-Host "Building new container image: $FullImage" -ForegroundColor Yellow
$backendDir = (Resolve-Path "$PSScriptRoot/../backend").Path
az acr build --registry $AcrName --image "${AppName}:${ImageTag}" $backendDir

Write-Host "Updating Container App to revision with image: $FullImage" -ForegroundColor Yellow
az containerapp update `
    --name $AppName `
    --resource-group $ResourceGroup `
    --image $FullImage `
    --output none

$fqdn = az containerapp show --name $AppName --resource-group $ResourceGroup --query properties.configuration.ingress.fqdn -o tsv
Write-Host "Update completed! Application URL: https://$fqdn" -ForegroundColor Green
