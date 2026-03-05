# Dynamic service tag resolution for IP-restricted ingress.
# Resolves Microsoft-published CIDR ranges at plan/apply time so we
# never hardcode IPs that rotate weekly.

data "azurerm_network_service_tags" "ppplex_uksouth" {
  service         = "PowerPlatformPlex"
  location        = var.location
  location_filter = var.location
}

data "azurerm_network_service_tags" "azconn_uksouth" {
  service         = "AzureConnectors"
  location        = var.location
  location_filter = var.location
}

locals {
  ppplex_rules = [for i, cidr in data.azurerm_network_service_tags.ppplex_uksouth.ipv4_cidrs : {
    name = "PPPlex-${i}"
    cidr = cidr
  }]

  azconn_rules = [for i, cidr in data.azurerm_network_service_tags.azconn_uksouth.ipv4_cidrs : {
    name = "AzConn-${i}"
    cidr = cidr
  }]

  admin_rules = var.admin_ip_cidr != "" ? [{ name = "Admin", cidr = var.admin_ip_cidr }] : []

  all_allow_rules = var.enable_ip_restrictions ? concat(local.admin_rules, local.ppplex_rules, local.azconn_rules) : []
}
