resource "azurerm_container_app_environment" "this" {
  name                = "cae-${var.project}-${var.environment}-${var.instance}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location

  tags = azurerm_resource_group.this.tags
}
