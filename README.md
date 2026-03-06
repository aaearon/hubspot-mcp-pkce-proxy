# HubSpot MCP PKCE Proxy

PKCE-injecting OAuth proxy that bridges
[HubSpot MCP](https://mcp.hubspot.com) (requires PKCE) and
[Microsoft Copilot Studio](https://learn.microsoft.com/en-us/microsoft-copilot-studio/)
(no PKCE support).

## How it works

Copilot Studio discovers OAuth endpoints via RFC 8414 / RFC 9728 metadata,
then starts a standard authorization code flow. The proxy intercepts
`/authorize`, generates a PKCE `code_verifier` + `code_challenge`, and
forwards the request to HubSpot with the challenge attached. When HubSpot
calls back, the proxy exchanges the authorization code using the stored
verifier, then issues its own code to Copilot Studio. Token exchange and
refresh requests are similarly proxied.

## Quick start

### Environment variables

Create a `.env` file:

```env
# Required
HUBSPOT_CLIENT_ID=your-hubspot-app-client-id
HUBSPOT_CLIENT_SECRET=your-hubspot-app-client-secret
PROXY_BASE_URL=https://your-domain.example.com
TOKEN_ENCRYPTION_KEY=<generate below>

# Optional
DATABASE_PATH=:memory:              # default; set a file path for persistence
AUTH_STATE_TTL_SECONDS=600          # default
AUTH_CODE_TTL_SECONDS=300           # default
LOG_LEVEL=INFO                      # default
ALLOWED_REDIRECT_DOMAINS='["api.powerva.microsoft.com"]'  # default
```

Generate `TOKEN_ENCRYPTION_KEY`:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Docker (recommended)

```bash
docker compose up -d --build
# Health check
curl http://localhost:8100/health
```

### Local

```bash
uv venv && uv pip install -e ".[dev]"
source .venv/bin/activate
uvicorn hubspot_mcp_proxy.app:create_app --factory --port 8000
```

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/.well-known/oauth-authorization-server` | RFC 8414 AS metadata |
| GET | `/.well-known/oauth-protected-resource` | RFC 9728 Protected Resource Metadata |
| POST | `/register` | RFC 7591 Dynamic Client Registration |
| GET | `/authorize` | OAuth authorize (injects PKCE) |
| GET | `/callback` | HubSpot OAuth callback |
| POST | `/token` | Token exchange / refresh |
| POST | `/mcp` | MCP HTTP reverse proxy (requires `Authorization` header) |
| GET | `/mcp` | OAuth discovery trigger (returns 401) |
| GET | `/health` | Health check |

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HUBSPOT_CLIENT_ID` | Yes | | HubSpot app client ID |
| `HUBSPOT_CLIENT_SECRET` | Yes | | HubSpot app client secret |
| `PROXY_BASE_URL` | Yes | | Public URL of this proxy |
| `TOKEN_ENCRYPTION_KEY` | Yes | | Fernet key for encrypting tokens at rest |
| `HUBSPOT_AUTH_URL` | No | `https://app.hubspot.com/oauth/authorize` | HubSpot authorization endpoint |
| `HUBSPOT_TOKEN_URL` | No | `https://api.hubapi.com/oauth/v1/token` | HubSpot token endpoint |
| `HUBSPOT_MCP_URL` | No | `https://mcp.hubspot.com` | HubSpot MCP server URL |
| `DATABASE_PATH` | No | `:memory:` | SQLite database path |
| `AUTH_STATE_TTL_SECONDS` | No | `600` | OAuth state TTL |
| `AUTH_CODE_TTL_SECONDS` | No | `300` | Proxy-issued auth code TTL |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `ALLOWED_REDIRECT_DOMAINS` | No | `["api.powerva.microsoft.com"]` | Allowed redirect URI domains for DCR |

## Development

```bash
# Run tests
source .venv/bin/activate && pytest

# Lint
source .venv/bin/activate && ruff check src/ tests/
```

Requires Python 3.12+.

## License

[MIT](LICENSE)
