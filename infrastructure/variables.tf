variable "project_id" {
  description = "The ID of the GCP project"
  type        = string
}

variable "region" {
  description = "The region to deploy to"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "The zone to deploy to"
  type        = string
  default     = "us-central1-a"
}

variable "machine_type" {
  description = "The machine type for the instance"
  type        = string
  default     = "e2-medium"
}

variable "instance_name" {
  description = "The name of the VM instance"
  type        = string
  default     = "terrier-connect-vm"
}

variable "github_owner" {
  description = "GitHub repository owner"
  type        = string
  default     = "eth-ts-x"
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "terrier-connect"
}
