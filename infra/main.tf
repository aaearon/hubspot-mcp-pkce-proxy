terraform {
  required_version = ">= 1.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    acme = {
      source  = "vancluever/acme"
      version = "~> 2.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  # Local state for PoC. Example Azure Storage backend:
  # backend "azurerm" {
  #   resource_group_name  = "rg-example"
  #   storage_account_name = "stexampletfstate001"
  #   container_name       = "tfstate"
  #   key                  = "hubspot-mcp.tfstate"
  # }
}

provider "azurerm" {
  features {}
}

provider "acme" {
  server_url = "https://acme-v02.api.letsencrypt.org/directory"
}

data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "this" {
  name     = "rg-${var.project}-${var.environment}-${var.instance}"
  location = var.location

  tags = {
    project     = var.project
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "azurerm_resource_provider_registration" "container_apps" {
  name = "Microsoft.App"
}
