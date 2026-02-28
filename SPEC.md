# HubSpot MCP PKCE Proxy - Specification

## Problem Statement

HubSpot's remote MCP server (`https://mcp.hubspot.com`) requires OAuth 2.1 with
PKCE. Microsoft Copilot Studio supports OAuth 2.0 with Dynamic Discovery but
does **not** support PKCE. This proxy bridges that gap by intercepting the OAuth
flow, injecting PKCE parameters when talking to HubSpot, and passing through
HubSpot's actual tokens to Copilot Studio. MCP requests are HTTP-proxied
transparently.

## Architecture

```
Copilot Studio  <-->  PKCE Proxy  <-->  HubSpot
  (no PKCE)        (injects PKCE)      (requires PKCE)
```

The proxy presents itself as a standard OAuth 2.0 authorization server (no PKCE
advertised) to Copilot Studio, while internally handling the PKCE flow with
HubSpot.

## OAuth Flow

1. **Discovery** (RFC 8414): Copilot Studio fetches
   `/.well-known/oauth-authorization-server` from the proxy.
2. **Dynamic Client Registration** (RFC 7591): Copilot Studio registers via
   `POST /register`.
3. **Authorization**: Copilot Studio redirects user to proxy's `/authorize`.
   Proxy generates PKCE params and redirects to HubSpot's authorize endpoint.
4. **Callback**: HubSpot redirects back to proxy's `/callback` with auth code.
   Proxy exchanges code + PKCE verifier for tokens with HubSpot, generates a
   proxy auth code, and redirects to Copilot Studio's callback.
5. **Token Exchange**: Copilot Studio exchanges proxy auth code at `/token`.
   Proxy returns stored HubSpot tokens.
6. **Refresh**: Copilot Studio sends refresh_token to `/token`. Proxy forwards
   to HubSpot with HubSpot's client credentials.
7. **MCP Proxy**: Copilot Studio sends MCP requests to `/mcp` with Bearer token.
   Proxy forwards to HubSpot MCP server.

## HubSpot Endpoints

| Purpose | URL |
|---------|-----|
| Authorization | `https://app.hubspot.com/oauth/authorize` |
| Token Exchange | `https://api.hubapi.com/oauth/v1/token` |
| MCP Server | `https://mcp.hubspot.com` |

## Technology Stack

- **Runtime**: Python 3.12 + FastAPI
- **HTTP Client**: httpx (async)
- **Database**: SQLite via aiosqlite
- **Configuration**: pydantic-settings
- **Testing**: pytest + pytest-asyncio + respx
- **Linting**: ruff

## Infrastructure

- Docker container on `optiplex` host
- Traefik reverse proxy on `media_default` network
- Port mapping: 8100:8000
- SQLite database persisted via Docker volume

## Multi-User Support

The proxy supports multiple concurrent users through:
- Per-request PKCE state tracking (keyed by `state` parameter)
- Temporary proxy auth codes (keyed by generated code)
- No server-side session required after token exchange

## Scope

More than a proof of concept, less than enterprise. Reliable and practical.
