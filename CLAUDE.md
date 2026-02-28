# HubSpot MCP PKCE Proxy

## Project Overview
PKCE-injecting OAuth proxy bridging HubSpot MCP (requires PKCE) and Microsoft
Copilot Studio (no PKCE support). Python + FastAPI.

## Architecture
- `src/hubspot_mcp_proxy/` - Application source
- `src/hubspot_mcp_proxy/routes/` - FastAPI route modules
- `tests/` - pytest test suite

## Development

```bash
# Setup
uv venv && uv pip install -e ".[dev]"

# Test
source .venv/bin/activate && pytest

# Lint
source .venv/bin/activate && ruff check src/ tests/
```

## Key Decisions
- async SQLite via aiosqlite (single-file DB, no external deps)
- httpx for async HTTP client (HubSpot API calls)
- pydantic-settings for configuration
- respx for mocking httpx in tests
- No PKCE advertised in OAuth metadata (Copilot Studio must not see it)

## Conventions
- TDD: write tests before implementation
- Feature branch workflow: `feat/<phase-name>` branches merged to `main`
- All routes are async
- Database operations use async context managers
