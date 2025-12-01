terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

resource "google_compute_network" "vpc_network" {
  name = "terrier-connect-network"
}

resource "google_compute_firewall" "allow_ssh" {
  name    = "allow-ssh"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
}

resource "google_compute_firewall" "allow_http_app" {
  name    = "allow-http-app"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["80", "443", "3002", "8000"]
  }

  source_ranges = ["0.0.0.0/0"]
}

resource "google_compute_address" "static_ip" {
  name = "terrier-connect-ip"
}

resource "google_compute_instance" "vm_instance" {
  name         = var.instance_name
  machine_type = var.machine_type
  tags         = ["http-server", "https-server"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
    }
  }

  network_interface {
    network = google_compute_network.vpc_network.name
    access_config {
      nat_ip = google_compute_address.static_ip.address
    }
  }

  metadata_startup_script = templatefile("${path.module}/startup.sh", {
    region              = var.region
    docker_image_client = "${var.region}-docker.pkg.dev/${var.project_id}/terrier-connect-repo/client:latest"
    docker_image_server = "${var.region}-docker.pkg.dev/${var.project_id}/terrier-connect-repo/server:latest"
  })

  service_account {
    email  = google_service_account.vm_service_account.email
    scopes = ["cloud-platform"]
  }

  depends_on = [
    google_artifact_registry_repository.repo,
    google_service_account.vm_service_account
  ]
}

# Enable necessary APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "compute.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com"
  ])
  service            = each.key
  disable_on_destroy = false
}

# Artifact Registry Repository
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "terrier-connect-repo"
  description   = "Docker repository for Terrier Connect"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

# GCS Bucket for Terraform State (Optional: Create this manually first if you want to use it as backend immediately)
resource "google_storage_bucket" "tf_state" {
  name          = "${var.project_id}-tf-state"
  location      = var.region
  force_destroy = false

  versioning {
    enabled = true
  }
  
  depends_on = [google_project_service.apis]
}

# Get project details for IAM
data "google_project" "project" {
}

# Service Account for the VM
resource "google_service_account" "vm_service_account" {
  account_id   = "terrier-connect-vm-sa"
  display_name = "Terrier Connect VM Service Account"
  depends_on   = [google_project_service.apis]
}

# Grant VM Service Account permission to pull from Artifact Registry
resource "google_project_iam_member" "vm_artifact_registry_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.vm_service_account.email}"
}

# Grant VM Service Account permission to write logs
resource "google_project_iam_member" "vm_logging_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.vm_service_account.email}"
}

# Grant Cloud Build Service Account permissions
resource "google_project_iam_member" "cloudbuild_editor" {
  project    = var.project_id
  role       = "roles/editor"
  member     = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
  depends_on = [google_project_service.apis]
}

# Grant Cloud Build permission to push to Artifact Registry
resource "google_project_iam_member" "cloudbuild_artifact_registry" {
  project    = var.project_id
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
  depends_on = [google_project_service.apis]
}

# Grant Cloud Build permission to manage Compute Engine
resource "google_project_iam_member" "cloudbuild_compute_admin" {
  project    = var.project_id
  role       = "roles/compute.admin"
  member     = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
  depends_on = [google_project_service.apis]
}

# Grant Cloud Build permission to use service accounts
resource "google_project_iam_member" "cloudbuild_service_account_user" {
  project    = var.project_id
  role       = "roles/iam.serviceAccountUser"
  member     = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
  depends_on = [google_project_service.apis]
}

# Cloud Build Trigger (optional - can also be created via console)
resource "google_cloudbuild_trigger" "deploy_trigger" {
  name        = "terrier-connect-deploy"
  description = "Trigger deployment on push to master branch"
  
  github {
    owner = var.github_owner
    name  = var.github_repo
    push {
      branch = "^master$"
    }
  }

  filename   = "cloudbuild.yaml"
  depends_on = [google_project_service.apis]
}
