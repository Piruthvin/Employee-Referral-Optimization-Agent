#!/usr/bin/env bash
# Deploy Referral Agent Backend to Azure Container Apps (ACR Cloud Build + Managed Identity)

set -euo pipefail

RG="${RESOURCE_GROUP:-ReferralAgentRG}"
LOCATION="${LOCATION:-southindia}"
ENV_NAME="${ENVIRONMENT_NAME:-referral-agent-env}"
APP_NAME="${APP_NAME:-referral-agent-backend}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/../backend"
ENV_FILE="${BACKEND_DIR}/.env"

echo "=========================================================="
echo "  Azure Container Apps Backend Deployment: ${APP_NAME}"
echo "=========================================================="

if ! command -v az &>/dev/null; then
  echo "Error: Azure CLI (az) is required but not installed." >&2
  exit 1
fi

if [ ! -f "${ENV_FILE}" ]; then
  echo "Error: Backend environment file not found at: ${ENV_FILE}" >&2
  exit 1
fi

ACR_NAME="${ACR_NAME:-referralacr$((1000 + RANDOM % 9000))}"
ACR_NAME="$(echo "${ACR_NAME}" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]')"
IMAGE_TAG="$(date +%Y%m%d-%H%M%S)"
FULL_IMAGE="${ACR_NAME}.azurecr.io/${APP_NAME}:${IMAGE_TAG}"

echo "[1/6] Target: RG=${RG}, Location=${LOCATION}, ACR=${ACR_NAME}, ImageTag=${IMAGE_TAG}"

# Create Resource Group
echo "[2/6] Ensuring Resource Group..."
az group create --name "${RG}" --location "${LOCATION}" --output none

# Create ACR (admin disabled)
echo "[3/6] Ensuring Container Registry..."
az acr create --resource-group "${RG}" --name "${ACR_NAME}" --sku Basic --admin-enabled false --output none

# Submit cloud build
echo "[4/6] Submitting cloud build to ACR..."
az acr build --registry "${ACR_NAME}" --image "${APP_NAME}:${IMAGE_TAG}" "${BACKEND_DIR}"

# Create Container App Environment
echo "[5/6] Ensuring Container Apps Environment..."
az containerapp env create --name "${ENV_NAME}" --resource-group "${RG}" --location "${LOCATION}" --output none

# Deploy container app
echo "[6/6] Creating / Updating Container App..."
az containerapp create \
  --name "${APP_NAME}" \
  --resource-group "${RG}" \
  --environment "${ENV_NAME}" \
  --image "${FULL_IMAGE}" \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --output none

FQDN="$(az containerapp show --name "${APP_NAME}" --resource-group "${RG}" --query properties.configuration.ingress.fqdn -o tsv)"

echo "=========================================================="
echo "  SUCCESS! Backend deployed to: https://${FQDN}"
echo "=========================================================="
