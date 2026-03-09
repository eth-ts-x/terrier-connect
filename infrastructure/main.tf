terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.13"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.32"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

data "google_client_config" "default" {}

provider "kubernetes" {
  host                   = "https://${google_container_cluster.gke.endpoint}"
  token                  = data.google_client_config.default.access_token
  cluster_ca_certificate = base64decode(google_container_cluster.gke.master_auth[0].cluster_ca_certificate)
}

provider "helm" {
  kubernetes {
    host                   = "https://${google_container_cluster.gke.endpoint}"
    token                  = data.google_client_config.default.access_token
    cluster_ca_certificate = base64decode(google_container_cluster.gke.master_auth[0].cluster_ca_certificate)
  }
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

resource "kubernetes_namespace_v1" "platform" {
  metadata {
    name = local.platform_namespace
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      "app.kubernetes.io/part-of"    = "terrier-connect"
    }
  }

  depends_on = [
    google_container_cluster.gke,
    google_container_node_pool.primary_nodes,
  ]
}

resource "helm_release" "redis" {
  name       = local.redis_release_name
  repository = local.bitnami_oci_repository
  chart      = "redis"
  version    = local.redis_chart_version
  namespace  = kubernetes_namespace_v1.platform.metadata[0].name

  cleanup_on_fail = true
  timeout         = 600

  values = [yamlencode({
    fullnameOverride = local.redis_release_name
    architecture     = "standalone"
    auth = {
      enabled = false
    }
    master = {
      resourcesPreset = "small"
      persistence = {
        enabled      = true
        size         = var.redis_storage_size
        storageClass = local.platform_storage_class_name
      }
    }
    metrics = {
      enabled = false
    }
  })]

  depends_on = [kubernetes_namespace_v1.platform]
}

resource "helm_release" "kafka" {
  name       = local.kafka_release_name
  repository = local.bitnami_oci_repository
  chart      = "kafka"
  version    = local.kafka_chart_version
  namespace  = kubernetes_namespace_v1.platform.metadata[0].name

  cleanup_on_fail = true
  timeout         = 900

  values = [yamlencode({
    fullnameOverride = local.kafka_release_name
    global = {
      security = {
        allowInsecureImages = true
      }
    }
    image = {
      registry   = "docker.io"
      repository = "bitnamilegacy/kafka"
    }
    listeners = {
      client = {
        protocol = "PLAINTEXT"
      }
      controller = {
        protocol = "PLAINTEXT"
      }
      interbroker = {
        protocol = "PLAINTEXT"
      }
    }
    controller = {
      replicaCount  = 1
      controllerOnly = false
      resourcesPreset = "small"
      persistence = {
        enabled      = true
        size         = var.kafka_storage_size
        storageClass = local.platform_storage_class_name
      }
    }
    broker = {
      replicaCount = 0
    }
    service = {
      type = "ClusterIP"
    }
    provisioning = {
      enabled      = true
      waitForKafka = true
      topics = [
        {
          name              = "cassandra.terrier.post_by_id"
          partitions        = 3
          replicationFactor = 1
        },
        {
          name              = "cassandra.terrier.likes_by_post"
          partitions        = 3
          replicationFactor = 1
        },
        {
          name              = "cassandra.terrier.comments_by_post"
          partitions        = 3
          replicationFactor = 1
        },
        {
          name              = "postgres.public.users_userfollowrel"
          partitions        = 3
          replicationFactor = 1
        },
        {
          name              = "__debezium-heartbeat.postgres"
          partitions        = 1
          replicationFactor = 1
        },
        {
          name              = "dlq-elasticsearch-posts"
          partitions        = 3
          replicationFactor = 1
        },
        {
          name              = "_connect-configs"
          partitions        = 1
          replicationFactor = 1
          config = {
            "cleanup.policy" = "compact"
          }
        },
        {
          name              = "_connect-offsets"
          partitions        = 1
          replicationFactor = 1
          config = {
            "cleanup.policy" = "compact"
          }
        },
        {
          name              = "_connect-status"
          partitions        = 1
          replicationFactor = 1
          config = {
            "cleanup.policy" = "compact"
          }
        },
      ]
    }
    metrics = {
      jmx = {
        enabled = false
      }
      serviceMonitor = {
        enabled = false
      }
    }
  })]

  depends_on = [kubernetes_namespace_v1.platform]
}

resource "kubernetes_persistent_volume_claim_v1" "cassandra" {
  wait_until_bound = false

  metadata {
    name      = "${local.cassandra_name}-data"
    namespace = kubernetes_namespace_v1.platform.metadata[0].name
    labels    = local.cassandra_labels
  }

  spec {
    access_modes = ["ReadWriteOnce"]

    resources {
      requests = {
        storage = var.cassandra_storage_size
      }
    }

    storage_class_name = local.platform_storage_class_name
  }

  depends_on = [kubernetes_namespace_v1.platform]
}

resource "kubernetes_service_v1" "cassandra" {
  metadata {
    name      = local.cassandra_name
    namespace = kubernetes_namespace_v1.platform.metadata[0].name
    labels    = local.cassandra_labels
  }

  spec {
    selector = local.cassandra_labels

    port {
      name        = "cql"
      port        = 9042
      target_port = 9042
    }

    type = "ClusterIP"
  }

  depends_on = [kubernetes_namespace_v1.platform]
}

resource "kubernetes_deployment_v1" "cassandra" {
  metadata {
    name      = local.cassandra_name
    namespace = kubernetes_namespace_v1.platform.metadata[0].name
    labels    = local.cassandra_labels
  }

  spec {
    replicas = 1

    strategy {
      type = "Recreate"
    }

    selector {
      match_labels = local.cassandra_labels
    }

    template {
      metadata {
        labels = local.cassandra_labels
      }

      spec {
        termination_grace_period_seconds = 120

        container {
          name              = "cassandra"
          image             = "cassandra:4.1"
          image_pull_policy = "IfNotPresent"

          env {
            name  = "CASSANDRA_CLUSTER_NAME"
            value = "TerrierCluster"
          }

          env {
            name  = "CASSANDRA_DC"
            value = "datacenter1"
          }

          env {
            name  = "CASSANDRA_ENDPOINT_SNITCH"
            value = "SimpleSnitch"
          }

          env {
            name  = "MAX_HEAP_SIZE"
            value = "512M"
          }

          env {
            name  = "HEAP_NEWSIZE"
            value = "128M"
          }

          port {
            container_port = 9042
            name           = "cql"
          }

          readiness_probe {
            initial_delay_seconds = 60
            period_seconds        = 10
            timeout_seconds       = 5
            failure_threshold     = 12

            tcp_socket {
              port = 9042
            }
          }

          liveness_probe {
            initial_delay_seconds = 120
            period_seconds        = 20
            timeout_seconds       = 5
            failure_threshold     = 6

            tcp_socket {
              port = 9042
            }
          }

          resources {
            requests = {
              cpu    = "250m"
              memory = "1Gi"
            }
            limits = {
              cpu    = "1"
              memory = "2Gi"
            }
          }

          volume_mount {
            mount_path = "/var/lib/cassandra"
            name       = "data"
          }
        }

        volume {
          name = "data"

          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim_v1.cassandra.metadata[0].name
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_service_v1.cassandra,
    kubernetes_persistent_volume_claim_v1.cassandra,
  ]
}

resource "kubernetes_service_v1" "kafka_connect" {
  metadata {
    name      = local.kafka_connect_name
    namespace = kubernetes_namespace_v1.platform.metadata[0].name
    labels    = local.kafka_connect_labels
  }

  spec {
    selector = local.kafka_connect_labels

    port {
      name        = "http"
      port        = 8083
      target_port = 8083
    }

    type = "ClusterIP"
  }

  depends_on = [kubernetes_namespace_v1.platform]
}

resource "kubernetes_deployment_v1" "kafka_connect" {
  metadata {
    name      = local.kafka_connect_name
    namespace = kubernetes_namespace_v1.platform.metadata[0].name
    labels    = local.kafka_connect_labels
  }

  spec {
    replicas = 1

    selector {
      match_labels = local.kafka_connect_labels
    }

    template {
      metadata {
        labels = local.kafka_connect_labels
      }

      spec {
        container {
          name              = "kafka-connect"
          image             = "debezium/connect:2.7.3.Final"
          image_pull_policy = "IfNotPresent"

          env {
            name  = "BOOTSTRAP_SERVERS"
            value = local.kafka_bootstrap_servers
          }

          env {
            name  = "GROUP_ID"
            value = "tc-connect-cluster"
          }

          env {
            name  = "CONFIG_STORAGE_TOPIC"
            value = "_connect-configs"
          }

          env {
            name  = "OFFSET_STORAGE_TOPIC"
            value = "_connect-offsets"
          }

          env {
            name  = "STATUS_STORAGE_TOPIC"
            value = "_connect-status"
          }

          env {
            name  = "CONFIG_STORAGE_REPLICATION_FACTOR"
            value = "1"
          }

          env {
            name  = "OFFSET_STORAGE_REPLICATION_FACTOR"
            value = "1"
          }

          env {
            name  = "STATUS_STORAGE_REPLICATION_FACTOR"
            value = "1"
          }

          port {
            container_port = 8083
            name           = "http"
          }

          readiness_probe {
            initial_delay_seconds = 20
            period_seconds        = 10
            timeout_seconds       = 5
            failure_threshold     = 6

            http_get {
              path = "/connectors"
              port = 8083
            }
          }

          liveness_probe {
            initial_delay_seconds = 45
            period_seconds        = 20
            timeout_seconds       = 5
            failure_threshold     = 6

            http_get {
              path = "/connectors"
              port = 8083
            }
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "512Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "1Gi"
            }
          }
        }
      }
    }
  }

  depends_on = [
    helm_release.kafka,
    kubernetes_service_v1.kafka_connect,
  ]
}

resource "helm_release" "elasticsearch" {
  name       = local.elasticsearch_release_name
  repository = local.bitnami_oci_repository
  chart      = "elasticsearch"
  version    = local.elasticsearch_chart_version
  namespace  = kubernetes_namespace_v1.platform.metadata[0].name

  cleanup_on_fail = true
  timeout         = 900

  values = [yamlencode({
    fullnameOverride = local.elasticsearch_release_name
    clusterName      = local.elasticsearch_release_name
    global = {
      kibanaEnabled = false
      security = {
        allowInsecureImages = true
      }
    }
    image = {
      registry   = "docker.io"
      repository = "bitnamilegacy/elasticsearch"
    }
    security = {
      enabled = false
      tls = {
        restEncryption = false
        autoGenerated  = false
      }
    }
    service = {
      type = "ClusterIP"
    }
    master = {
      masterOnly      = false
      replicaCount    = 1
      resourcesPreset = "small"
      heapSize        = "1g"
      resources = {
        requests = {
          cpu    = "250m"
          memory = "1Gi"
        }
        limits = {
          cpu    = "1"
          memory = "2Gi"
        }
      }
      persistence = {
        enabled      = true
        size         = var.elasticsearch_storage_size
        storageClass = local.platform_storage_class_name
      }
    }
    data = {
      replicaCount = 0
    }
    coordinating = {
      replicaCount = 0
    }
    ingest = {
      enabled      = false
      replicaCount = 0
    }
    metrics = {
      enabled = false
    }
    sysctlImage = {
      registry   = "docker.io"
      repository = "bitnamilegacy/os-shell"
    }
  })]

  depends_on = [kubernetes_namespace_v1.platform]
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

    database_flags {
      name  = "cloudsql.logical_decoding"
      value = "on"
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
  force_destroy = true

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
  platform_namespace        = var.platform_namespace
  platform_storage_class_name = var.platform_storage_class != "" ? var.platform_storage_class : "standard-rwo"
  cluster_domain            = var.k8s_cluster_domain
  bitnami_oci_repository    = "oci://registry-1.docker.io/bitnamicharts"
  redis_chart_version       = "25.3.2"
  kafka_chart_version       = "32.4.3"
  elasticsearch_chart_version = "22.1.6"
  redis_release_name        = "terrier-redis"
  kafka_release_name        = "terrier-kafka"
  cassandra_name            = "terrier-cassandra"
  kafka_connect_name        = "terrier-kafka-connect"
  elasticsearch_release_name = "terrier-elasticsearch"
  cassandra_host            = "${local.cassandra_name}.${local.platform_namespace}.svc.${local.cluster_domain}"
  redis_host                = "${local.redis_release_name}-master.${local.platform_namespace}.svc.${local.cluster_domain}"
  redis_url                 = "redis://${local.redis_host}:6379/0"
  kafka_bootstrap_servers   = "${local.kafka_release_name}.${local.platform_namespace}.svc.${local.cluster_domain}:9092"
  kafka_connect_url         = "http://${local.kafka_connect_name}.${local.platform_namespace}.svc.${local.cluster_domain}:8083"
  elasticsearch_url         = "http://${local.elasticsearch_release_name}.${local.platform_namespace}.svc.${local.cluster_domain}:9200"
  cassandra_labels = {
    "app.kubernetes.io/managed-by" = "terraform"
    "app.kubernetes.io/name"       = "terrier-cassandra"
    "app.kubernetes.io/part-of"    = "terrier-connect"
  }
  kafka_connect_labels = {
    "app.kubernetes.io/managed-by" = "terraform"
    "app.kubernetes.io/name"       = "terrier-kafka-connect"
    "app.kubernetes.io/part-of"    = "terrier-connect"
  }
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
#   echo -n "<value>" | gcloud secrets versions add terrier-connect-google-client-id --data-file=-
#   echo -n "<value>" | gcloud secrets versions add terrier-connect-google-client-secret --data-file=-
#   echo -n "<value>" | gcloud secrets versions add terrier-connect-debezium-db-user --data-file=-
#   echo -n "<value>" | gcloud secrets versions add terrier-connect-debezium-db-password --data-file=-
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

resource "google_secret_manager_secret" "google_client_id" {
  secret_id = "terrier-connect-google-client-id"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "google_client_secret" {
  secret_id = "terrier-connect-google-client-secret"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "debezium_db_user" {
  secret_id = "terrier-connect-debezium-db-user"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "debezium_db_password" {
  secret_id = "terrier-connect-debezium-db-password"
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

  git_file_source {
    path       = "cloudbuild.yaml"
    repository = google_cloudbuildv2_repository.github_repo.id
    revision   = "refs/heads/main"
    repo_type  = "GITHUB"
  }

  # Use the dedicated Cloud Build SA created above.
  service_account = google_service_account.cloudbuild_sa.id

  # Non-secret substitutions; secrets come from Secret Manager via availableSecrets
  substitutions = {
    _REGION                   = var.region
    _CLUSTER_NAME             = var.gke_cluster_name
    _DOMAIN_NAME              = var.domain_name
    _CLOUDSQL_INSTANCE_NAME   = var.cloudsql_instance_name
    _K8S_NAMESPACE            = var.k8s_namespace
    _CASSANDRA_HOSTS          = local.cassandra_host
    _REDIS_URL                = local.redis_url
    _ELASTICSEARCH_URL        = local.elasticsearch_url
    _KAFKA_BOOTSTRAP_SERVERS  = local.kafka_bootstrap_servers
    _KAFKA_CONNECT_URL        = local.kafka_connect_url
    _DEBEZIUM_DB_HOST         = google_sql_database_instance.db.private_ip_address
    _DEBEZIUM_DB_PORT         = "5432"
    _DEBEZIUM_DB_NAME         = var.db_name
    _PROJECTION_EVENTS_ENABLED = "1"
    _REACT_APP_API_BASE_URL   = "/api"
    _REACT_APP_MEDIA_BASE_URL = "/media"
  }

  depends_on = [
    google_project_service.apis,
    google_project_iam_member.cloudbuild_roles,
    google_service_account_iam_member.cloudbuild_agent_token_creator,
  ]
}
