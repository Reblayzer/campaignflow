terraform {
  required_version = ">= 1.5"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

# Production bronze landing zone on real Azure. The local emulator equivalent
# lives in ../local. Apply this with a service principal:
#   ARM_SUBSCRIPTION_ID / ARM_TENANT_ID / ARM_CLIENT_ID / ARM_CLIENT_SECRET.
provider "azurerm" {
  features {}
  subscription_id                 = var.subscription_id
  resource_provider_registrations = "none"
}

resource "azurerm_resource_group" "landing" {
  name     = "rg-campaignflow-landing"
  location = var.location
}

resource "azurerm_storage_account" "landing" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.landing.name
  location                 = azurerm_resource_group.landing.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
}

resource "azurerm_storage_container" "bronze" {
  name                  = var.container_name
  storage_account_id    = azurerm_storage_account.landing.id
  container_access_type = "private"
}
