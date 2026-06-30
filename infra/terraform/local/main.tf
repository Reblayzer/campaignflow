terraform {
  required_version = ">= 1.5"
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

# Local bronze landing zone on the Azurite emulator. azurerm targets the Azure
# Resource Manager control plane, which Azurite does not emulate, so the
# container is created through the blob data plane by a helper script. This root
# module applies with no cloud account: `terraform apply` against running
# Azurite stands up a runnable landing zone. The production-Azure equivalent
# lives in ../azure.
resource "null_resource" "azurite_container" {
  triggers = {
    container = var.container_name
  }

  provisioner "local-exec" {
    command = "python3 ${path.module}/scripts/create_container.py"
    environment = {
      AZURE_STORAGE_CONNECTION_STRING = var.azurite_connection_string
      CONTAINER_NAME                  = var.container_name
    }
  }
}
