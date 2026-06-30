variable "container_name" {
  description = "Blob container that bronze lands raw campaign files into."
  type        = string
  default     = "bronze-landing"
}

variable "azurite_connection_string" {
  description = "Azurite blob connection string."
  type        = string
  sensitive   = true
  # Azurite's well-known public emulator account (not a secret).
  default = "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
}
