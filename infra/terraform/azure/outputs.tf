output "container_name" {
  description = "Blob container bronze reads raw campaign files from."
  value       = azurerm_storage_container.bronze.name
}

output "storage_account_name" {
  description = "Storage account hosting the landing container."
  value       = azurerm_storage_account.landing.name
}
