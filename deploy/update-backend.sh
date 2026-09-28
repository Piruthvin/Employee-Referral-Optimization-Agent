#!/usr/bin/env bash
# Update existing Referral Agent Backend Container App with new image build

set -euo pipefail

RG="${RESOURCE_GROUP:-ReferralAgentRG}"
APP_NAME="${APP_NAME:-referral-agent-backend}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/../backend"

ACR_NAME="${ACR_NAME:-$(az acr list --resource-group "${RG}" --query "[0].name" -o tsv)}"
IMAGE_TAG="$(date +%Y%m%d-%H%M%S)"
FULL_IMAGE="${ACR_NAME}.azurecr.io/${APP_NAME}:${IMAGE_TAG}"

echo "Building new container image: ${FULL_IMAGE}..."
az acr build --registry "${ACR_NAME}" --image "${APP_NAME}:${IMAGE_TAG}" "${BACKEND_DIR}"

echo "Updating Container App..."
az containerapp update --name "${APP_NAME}" --resource-group "${RG}" --image "${FULL_IMAGE}" --output none

FQDN="$(az containerapp show --name "${APP_NAME}" --resource-group "${RG}" --query properties.configuration.ingress.fqdn -o tsv)"
echo "Update completed! Application URL: https://${FQDN}"
