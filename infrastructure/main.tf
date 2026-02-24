terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

data "google_project" "project" {}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "compute.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "container.googleapis.com",
    "sqladmin.googleapis.com",
    "servicenetworking.googleapis.com",
    "dns.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "secretmanager.googleapis.com"
  ])
  service            = each.key
  disable_on_destroy = false
}

# VPC and subnet for GKE
resource "google_compute_network" "vpc_network" {
  name                    = "terrier-connect-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

resource "google_compute_subnetwork" "gke_subnet" {
  name          = "terrier-connect-subnet"
  region        = var.region
  network       = google_compute_network.vpc_network.id
  ip_cidr_range = var.subnet_cidr

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = var.pods_cidr
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = var.services_cidr
  }
}

# Private Service Access for Cloud SQL
resource "google_compute_global_address" "private_services" {
  name          = "terrier-connect-psa"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc_network.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc_network.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]
  deletion_policy         = "ABANDON"
}

# GKE cluster + node pool
resource "google_container_cluster" "gke" {
  name                     = var.gke_cluster_name
  location                 = var.region
  deletion_protection      = false
  remove_default_node_pool = true
  initial_node_count       = 1

  network    = google_compute_network.vpc_network.id
  subnetwork = google_compute_subnetwork.gke_subnet.id

  node_config {
    disk_size_gb = 30
  }
  
  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  release_channel {
    channel = "REGULAR"
  }

  depends_on = [google_project_service.apis]
}

resource "google_container_node_pool" "primary_nodes" {
  name       = "primary-node-pool"
  location   = var.region
  cluster    = google_container_cluster.gke.name
  node_count = var.gke_node_count

  node_config {
    machine_type = var.gke_node_machine_type
    disk_size_gb = 30
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}

# Artifact Registry Repository
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "terrier-connect-repo"
  description   = "Docker repository for Terrier Connect"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

# Cloud SQL (Postgres) with private IP
resource "google_sql_database_instance" "db" {
  name             = var.cloudsql_instance_name
  database_version = "POSTGRES_15"
  region           = var.region
  deletion_protection = false

  settings {
    tier              = var.cloudsql_tier
    availability_type = var.cloudsql_availability_type

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc_network.id
    }

    backup_configuration {
      enabled = true
    }
  }

  depends_on = [google_service_networking_connection.private_vpc_connection]
}

resource "google_sql_database" "app_db" {
  name     = var.db_name
  instance = google_sql_database_instance.db.name
}

resource "google_sql_user" "app_user" {
  name     = var.db_user
  instance = google_sql_database_instance.db.name
  password = var.db_password
}

# Media bucket
resource "google_storage_bucket" "media" {
  name          = var.media_bucket_name
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }
}

resource "google_storage_bucket_iam_member" "media_public" {
  count  = var.media_bucket_public ? 1 : 0
  bucket = google_storage_bucket.media.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# Workload Identity: GSA for server pods
resource "google_service_account" "gke_workload" {
  account_id   = var.gke_workload_sa_name
  display_name = "Terrier Connect GKE Workload SA"
}

resource "google_project_iam_member" "gke_workload_cloudsql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.gke_workload.email}"
}

resource "google_storage_bucket_iam_member" "gke_workload_storage" {
  bucket = google_storage_bucket.media.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.gke_workload.email}"
}

resource "google_service_account_iam_member" "gke_workload_identity" {
  service_account_id = google_service_account.gke_workload.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.k8s_namespace}/server]"

  depends_on = [google_container_cluster.gke]
}

# Static IP for Ingress
resource "google_compute_global_address" "lb_ip" {
  name = var.lb_ip_name

  depends_on = [google_project_service.apis]
}

# Cloud DNS
resource "google_dns_managed_zone" "primary" {
  name     = var.dns_zone_name
  dns_name = "${var.domain_name}."

  depends_on = [google_project_service.apis]
}

resource "google_dns_record_set" "root_a" {
  name         = "${var.domain_name}."
  managed_zone = google_dns_managed_zone.primary.name
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_global_address.lb_ip.address]
}

resource "google_dns_record_set" "www_a" {
  name         = "www.${var.domain_name}."
  managed_zone = google_dns_managed_zone.primary.name
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_global_address.lb_ip.address]
}

# Dedicated service account for Cloud Build (both gcloud builds submit and GitOps trigger).
# Modern GCP projects do not auto-create the legacy PROJECT_NUMBER@cloudbuild SA,
# so we create and manage our own with least-privilege roles.
resource "google_service_account" "cloudbuild_sa" {
  account_id   = "terrier-connect-cloudbuild-sa"
  display_name = "Terrier Connect Cloud Build SA"
  depends_on   = [google_project_service.apis]
}

# Allow the Cloud Build service agent to impersonate our SA.
# Required whenever a user-managed SA is specified on a build.
resource "google_service_account_iam_member" "cloudbuild_agent_token_creator" {
  service_account_id = google_service_account.cloudbuild_sa.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
}

# IAM for Cloud Build — all roles in one place, managed via for_each.
# Add roles here as needed; Terraform will create/destroy bindings automatically.
locals {
  cloudbuild_sa = "serviceAccount:${google_service_account.cloudbuild_sa.email}"
  cloudbuild_roles = toset([
    "roles/editor",                       # broad base required for Terraform apply
    "roles/container.admin",              # GKE deployments
    "roles/iam.serviceAccountAdmin",      # manage service accounts
    "roles/iam.serviceAccountUser",       # act as other SAs
    "roles/cloudsql.admin",               # Cloud SQL
    "roles/dns.admin",                    # Cloud DNS
    "roles/artifactregistry.writer",      # push images to Artifact Registry
    "roles/secretmanager.secretAccessor", # read Secret Manager secrets
    "roles/storage.admin",                # Terraform state bucket
    "roles/logging.logWriter",            # write Cloud Build logs
  ])
}

resource "google_project_iam_member" "cloudbuild_roles" {
  for_each   = local.cloudbuild_roles
  project    = var.project_id
  role       = each.value
  member     = local.cloudbuild_sa
  depends_on = [google_project_service.apis]
}

# Secret Manager — secret shells only (values populated manually after first apply)
# Run after first apply:
#   echo -n "<value>" | gcloud secrets versions add terrier-connect-db-password --data-file=-
#   echo -n "<value>" | gcloud secrets versions add terrier-connect-django-secret-key --data-file=-
#   echo -n "<value>" | gcloud secrets versions add terrier-connect-maps-api-key --data-file=-
resource "google_secret_manager_secret" "db_password" {
  secret_id = "terrier-connect-db-password"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "django_secret_key" {
  secret_id = "terrier-connect-django-secret-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "maps_api_key" {
  secret_id = "terrier-connect-maps-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

# Secret Manager access for Cloud Build SA is granted at the project level
# via google_project_iam_member.cloudbuild_roles above (roles/secretmanager.secretAccessor).

# GitOps - 2nd gen Cloud Build GitHub connection
# The connection itself must be created once in the GCP Console (requires OAuth):
#   Cloud Build -> Repositories -> Create host connection -> GitHub
# Then set github_connection_name in terraform.tfvars to match the connection name.
resource "google_cloudbuildv2_repository" "github_repo" {
  name              = var.github_repo
  location          = var.region
  parent_connection = "projects/${var.project_id}/locations/${var.region}/connections/${var.github_connection_name}"
  remote_uri        = "https://github.com/${var.github_owner}/${var.github_repo}.git"

  depends_on = [google_project_service.apis]
}

# GitOps Cloud Build trigger - fires on every push to main
resource "google_cloudbuild_trigger" "gitops_main" {
  name        = "terrier-connect-main"
  description = "GitOps: full build + deploy on push to main"
  location    = var.region

  repository_event_config {
    repository = google_cloudbuildv2_repository.github_repo.id
    push {
      branch = "^main$"
    }
  }

  filename = "cloudbuild.yaml"

  # Use the dedicated Cloud Build SA created above.
  service_account = google_service_account.cloudbuild_sa.id

  # Non-secret substitutions; secrets come from Secret Manager via availableSecrets
  substitutions = {
    _REGION                   = var.region
    _CLUSTER_NAME             = var.gke_cluster_name
    _DOMAIN_NAME              = var.domain_name
    _CLOUDSQL_INSTANCE_NAME   = var.cloudsql_instance_name
    _REACT_APP_API_BASE_URL   = "/api"
    _REACT_APP_MEDIA_BASE_URL = "/media"
  }

  depends_on = [
    google_project_service.apis,
    google_project_iam_member.cloudbuild_roles,
  ]
}
