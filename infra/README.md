# Infrastructure

Terraform IaC for deploying the HubSpot MCP PKCE Proxy to Azure Container Apps.

## Architecture

- **Azure Container Apps** — serverless container hosting (single revision, 0-1 replicas)
- **Let's Encrypt TLS** — ACME provider with DNS-01 challenge, auto-renews on `terraform apply` when <30 days remain
- **Dynamic IP allowlisting** — ingress restricted to Microsoft PowerPlatformPlex and AzureConnectors service tags (resolved dynamically, not hardcoded)
- **User-assigned managed identity** — pulls images from ACR without registry credentials
- **In-memory SQLite** — no persistent volumes; all state is transient and auto-recoverable

## Prerequisites

- [Terraform](https://www.terraform.io/) >= 1.5
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/) (`az`), authenticated
- An existing Azure Container Registry (ACR)
- An existing Azure DNS zone

## Variables

### Required (no defaults)

| Variable | Type | Sensitive | Description |
|----------|------|-----------|-------------|
| `existing_acr_name` | string | | Name of the existing ACR |
| `existing_acr_resource_group` | string | | Resource group containing the ACR |
| `existing_dns_zone_name` | string | | Existing Azure DNS zone name |
| `existing_dns_zone_resource_group` | string | | Resource group containing the DNS zone |
| `custom_domain` | string | | Custom domain for the Container App |
| `container_image` | string | | Full image reference (`myacr.azurecr.io/repo:tag`) |
| `hubspot_client_id` | string | Yes | HubSpot OAuth client ID |
| `hubspot_client_secret` | string | Yes | HubSpot OAuth client secret |
| `token_encryption_key` | string | Yes | Fernet key for encrypting tokens at rest |
| `proxy_base_url` | string | | Public base URL of the proxy |
| `acme_email` | string | | Email for Let's Encrypt registration |

### Optional (with defaults)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `project` | string | `hubspot-mcp` | Project name for resource naming |
| `environment` | string | `lab` | Environment label (lab, dev, prod) |
| `location` | string | `uksouth` | Azure region |
| `instance` | string | `001` | Instance number for resource naming |
| `hubspot_authorize_url` | string | `https://app.hubspot.com/oauth/authorize` | HubSpot authorize endpoint |
| `hubspot_token_url` | string | `https://api.hubapi.com/oauth/v1/token` | HubSpot token endpoint |
| `hubspot_mcp_url` | string | `https://mcp.hubspot.com` | HubSpot MCP server URL |
| `hubspot_scopes` | string | *(contacts, companies, deals)* | HubSpot OAuth scopes |
| `admin_ip_cidr` | string | `""` | Admin IP CIDR for access (e.g., `203.0.113.10/32`) |
| `log_level` | string | `INFO` | Application log level |
| `enable_ip_restrictions` | bool | `true` | Toggle IP-based ingress restrictions |

## Deployment

```bash
# Full deploy (infra + build + update + health check)
./deploy.sh

# Plan only (no apply)
./deploy.sh --plan-only

# Code-only change (skip Terraform)
./deploy.sh --skip-infra

# Infra-only change (skip container build)
./deploy.sh --skip-build
```

The deploy script runs four phases:

1. **Infrastructure** — `terraform init`, `plan`, `apply`
2. **Build** — `az acr build` to build and push the image
3. **Update** — `az containerapp update` with the new image
4. **Verification** — health check against the Container App FQDN

## Outputs

| Output | Description |
|--------|-------------|
| `resource_group_name` | Resource group name |
| `container_app_name` | Container App name |
| `container_app_fqdn` | Default FQDN |
| `custom_domain` | Custom domain |
| `health_url` | Health check URL (`https://{custom_domain}/health`) |
| `managed_identity_client_id` | Managed identity client ID |
| `acr_name` | ACR name |

## Naming convention

Resources follow the pattern `{type}-{project}-{environment}-{instance}`:

| Resource | Example |
|----------|---------|
| Resource group | `rg-hubspot-mcp-lab-001` |
| Managed identity | `id-hubspot-mcp-lab-001` |
| Container App Environment | `cae-hubspot-mcp-lab-001` |
| Container App | `ca-hubspot-mcp-lab-001` |

## Validation

Run the Terraform validation suite:

```bash
./tests/validate.sh
```

Checks include:
- `terraform fmt`, `init`, and `validate`
- IP security restrictions present and HTTPS-only ingress
- Dynamic network service tags (not hardcoded CIDRs)
- ACME certificate resource (not Azure managed certs)
- `TOKEN_ENCRYPTION_KEY` secret configured
- No volume mounts or storage (in-memory SQLite)
- No org-specific defaults in variables
- IP restriction toggle variable exists

## Security notes

- **IP restrictions** are enabled by default. Set `enable_ip_restrictions = false` to allow all traffic (useful for debugging Copilot Studio connectivity).
- **Secrets** (`hubspot_client_id`, `hubspot_client_secret`, `token_encryption_key`) are stored as Container App secrets and injected as environment variables.
- **No persistent storage** — the database runs in-memory. Restarting the container clears all state, which is by design (all data is auto-recoverable from HubSpot).
- **Terraform state** is local by default. See `main.tf` for an Azure Storage backend example.
