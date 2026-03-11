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
  description = "Minimum number of nodes in the primary node pool"
  type        = number
  default     = 2
}

variable "gke_node_max_count" {
  description = "Maximum number of nodes in the primary node pool autoscaler"
  type        = number
  default     = 3
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
  default     = "terrier-connect"
}

variable "platform_namespace" {
  description = "Kubernetes namespace for shared data and messaging services"
  type        = string
  default     = "terrier-platform"
}

variable "k8s_cluster_domain" {
  description = "Kubernetes cluster DNS domain"
  type        = string
  default     = "cluster.local"
}

variable "platform_storage_class" {
  description = "Optional storage class for Redis, Kafka, Cassandra, and Elasticsearch PVCs"
  type        = string
  default     = ""
}

variable "redis_storage_size" {
  description = "Persistent volume size for Redis"
  type        = string
  default     = "8Gi"
}

variable "kafka_storage_size" {
  description = "Persistent volume size for Kafka"
  type        = string
  default     = "20Gi"
}

variable "cassandra_storage_size" {
  description = "Persistent volume size for Cassandra"
  type        = string
  default     = "20Gi"
}

variable "elasticsearch_storage_size" {
  description = "Persistent volume size for Elasticsearch"
  type        = string
  default     = "20Gi"
}

variable "gke_workload_sa_name" {
  description = "GCP service account name for Workload Identity"
  type        = string
  default     = "terrier-connect-gke-sa"
}

variable "github_owner" {
  description = "GitHub username or organisation that owns the repo"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name (without the owner prefix)"
  type        = string
  default     = "terrier-connect"
}

variable "github_connection_name" {
  description = "Name of the 2nd-gen Cloud Build GitHub connection created in the GCP Console"
  type        = string
  default     = "terrier-connect-github"
}

variable "alert_notification_email" {
  description = "Optional email address for Cloud Monitoring alert notifications"
  type        = string
  default     = ""
}

variable "enable_gateway_slos" {
  description = "Create gateway metric-backed SLOs and burn-rate alerts after Managed Prometheus metrics are visible in Cloud Monitoring"
  type        = bool
  default     = false
}

variable "enable_metric_alert_policies" {
  description = "Create PromQL metric-backed alert policies after Prometheus metrics are visible in Cloud Monitoring"
  type        = bool
  default     = false
}
