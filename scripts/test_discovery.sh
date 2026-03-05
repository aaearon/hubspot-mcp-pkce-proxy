#!/usr/bin/env bash
# Verify the full OAuth discovery flow against a deployed instance.
# Usage: ./scripts/test_discovery.sh https://your-proxy-domain.example.com
set -euo pipefail

BASE_URL="${1:?Usage: $0 <base-url>}"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

echo "=== OAuth Discovery Flow Test ==="
echo "Target: $BASE_URL"
echo

# 1. POST /mcp without auth -> 401 + WWW-Authenticate
echo "Step 1: POST /mcp (no auth) -> expect 401 + WWW-Authenticate"
HDRS=$(mktemp)
RESP=$(curl -s -o /dev/null -D "$HDRS" -w '%{http_code}' -X POST "$BASE_URL/mcp")
if [ "$RESP" = "401" ]; then pass "status 401"; else fail "expected 401, got $RESP"; fi

WWW_AUTH=$(grep -i 'www-authenticate' "$HDRS" || true)
rm -f "$HDRS"
if echo "$WWW_AUTH" | grep -q 'resource_metadata'; then
    pass "WWW-Authenticate contains resource_metadata"
else
    fail "WWW-Authenticate missing resource_metadata: $WWW_AUTH"
fi

# 2. GET protected resource metadata
echo
echo "Step 2: GET /.well-known/oauth-protected-resource -> expect 200"
PRM=$(curl -sf "$BASE_URL/.well-known/oauth-protected-resource")
PRM_STATUS=$?
if [ $PRM_STATUS -eq 0 ]; then pass "status 200"; else fail "request failed"; fi

AS_URL=$(echo "$PRM" | python3 -c "import sys,json; print(json.load(sys.stdin)['authorization_servers'][0])" 2>/dev/null || echo "")
if [ -n "$AS_URL" ]; then
    pass "authorization_servers present: $AS_URL"
else
    fail "authorization_servers missing from PRM"
fi

# 3. GET AS metadata
echo
echo "Step 3: GET AS metadata -> expect code_challenge_methods_supported"
AS_META=$(curl -sf "$AS_URL/.well-known/oauth-authorization-server")
if echo "$AS_META" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'S256' in d['code_challenge_methods_supported']" 2>/dev/null; then
    pass "code_challenge_methods_supported includes S256"
else
    fail "code_challenge_methods_supported missing or no S256"
fi

REG_EP=$(echo "$AS_META" | python3 -c "import sys,json; print(json.load(sys.stdin)['registration_endpoint'])" 2>/dev/null || echo "")
if [ -n "$REG_EP" ]; then
    pass "registration_endpoint present: $REG_EP"
else
    fail "registration_endpoint missing"
fi

# 4. POST /register (DCR)
echo
echo "Step 4: POST /register -> expect 201 + client_id"
REG_RESP=$(curl -s -w '\n%{http_code}' -X POST "$REG_EP" \
    -H "Content-Type: application/json" \
    -d '{"redirect_uris": ["https://test.example.com/callback"], "client_name": "discovery-test"}')
REG_BODY=$(echo "$REG_RESP" | head -n -1)
REG_CODE=$(echo "$REG_RESP" | tail -1)
if [ "$REG_CODE" = "201" ]; then pass "status 201"; else fail "expected 201, got $REG_CODE"; fi

if echo "$REG_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['client_id'] and d['client_secret']" 2>/dev/null; then
    pass "client_id and client_secret present"
else
    fail "client_id/client_secret missing from DCR response"
fi

echo
echo "=== Results: $PASS passed, $FAIL failed ==="
[ $FAIL -eq 0 ] && exit 0 || exit 1
