# HubSpot MCP PKCE Proxy

## Project Overview
PKCE-injecting OAuth proxy bridging HubSpot MCP (requires PKCE) and Microsoft
Copilot Studio (no PKCE support). Python + FastAPI.

## Architecture
- `src/hubspot_mcp_proxy/app.py` - FastAPI app factory with async lifespan
- `src/hubspot_mcp_proxy/config.py` - Pydantic Settings (env vars)
- `src/hubspot_mcp_proxy/crypto.py` - Fernet token encryption + scrypt secret hashing
- `src/hubspot_mcp_proxy/db.py` - Async SQLite CRUD
- `src/hubspot_mcp_proxy/hub_client.py` - httpx client for HubSpot APIs
- `src/hubspot_mcp_proxy/pkce.py` - PKCE code verifier/challenge generation
- `src/hubspot_mcp_proxy/models.py` - Pydantic request/response models
- `src/hubspot_mcp_proxy/routes/` - FastAPI route modules
- `tests/` - pytest test suite (94 tests)
- `scripts/test_discovery.sh` - End-to-end OAuth discovery flow verification
- `infra/` - Terraform IaC for Azure Container Apps

## Development

```bash
# Setup
uv venv && uv pip install -e ".[dev]"

# Test
source .venv/bin/activate && pytest

# Lint
source .venv/bin/activate && ruff check src/ tests/

# Docker build
docker compose build

# Docker run (requires .env)
docker compose up -d
```

## Key Decisions
- In-memory SQLite by default (`:memory:`) — all stored data is transient and auto-recoverable; set `DATABASE_PATH` env var for file-based persistence
- async SQLite via aiosqlite (no external deps)
- httpx for async HTTP client (HubSpot API calls)
- pydantic-settings for configuration
- respx for mocking httpx in tests
- PKCE (`code_challenge_methods_supported: ["S256"]`) advertised in AS metadata — required for Copilot Studio to proceed past discovery. CS doesn't actually send PKCE; our proxy generates its own for HubSpot
- RFC 9728 Protected Resource Metadata at `/.well-known/oauth-protected-resource`
- 401 responses include `WWW-Authenticate` header with `resource_metadata` URL per RFC 9728
- Structured logging: INFO for flow events, WARNING for auth failures, ERROR for upstream errors, DEBUG for sensitive details
- Fernet (AES-128-CBC + HMAC-SHA256) for encrypting tokens at rest in SQLite
- scrypt (n=16384, r=8, p=1) for hashing client secrets, with SHA-256 legacy fallback
- Open DCR `/register` endpoint (IP-restricted at infra level, redirect URI domain allowlist)
- `ALLOWED_REDIRECT_DOMAINS` restricts DCR redirect URIs to approved domains (default: `["api.powerva.microsoft.com"]`); supports subdomains, requires `https`
- Authorization header required for MCP proxy endpoints
- State parameter validated against `[A-Za-z0-9_\-\.~]{1,512}` pattern
- Only `response_type=code` accepted (implicit grant rejected)

## Conventions
- TDD: write tests before implementation
- Feature branch workflow: `feat/<phase-name>` branches merged to `main`
- All routes are async
- Route modules use factory functions (`create_*_router`) for dependency injection

## Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/.well-known/oauth-authorization-server` | RFC 8414 AS metadata |
| GET | `/.well-known/oauth-protected-resource` | RFC 9728 PRM |
| POST | `/register` | RFC 7591 DCR (requires Bearer token) |
| GET | `/authorize` | OAuth authorize (injects PKCE) |
| GET | `/callback` | HubSpot callback (exchanges code, handles errors) |
| POST | `/token` | Token exchange / refresh |
| POST | `/mcp` | MCP HTTP reverse proxy (requires Authorization) |
| GET | `/mcp` | OAuth discovery trigger (returns 401) |
| GET | `/health` | Health check |

## Infrastructure
- **Hosting**: Azure Container Apps
- **TLS**: Let's Encrypt (managed via Terraform ACME provider)
- **IaC**: Terraform in `infra/` (local state, not committed)
- **IP restrictions**: PowerPlatformPlex + AzureConnectors service tags (toggleable via `enable_ip_restrictions` variable)
- **Diagnostic logging**: Request middleware logs method, path, user-agent, auth presence, status code for every request
- See `infra/` for resource names, ACR, DNS, and deployment details

### Deployment
```bash
# Build and push container image
./infra/deploy.sh

# Infrastructure-only change (no container rebuild)
./infra/deploy.sh --skip-build

# Code-only change (no Terraform)
./infra/deploy.sh --skip-infra

# Check health
curl -s https://<your-domain>/health
```

## Migration Guide (for LLMs and operators deploying updates)

### Breaking Changes (Security Hardening Release)

**One new required environment variable** - the service will NOT start without it:

| Variable | Purpose | Generate with |
|----------|---------|---------------|
| `TOKEN_ENCRYPTION_KEY` | Fernet key for encrypting tokens at rest | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

**New optional environment variable:**

| Variable | Purpose | Default |
|----------|---------|---------|
| `ALLOWED_REDIRECT_DOMAINS` | JSON list of allowed redirect URI domains for DCR | `["api.powerva.microsoft.com"]` |

**Endpoint authentication changes:**
- `POST /register` is open (no auth required) — relies on IP restrictions at infra level and redirect URI domain allowlist for access control.
- `POST /mcp` and `POST /` now require an `Authorization` header. Requests without one return 401. Copilot Studio already sends this, so no client changes needed.

**Input validation on `/register`:**
- `redirect_uris` must all use `https` scheme
- Each URI's hostname must match or be a subdomain of an `ALLOWED_REDIRECT_DOMAINS` entry
- Rejected URIs return 400 with `{"error": "invalid_redirect_uri"}`

**Input validation on `/authorize`:**
- `response_type` must be `code` (implicit grant `token` is rejected with 400)
- `state` must match `[A-Za-z0-9_\-\.~]{1,512}` (rejects HTML/script injection, length > 512)

### Migration Steps

1. Generate both new env vars and add them to `.env` on the host
2. Stop the old container: `docker compose down`
3. Wait 10 minutes (allows in-flight auth_states/auth_codes to expire - they cannot be decrypted by the new instance since they were stored unencrypted)
4. Rebuild and start: `docker compose up -d --build`
5. Verify health: `curl http://localhost:8100/health`
6. If Copilot Studio needs to re-register: `curl -X POST https://<domain>/register -H "Content-Type: application/json" -d '{"redirect_uris": ["..."], "client_name": "..."}'`

### Backward Compatibility
- **Client secret hashing**: Existing clients with SHA-256 hashes continue to work (legacy fallback in `verify_client_secret`). New registrations use scrypt.
- **OAuth callback errors**: HubSpot OAuth errors (e.g., `access_denied`) are now properly forwarded to the client's redirect_uri instead of returning a raw 400.
- **New dependency**: `cryptography>=44.0` added to `pyproject.toml`.
