variable "container_name" {
  description = "Blob container that bronze lands raw campaign files into."
  type        = string
  default     = "bronze-landing"
}

variable "location" {
  description = "Azure region for the landing zone."
  type        = string
  default     = "westeurope"
}

variable "storage_account_name" {
  description = "Storage account name (3-24 lowercase alphanumerics, globally unique)."
  type        = string
  default     = "stcampaignflowland"
}

variable "subscription_id" {
  description = "Azure subscription id."
  type        = string
  default     = "00000000-0000-0000-0000-000000000000"
}
