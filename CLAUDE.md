# HubSpot MCP PKCE Proxy

## Project Overview
PKCE-injecting OAuth proxy bridging HubSpot MCP (requires PKCE) and Microsoft
Copilot Studio (no PKCE support). Python + FastAPI.

## Architecture
- `src/hubspot_mcp_proxy/app.py` - FastAPI app factory with async lifespan
- `src/hubspot_mcp_proxy/config.py` - Pydantic Settings (env vars)
- `src/hubspot_mcp_proxy/db.py` - Async SQLite CRUD
- `src/hubspot_mcp_proxy/hub_client.py` - httpx client for HubSpot APIs
- `src/hubspot_mcp_proxy/pkce.py` - PKCE code verifier/challenge generation
- `src/hubspot_mcp_proxy/models.py` - Pydantic request/response models
- `src/hubspot_mcp_proxy/routes/` - FastAPI route modules
- `tests/` - pytest test suite (44 tests)

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
- async SQLite via aiosqlite (single-file DB, no external deps)
- httpx for async HTTP client (HubSpot API calls)
- pydantic-settings for configuration
- respx for mocking httpx in tests
- No PKCE advertised in OAuth metadata (Copilot Studio must not see it)
- Structured logging: INFO for flow events, WARNING for auth failures, ERROR for upstream errors, DEBUG for sensitive details

## Conventions
- TDD: write tests before implementation
- Feature branch workflow: `feat/<phase-name>` branches merged to `main`
- All routes are async
- Route modules use factory functions (`create_*_router`) for dependency injection

## Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/.well-known/oauth-authorization-server` | RFC 8414 metadata |
| POST | `/register` | RFC 7591 DCR |
| GET | `/authorize` | OAuth authorize (injects PKCE) |
| GET | `/callback` | HubSpot callback (exchanges code) |
| POST | `/token` | Token exchange / refresh |
| POST | `/mcp` | MCP HTTP reverse proxy |
| GET | `/health` | Health check |

## Infrastructure
- **Domain**: `hmcp.ams.iosharp.com` (via Traefik TLS with Let's Encrypt)
- **Host**: `optiplex:/home/tim/hubspot-mcp-pkce-proxy`
- **Port**: 8100 (host) → 8000 (container)
- **Network**: `media_default` (external, shared with Traefik)
- **Volume**: `proxy-data` → `/data` (SQLite persistence)
- **Traefik config**: `optiplex:/home/tim/media/appdata/traefik/dynamic/hubspot-mcp.yml`
- Includes `strip-trailing-slash` middleware for `/mcp/` → `/mcp` redirect

### Deployment
```bash
# Sync code to optiplex (from WSL2)
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='.pytest_cache' \
  --exclude='*.egg-info' --exclude='.env' --exclude='.ruff_cache' --exclude='.git' \
  -e ssh.exe . optiplex:/home/tim/hubspot-mcp-pkce-proxy/

# Build and start
ssh.exe optiplex "sudo docker compose -f /home/tim/hubspot-mcp-pkce-proxy/docker-compose.yml up -d --build"

# Check status
ssh.exe optiplex "sudo docker ps --filter name=hubspot-mcp-proxy"
ssh.exe optiplex "curl -s http://localhost:8100/health"
```
