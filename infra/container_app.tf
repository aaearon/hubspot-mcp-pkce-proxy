resource "azurerm_container_app" "this" {
  name                         = "ca-${var.project}-${var.environment}-${var.instance}"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = azurerm_resource_group.this.name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.this.id]
  }

  registry {
    server   = data.azurerm_container_registry.existing.login_server
    identity = azurerm_user_assigned_identity.this.id
  }

  secret {
    name  = "hubspot-client-id"
    value = var.hubspot_client_id
  }

  secret {
    name  = "hubspot-client-secret"
    value = var.hubspot_client_secret
  }

  secret {
    name  = "token-encryption-key"
    value = var.token_encryption_key
  }

  ingress {
    external_enabled           = true
    target_port                = 8000
    transport                  = "http"
    allow_insecure_connections = false

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }

    dynamic "ip_security_restriction" {
      for_each = local.all_allow_rules
      content {
        name             = ip_security_restriction.value.name
        ip_address_range = ip_security_restriction.value.cidr
        action           = "Allow"
      }
    }
  }

  template {
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "proxy"
      image  = var.container_image
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name        = "HUBSPOT_CLIENT_ID"
        secret_name = "hubspot-client-id"
      }

      env {
        name        = "HUBSPOT_CLIENT_SECRET"
        secret_name = "hubspot-client-secret"
      }

      env {
        name        = "TOKEN_ENCRYPTION_KEY"
        secret_name = "token-encryption-key"
      }

      env {
        name  = "PROXY_BASE_URL"
        value = var.proxy_base_url
      }

      env {
        name  = "HUBSPOT_AUTHORIZE_URL"
        value = var.hubspot_authorize_url
      }

      env {
        name  = "HUBSPOT_TOKEN_URL"
        value = var.hubspot_token_url
      }

      env {
        name  = "HUBSPOT_MCP_URL"
        value = var.hubspot_mcp_url
      }

      env {
        name  = "HUBSPOT_SCOPES"
        value = var.hubspot_scopes
      }

      env {
        name  = "LOG_LEVEL"
        value = var.log_level
      }

      liveness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/health"

        initial_delay    = 5
        interval_seconds = 30
      }

      readiness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/health"

        interval_seconds = 10
      }

      startup_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/health"

        interval_seconds        = 5
        failure_count_threshold = 10
      }
    }
  }

  depends_on = [
    azurerm_role_assignment.acr_pull,
  ]

  tags = azurerm_resource_group.this.tags
}
