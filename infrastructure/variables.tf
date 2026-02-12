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

variable "subnet_cidr" {
  description = "Primary subnet CIDR for GKE"
  type        = string
  default     = "10.10.0.0/16"
}

variable "pods_cidr" {
  description = "Secondary CIDR for GKE pods"
  type        = string
  default     = "10.20.0.0/16"
}

variable "services_cidr" {
  description = "Secondary CIDR for GKE services"
  type        = string
  default     = "10.30.0.0/16"
}

variable "gke_cluster_name" {
  description = "GKE cluster name"
  type        = string
  default     = "terrier-connect-gke"
}

variable "gke_node_machine_type" {
  description = "Machine type for GKE node pool"
  type        = string
  default     = "e2-medium"
}

variable "gke_node_count" {
  description = "Number of nodes in the primary node pool"
  type        = number
  default     = 2
}

variable "cloudsql_instance_name" {
  description = "Cloud SQL instance name"
  type        = string
  default     = "terrier-connect-db"
}

variable "cloudsql_tier" {
  description = "Cloud SQL instance tier"
  type        = string
  default     = "db-f1-micro"
}

variable "cloudsql_availability_type" {
  description = "Cloud SQL availability type (ZONAL or REGIONAL)"
  type        = string
  default     = "ZONAL"
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "terrier-connect-prod"
}

variable "db_user" {
  description = "Database user"
  type        = string
  default     = "appuser"
}

variable "db_password" {
  description = "Database user password"
  type        = string
  sensitive   = true
}

variable "media_bucket_name" {
  description = "GCS bucket for media uploads"
  type        = string
  default     = "terrier-connect-media"
}

variable "media_bucket_public" {
  description = "Whether to make the media bucket publicly readable"
  type        = bool
  default     = true
}

variable "dns_zone_name" {
  description = "Cloud DNS managed zone name"
  type        = string
}

variable "domain_name" {
  description = "Root domain name (example.com)"
  type        = string
}

variable "lb_ip_name" {
  description = "Global static IP name for GKE Ingress"
  type        = string
  default     = "terrier-connect-ip"
}

variable "k8s_namespace" {
  description = "Kubernetes namespace for the server workload"
  type        = string
  default     = "default"
}

variable "gke_workload_sa_name" {
  description = "GCP service account name for Workload Identity"
  type        = string
  default     = "terrier-connect-gke-sa"
}
