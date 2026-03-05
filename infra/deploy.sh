#!/usr/bin/env bash
# Deploy HubSpot MCP PKCE Proxy to Azure Container Apps
# Usage: ./deploy.sh [--plan-only] [--skip-infra] [--skip-build]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Defaults
PLAN_ONLY=false
SKIP_INFRA=false
SKIP_BUILD=false

# Parse flags
for arg in "$@"; do
    case $arg in
        --plan-only)  PLAN_ONLY=true ;;
        --skip-infra) SKIP_INFRA=true ;;
        --skip-build) SKIP_BUILD=true ;;
        *) echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

# Read Terraform outputs helper
tf_output() {
    terraform -chdir="${SCRIPT_DIR}" output -raw "$1"
}

echo "=== HubSpot MCP PKCE Proxy - Azure Deployment ==="
echo

# Phase 1: Terraform
if [ "${SKIP_INFRA}" = false ]; then
    echo "--- Phase 1: Infrastructure (Terraform) ---"
    terraform -chdir="${SCRIPT_DIR}" init -input=false
    terraform -chdir="${SCRIPT_DIR}" plan -out=tfplan

    if [ "${PLAN_ONLY}" = true ]; then
        echo "Plan-only mode. Exiting."
        exit 0
    fi

    terraform -chdir="${SCRIPT_DIR}" apply tfplan
    rm -f "${SCRIPT_DIR}/tfplan"
    echo "Infrastructure deployed."
    echo
fi

# Read resource names from Terraform outputs
RG_NAME=$(tf_output resource_group_name)
ACR_NAME=$(tf_output acr_name)
APP_NAME=$(tf_output container_app_name)
IMAGE="${ACR_NAME}.azurecr.io/hubspot-mcp-proxy"
CUSTOM_DOMAIN=$(tf_output custom_domain)

# Phase 2: Build and push container image
if [ "${SKIP_BUILD}" = false ]; then
    echo "--- Phase 2: Build Container Image ---"
    echo "Building image in ACR: ${ACR_NAME}"
    az acr build \
        --registry "${ACR_NAME}" \
        --image "hubspot-mcp-proxy:latest" \
        --file "${PROJECT_ROOT}/Dockerfile" \
        "${PROJECT_ROOT}"
    echo "Image built and pushed."
    echo
fi

# Phase 3: Update Container App with new image
echo "--- Phase 3: Update Container App ---"
az containerapp update \
    --name "${APP_NAME}" \
    --resource-group "${RG_NAME}" \
    --image "${IMAGE}:latest"
echo "Container App updated."
echo

# Phase 4: Verify
echo "--- Phase 4: Verification ---"
FQDN=$(tf_output container_app_fqdn)
echo "Default FQDN: https://${FQDN}"
echo "Custom domain: https://${CUSTOM_DOMAIN}"
echo
echo "Checking health endpoint..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://${FQDN}/health" || echo "000")
if [ "${HTTP_CODE}" = "200" ]; then
    echo "Health check: OK (HTTP ${HTTP_CODE})"
else
    echo "Health check: ${HTTP_CODE} (may need a moment to start)"
fi

echo
echo "=== Deployment Complete ==="
