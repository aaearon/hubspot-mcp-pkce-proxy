variable "project" {
  description = "Project name used in resource naming"
  type        = string
  default     = "hubspot-mcp"
}

variable "environment" {
  description = "Environment label (lab, dev, prod)"
  type        = string
  default     = "lab"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "uksouth"
}

variable "instance" {
  description = "Instance number for resource naming"
  type        = string
  default     = "001"
}

variable "existing_acr_name" {
  description = "Name of the existing Azure Container Registry"
  type        = string
}

variable "existing_acr_resource_group" {
  description = "Resource group containing the existing ACR"
  type        = string
}

variable "existing_dns_zone_name" {
  description = "Existing Azure DNS zone name"
  type        = string
}

variable "existing_dns_zone_resource_group" {
  description = "Resource group containing the existing DNS zone"
  type        = string
}

variable "custom_domain" {
  description = "Custom domain for the Container App"
  type        = string
}

variable "container_image" {
  description = "Full container image reference (ACR/repo:tag)"
  type        = string
}

variable "hubspot_client_id" {
  description = "HubSpot OAuth client ID"
  type        = string
  sensitive   = true
}

variable "hubspot_client_secret" {
  description = "HubSpot OAuth client secret"
  type        = string
  sensitive   = true
}

variable "token_encryption_key" {
  description = "Fernet key for encrypting tokens at rest"
  type        = string
  sensitive   = true
}

variable "proxy_base_url" {
  description = "Public base URL of the proxy"
  type        = string
}

variable "hubspot_authorize_url" {
  description = "HubSpot OAuth authorize endpoint"
  type        = string
  default     = "https://app.hubspot.com/oauth/authorize"
}

variable "hubspot_token_url" {
  description = "HubSpot OAuth token endpoint"
  type        = string
  default     = "https://api.hubapi.com/oauth/v1/token"
}

variable "hubspot_mcp_url" {
  description = "HubSpot MCP server URL"
  type        = string
  default     = "https://mcp.hubspot.com"
}

variable "hubspot_scopes" {
  description = "HubSpot OAuth scopes"
  type        = string
  default     = "oauth crm.objects.contacts.read crm.objects.contacts.write crm.objects.companies.read crm.objects.deals.read"
}

variable "acme_email" {
  description = "Email address for Let's Encrypt ACME registration"
  type        = string
}

variable "admin_ip_cidr" {
  description = "Admin IP CIDR for Container App access (e.g. 203.0.113.10/32). Leave empty to skip."
  type        = string
  default     = ""
}

variable "log_level" {
  description = "Application log level (DEBUG, INFO, WARNING, ERROR)"
  type        = string
  default     = "INFO"
}

variable "enable_ip_restrictions" {
  description = "Enable IP-based ingress restrictions. Set to false to allow all traffic (useful for debugging Copilot Studio connectivity)."
  type        = bool
  default     = true
}
