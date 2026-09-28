#!/usr/bin/env bash
# Build and Deploy Referral Agent Frontend to Azure Static Web Apps

set -euo pipefail

RG="${RESOURCE_GROUP:-ReferralAgentRG}"
LOCATION="${LOCATION:-southindia}"
APP_NAME="${APP_NAME:-referral-agent-frontend}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="${SCRIPT_DIR}/../frontend"

echo "=========================================================="
echo "  Azure Static Web Apps Frontend Deployment: ${APP_NAME}"
echo "=========================================================="

echo "[1/3] Building production bundle..."
(cd "${FRONTEND_DIR}" && npm run build)

DEPLOYMENT_TOKEN="${SWA_CLI_DEPLOYMENT_TOKEN:-}"

if command -v az &>/dev/null; then
  echo "[2/3] Checking Static Web App resource in Azure..."
  if ! az staticwebapp show --name "${APP_NAME}" --resource-group "${RG}" &>/dev/null; then
    echo "Creating Static Web App (${APP_NAME})..."
    az staticwebapp create \
      --name "${APP_NAME}" \
      --resource-group "${RG}" \
      --location "${LOCATION}" \
      --sku Standard \
      --output none
  fi

  if [ -z "${DEPLOYMENT_TOKEN}" ]; then
    DEPLOYMENT_TOKEN="$(az staticwebapp secrets list --name "${APP_NAME}" --resource-group "${RG}" --query "properties.apiKey" -o tsv)"
  fi
fi

echo "[3/3] Deploying dist/ via SWA CLI..."
if [ -n "${DEPLOYMENT_TOKEN}" ]; then
  (cd "${FRONTEND_DIR}" && npx -y @azure/static-web-apps-cli deploy ./dist --env production --deployment-token "${DEPLOYMENT_TOKEN}")
else
  (cd "${FRONTEND_DIR}" && npx -y @azure/static-web-apps-cli deploy ./dist --env production)
fi

echo "=========================================================="
echo "  SUCCESS! Frontend deployed."
echo "=========================================================="
