resource "azurerm_user_assigned_identity" "this" {
  name                = "id-${var.project}-${var.environment}-${var.instance}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location

  tags = azurerm_resource_group.this.tags
}
