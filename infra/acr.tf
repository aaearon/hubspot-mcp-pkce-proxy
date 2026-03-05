data "azurerm_container_registry" "existing" {
  name                = var.existing_acr_name
  resource_group_name = var.existing_acr_resource_group
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = data.azurerm_container_registry.existing.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.this.principal_id
}
