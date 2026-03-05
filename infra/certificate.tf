# Let's Encrypt certificate via ACME DNS-01 challenge against Azure DNS.
# Replaces the slow Azure managed certificate (10-20 min provisioning).
# Auto-renews on terraform apply when <30 days remain (90-day LE certs).

resource "tls_private_key" "acme_account" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "acme_registration" "this" {
  account_key_pem = tls_private_key.acme_account.private_key_pem
  email_address   = var.acme_email
}

resource "random_password" "cert_pfx" {
  length  = 24
  special = true
}

resource "acme_certificate" "this" {
  account_key_pem          = acme_registration.this.account_key_pem
  common_name              = var.custom_domain
  key_type                 = "4096"
  min_days_remaining       = 30
  certificate_p12_password = random_password.cert_pfx.result

  dns_challenge {
    provider = "azuredns"
    config = {
      AZURE_RESOURCE_GROUP  = var.existing_dns_zone_resource_group
      AZURE_ZONE_NAME       = var.existing_dns_zone_name
      AZURE_SUBSCRIPTION_ID = data.azurerm_client_config.current.subscription_id
      AZURE_TTL             = 60
    }
  }
}

resource "azurerm_container_app_environment_certificate" "this" {
  name                         = "le-${replace(var.custom_domain, ".", "-")}"
  container_app_environment_id = azurerm_container_app_environment.this.id
  certificate_blob_base64      = acme_certificate.this.certificate_p12
  certificate_password         = random_password.cert_pfx.result
}
