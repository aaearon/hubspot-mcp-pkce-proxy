data "azurerm_dns_zone" "existing" {
  name                = var.existing_dns_zone_name
  resource_group_name = var.existing_dns_zone_resource_group
}

resource "azurerm_dns_cname_record" "app" {
  name                = split(".", var.custom_domain)[0]
  zone_name           = data.azurerm_dns_zone.existing.name
  resource_group_name = data.azurerm_dns_zone.existing.resource_group_name
  ttl                 = 300
  record              = azurerm_container_app.this.ingress[0].fqdn
}

resource "azurerm_dns_txt_record" "domain_verification" {
  name                = "asuid.${split(".", var.custom_domain)[0]}"
  zone_name           = data.azurerm_dns_zone.existing.name
  resource_group_name = data.azurerm_dns_zone.existing.resource_group_name
  ttl                 = 300

  record {
    value = azurerm_container_app_environment.this.custom_domain_verification_id
  }
}
