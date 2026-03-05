# Custom domain with Let's Encrypt TLS certificate binding.

resource "azurerm_container_app_custom_domain" "this" {
  name                                     = var.custom_domain
  container_app_id                         = azurerm_container_app.this.id
  container_app_environment_certificate_id = azurerm_container_app_environment_certificate.this.id
  certificate_binding_type                 = "SniEnabled"

  depends_on = [
    azurerm_dns_cname_record.app,
    azurerm_dns_txt_record.domain_verification,
  ]
}
