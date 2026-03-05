#!/usr/bin/env bash
# Terraform validation test suite
# Runs format check, init, and validate against the infra/ directory.
set -euo pipefail

INFRA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ERRORS=0

echo "=== Terraform Validation Suite ==="
echo "Working directory: ${INFRA_DIR}"
echo

# 1. Format check
echo "--- terraform fmt -check ---"
if terraform -chdir="${INFRA_DIR}" fmt -check -diff; then
    echo "PASS: formatting"
else
    echo "FAIL: formatting (run 'terraform fmt' to fix)"
    ERRORS=$((ERRORS + 1))
fi
echo

# 2. Init (no backend)
echo "--- terraform init -backend=false ---"
if terraform -chdir="${INFRA_DIR}" init -backend=false -input=false > /dev/null 2>&1; then
    echo "PASS: init"
else
    echo "FAIL: init"
    ERRORS=$((ERRORS + 1))
fi
echo

# 3. Validate
echo "--- terraform validate ---"
if terraform -chdir="${INFRA_DIR}" validate; then
    echo "PASS: validate"
else
    echo "FAIL: validate"
    ERRORS=$((ERRORS + 1))
fi
echo

# 4. Security hardening checks
echo "--- Security hardening ---"

# 4a. Container App has IP security restrictions
if grep -q 'ip_security_restriction' "${INFRA_DIR}/container_app.tf"; then
    echo "PASS: Container App IP restrictions present"
else
    echo "FAIL: container_app.tf must contain ip_security_restriction"
    ERRORS=$((ERRORS + 1))
fi

# 4b. Container App disallows insecure connections
if grep -q 'allow_insecure_connections\s*=\s*false' "${INFRA_DIR}/container_app.tf"; then
    echo "PASS: Container App HTTPS-only"
else
    echo "FAIL: container_app.tf must set allow_insecure_connections = false"
    ERRORS=$((ERRORS + 1))
fi

# 4c. Network service tags data sources exist
if [ -f "${INFRA_DIR}/network.tf" ] && grep -q 'azurerm_network_service_tags' "${INFRA_DIR}/network.tf"; then
    echo "PASS: network service tags data sources present"
else
    echo "FAIL: network.tf must contain azurerm_network_service_tags data sources"
    ERRORS=$((ERRORS + 1))
fi

# 4d. TLS certificate managed by ACME provider (not Azure managed cert)
if grep -q 'acme_certificate' "${INFRA_DIR}/certificate.tf" 2>/dev/null; then
    echo "PASS: ACME certificate resource present"
else
    echo "FAIL: certificate.tf must contain acme_certificate resource"
    ERRORS=$((ERRORS + 1))
fi

# 4e. TOKEN_ENCRYPTION_KEY secret configured in Container App
if grep -q 'token-encryption-key' "${INFRA_DIR}/container_app.tf"; then
    echo "PASS: TOKEN_ENCRYPTION_KEY secret present"
else
    echo "FAIL: container_app.tf must contain token-encryption-key secret"
    ERRORS=$((ERRORS + 1))
fi

# 4f. No storage volume mounts (in-memory SQLite)
if grep -q 'volume_mounts' "${INFRA_DIR}/container_app.tf"; then
    echo "FAIL: container_app.tf must not contain volume_mounts (in-memory SQLite)"
    ERRORS=$((ERRORS + 1))
else
    echo "PASS: No volume mounts (in-memory SQLite)"
fi

# 4g. No storage.tf file (storage no longer used)
if [ -f "${INFRA_DIR}/storage.tf" ]; then
    echo "FAIL: storage.tf must not exist (storage no longer used)"
    ERRORS=$((ERRORS + 1))
else
    echo "PASS: No storage.tf"
fi

# 4h. No org-specific defaults in variables.tf
if grep -q 'acrtechlabslab001\|cyberiam' "${INFRA_DIR}/variables.tf"; then
    echo "FAIL: variables.tf contains org-specific defaults (scrub required)"
    ERRORS=$((ERRORS + 1))
else
    echo "PASS: No org-specific defaults in variables.tf"
fi

# 4i. IP restriction toggle variable exists
if grep -q 'enable_ip_restrictions' "${INFRA_DIR}/variables.tf"; then
    echo "PASS: IP restriction toggle variable present"
else
    echo "FAIL: variables.tf must contain enable_ip_restrictions variable"
    ERRORS=$((ERRORS + 1))
fi
echo

# Summary
if [ "${ERRORS}" -eq 0 ]; then
    echo "=== ALL CHECKS PASSED ==="
    exit 0
else
    echo "=== ${ERRORS} CHECK(S) FAILED ==="
    exit 1
fi
