output "resource_group_name" {
  description = "Name of the resource group"
  value       = azurerm_resource_group.this.name
}

output "container_app_name" {
  description = "Name of the Container App"
  value       = azurerm_container_app.this.name
}

output "container_app_fqdn" {
  description = "Default FQDN of the Container App"
  value       = azurerm_container_app.this.ingress[0].fqdn
}

output "custom_domain" {
  description = "Custom domain for the Container App"
  value       = var.custom_domain
}

output "health_url" {
  description = "Health check URL"
  value       = "https://${var.custom_domain}/health"
}

output "managed_identity_client_id" {
  description = "Client ID of the managed identity"
  value       = azurerm_user_assigned_identity.this.client_id
}

output "acr_name" {
  description = "Name of the Azure Container Registry"
  value       = data.azurerm_container_registry.existing.name
}
