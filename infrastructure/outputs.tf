output "instance_name" {
  value = google_compute_instance.vm_instance.name
}

output "public_ip" {
  value = google_compute_address.static_ip.address
}

output "connection_command" {
  value = "gcloud compute ssh ${google_compute_instance.vm_instance.name} --zone=${var.zone}"
}

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

output "vm_service_account" {
  description = "Service account used by the VM"
  value       = google_service_account.vm_service_account.email
}

output "app_url" {
  description = "Application URL"
  value       = "http://${google_compute_address.static_ip.address}:3002"
}

output "api_url" {
  description = "API URL"
  value       = "http://${google_compute_address.static_ip.address}:8000"
}
