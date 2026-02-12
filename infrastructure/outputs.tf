output "artifact_registry_url" {
  description = "Artifact Registry repository URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}"
}

output "client_image_url" {
  description = "Client Docker image URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}/client:latest"
}

output "server_image_url" {
  description = "Server Docker image URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}/server:latest"
}

output "terraform_state_bucket" {
  description = "GCS bucket for Terraform state"
  value       = google_storage_bucket.tf_state.name
}

output "gke_cluster_name" {
  description = "GKE cluster name"
  value       = google_container_cluster.gke.name
}

output "gke_region" {
  description = "GKE cluster region"
  value       = var.region
}

output "cloudsql_connection_name" {
  description = "Cloud SQL instance connection name"
  value       = google_sql_database_instance.db.connection_name
}

output "media_bucket_name" {
  description = "GCS bucket for media"
  value       = google_storage_bucket.media.name
}

output "gke_workload_service_account" {
  description = "GCP service account for Workload Identity"
  value       = google_service_account.gke_workload.email
}

output "ingress_ip_address" {
  description = "Global static IP for Ingress"
  value       = google_compute_global_address.lb_ip.address
}

output "domain_name" {
  description = "Root domain"
  value       = var.domain_name
}
