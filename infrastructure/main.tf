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
    "cloudtrace.googleapis.com",
    "telemetry.googleapis.com",
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
  logging_service          = "logging.googleapis.com/kubernetes"
  monitoring_service       = "monitoring.googleapis.com/kubernetes"

  network    = google_compute_network.vpc_network.id
  subnetwork = google_compute_subnetwork.gke_subnet.id

  logging_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"]
  }

  monitoring_config {
    enable_components = [
      "SYSTEM_COMPONENTS",
      "APISERVER",
      "SCHEDULER",
      "CONTROLLER_MANAGER",
      "STORAGE",
      "POD",
      "DAEMONSET",
      "DEPLOYMENT",
      "STATEFULSET",
      "HPA",
    ]

    managed_prometheus {
      enabled = true
    }
  }

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
  initial_node_count = var.gke_node_count

  autoscaling {
    min_node_count = var.gke_node_count
    max_node_count = var.gke_node_max_count
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

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
    overrideConfiguration = {
      "default.replication.factor"             = 1
      "offsets.topic.replication.factor"       = 1
      "transaction.state.log.replication.factor" = 1
      "transaction.state.log.min.isr"          = 1
      "min.insync.replicas"                    = 1
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
      resources = {
        requests = {
          cpu    = "50m"
          memory = "64Mi"
        }
        limits = {
          cpu    = "250m"
          memory = "256Mi"
        }
      }
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

resource "google_project_iam_member" "gke_workload_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.gke_workload.email}"
}

resource "google_project_iam_member" "gke_workload_traces" {
  project = var.project_id
  role    = "roles/telemetry.tracesWriter"
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
  gateway_monitoring_service_id = "terrier-connect-gateway"
  gateway_request_counter_metric = "prometheus.googleapis.com/gateway_http_requests_total/counter"
  gateway_request_latency_metric = "prometheus.googleapis.com/gateway_http_request_duration_seconds/histogram"
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
  gateway_request_total_filter = join(" AND ", [
    "resource.type=\"prometheus_target\"",
    "metric.type=\"${local.gateway_request_counter_metric}\"",
  ])
  gateway_request_5xx_filter = join(" AND ", [
    local.gateway_request_total_filter,
    "metric.labels.status_code=monitoring.regex.full_match(\"^5..\")",
  ])
  gateway_request_latency_filter = join(" AND ", [
    "resource.type=\"prometheus_target\"",
    "metric.type=\"${local.gateway_request_latency_metric}\"",
  ])
  public_homepage_uptime_filter = join(" AND ", [
    "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\"",
    "resource.type=\"uptime_url\"",
    "metric.labels.check_id=\"${google_monitoring_uptime_check_config.public_homepage.uptime_check_id}\"",
  ])
  public_api_health_uptime_filter = join(" AND ", [
    "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\"",
    "resource.type=\"uptime_url\"",
    "metric.labels.check_id=\"${google_monitoring_uptime_check_config.public_api_health.uptime_check_id}\"",
  ])
}

resource "google_project_iam_member" "cloudbuild_roles" {
  for_each   = local.cloudbuild_roles
  project    = var.project_id
  role       = each.value
  member     = local.cloudbuild_sa
  depends_on = [google_project_service.apis]
}

resource "google_monitoring_notification_channel" "ops_email" {
  count = trimspace(var.alert_notification_email) != "" ? 1 : 0

  display_name = "Terrier Connect Ops Email"
  type         = "email"
  labels = {
    email_address = trimspace(var.alert_notification_email)
  }
  force_delete = false

  user_labels = {
    service = "terrier-connect"
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_custom_service" "gateway" {
  service_id   = local.gateway_monitoring_service_id
  display_name = "Terrier Connect Gateway"

  user_labels = {
    service = "terrier-connect"
    tier    = "edge"
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_slo" "gateway_availability" {
  count        = var.enable_gateway_slos ? 1 : 0
  service      = google_monitoring_custom_service.gateway.service_id
  slo_id       = "gateway-availability-30d"
  display_name = "Gateway availability 99% over 30 days"
  goal         = 0.99

  rolling_period_days = 30

  request_based_sli {
    good_total_ratio {
      bad_service_filter   = local.gateway_request_5xx_filter
      total_service_filter = local.gateway_request_total_filter
    }
  }

  user_labels = {
    service = "terrier-connect"
    sli     = "availability"
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_slo" "gateway_latency" {
  count        = var.enable_gateway_slos ? 1 : 0
  service      = google_monitoring_custom_service.gateway.service_id
  slo_id       = "gateway-latency-30d"
  display_name = "Gateway latency 95% under 1s over 30 days"
  goal         = 0.95

  rolling_period_days = 30

  request_based_sli {
    distribution_cut {
      distribution_filter = local.gateway_request_latency_filter

      range {
        max = 1
      }
    }
  }

  user_labels = {
    service = "terrier-connect"
    sli     = "latency"
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_uptime_check_config" "public_homepage" {
  display_name       = "Terrier Connect public homepage"
  period             = "60s"
  timeout            = "10s"
  checker_type       = "STATIC_IP_CHECKERS"

  http_check {
    path         = "/"
    use_ssl      = true
    validate_ssl = true

    accepted_response_status_codes {
      status_class = "STATUS_CLASS_2XX"
    }
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = var.domain_name
    }
  }

  user_labels = {
    service  = "terrier-connect"
    surface  = "public-frontend"
    protocol = "https"
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_uptime_check_config" "public_api_health" {
  display_name       = "Terrier Connect public API health"
  period             = "60s"
  timeout            = "10s"
  checker_type       = "STATIC_IP_CHECKERS"

  http_check {
    path         = "/api/posts/health/"
    use_ssl      = true
    validate_ssl = true

    accepted_response_status_codes {
      status_class = "STATUS_CLASS_2XX"
    }
  }

  content_matchers {
    content = "healthy"
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = var.domain_name
    }
  }

  user_labels = {
    service  = "terrier-connect"
    surface  = "public-api"
    protocol = "https"
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_dashboard" "application_overview" {
  dashboard_json = jsonencode({
    displayName = "Terrier Connect Application Overview"
    annotations = {
      defaultResourceNames = ["projects/${var.project_id}"]
      eventAnnotations = [
        {
          displayName = "GKE pod crashes"
          eventType   = "GKE_POD_CRASH"
          enabled     = true
        },
        {
          displayName = "Alert incidents"
          eventType   = "CLOUD_ALERTING_ALERT"
          enabled     = true
        },
      ]
    }
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          xPos   = 0
          yPos   = 0
          width  = 12
          height = 2
          widget = {
            title = "Observability scope"
            text = {
              format = "MARKDOWN"
              content = join("\n", [
                "## Terrier Connect observability overview",
                "Tracks gateway traffic, async pipeline health, and active incidents.",
                "Trace context now flows from Django requests into the Cassandra outbox, Kafka relay, and worker consumers.",
              ])
            }
          }
        },
        {
          xPos   = 0
          yPos   = 2
          width  = 4
          height = 4
          widget = {
            title = "Gateway request rate"
            xyChart = {
              dataSets = [
                {
                  plotType = "LINE"
                  legendTemplate = "req/s"
                  minAlignmentPeriod = "60s"
                  timeSeriesQuery = {
                    unitOverride    = "1/s"
                    prometheusQuery = "sum(rate(gateway_http_requests_total[5m]))"
                  }
                }
              ]
              yAxis = {
                label = "Requests / second"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 4
          yPos   = 2
          width  = 4
          height = 4
          widget = {
            title = "Gateway 5xx ratio"
            xyChart = {
              dataSets = [
                {
                  plotType = "LINE"
                  legendTemplate = "5xx ratio"
                  minAlignmentPeriod = "60s"
                  timeSeriesQuery = {
                    unitOverride = "10^2.%"
                    prometheusQuery = "100 * sum(rate(gateway_http_requests_total{status_code=~\"5..\"}[5m])) / clamp_min(sum(rate(gateway_http_requests_total[5m])), 0.001)"
                  }
                }
              ]
              yAxis = {
                label = "Percent"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 8
          yPos   = 2
          width  = 4
          height = 4
          widget = {
            title = "Gateway p95 latency"
            xyChart = {
              dataSets = [
                {
                  plotType = "LINE"
                  legendTemplate = "p95 latency"
                  minAlignmentPeriod = "60s"
                  timeSeriesQuery = {
                    unitOverride    = "s"
                    prometheusQuery = "histogram_quantile(0.95, sum by (le) (rate(gateway_http_request_duration_seconds_bucket[5m])))"
                  }
                }
              ]
              yAxis = {
                label = "Seconds"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 0
          yPos   = 6
          width  = 6
          height = 4
          widget = {
            title = "Django request volume"
            xyChart = {
              dataSets = [
                {
                  plotType = "LINE"
                  legendTemplate = "requests / second"
                  minAlignmentPeriod = "60s"
                  timeSeriesQuery = {
                    unitOverride    = "1/s"
                    prometheusQuery = "sum(rate(django_http_requests_before_middlewares_total[5m]))"
                  }
                }
              ]
              yAxis = {
                label = "Requests / second"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 6
          yPos   = 6
          width  = 6
          height = 4
          widget = {
            title = "Async worker errors"
            logsPanel = {
              resourceNames = ["projects/${var.project_id}"]
              filter = join("\n", [
                "resource.type=\"k8s_container\"",
                "severity>=ERROR",
                "(",
                "  jsonPayload.message:\"Outbox relay failed\"",
                "  OR jsonPayload.message:\"handler error\"",
                "  OR jsonPayload.message:\"Kafka delivery failed\"",
                "  OR textPayload:\"Outbox relay failed\"",
                "  OR textPayload:\"handler error\"",
                "  OR textPayload:\"Kafka delivery failed\"",
                ")",
              ])
            }
          }
        },
        {
          xPos   = 0
          yPos   = 10
          width  = 4
          height = 4
          widget = {
            title = "Outbox oldest event age"
            xyChart = {
              dataSets = [
                {
                  plotType = "LINE"
                  legendTemplate = "oldest age"
                  minAlignmentPeriod = "60s"
                  timeSeriesQuery = {
                    unitOverride    = "s"
                    prometheusQuery = "max(terrier_async_outbox_oldest_event_age_seconds)"
                  }
                }
              ]
              yAxis = {
                label = "Seconds"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 4
          yPos   = 10
          width  = 4
          height = 4
          widget = {
            title = "Outbox pending events"
            xyChart = {
              dataSets = [
                {
                  plotType = "LINE"
                  legendTemplate = "pending"
                  minAlignmentPeriod = "60s"
                  timeSeriesQuery = {
                    unitOverride    = "1"
                    prometheusQuery = "max(terrier_async_outbox_pending_events)"
                  }
                }
              ]
              yAxis = {
                label = "Events"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 8
          yPos   = 10
          width  = 4
          height = 4
          widget = {
            title = "Async consumer failures"
            xyChart = {
              dataSets = [
                {
                  plotType = "STACKED_BAR"
                  legendTemplate = "{{consumer}}"
                  minAlignmentPeriod = "60s"
                  timeSeriesQuery = {
                    unitOverride    = "1/s"
                    prometheusQuery = "sum by (consumer) (rate(terrier_async_consumer_events_total{result=\"error\"}[5m]))"
                  }
                }
              ]
              yAxis = {
                label = "Errors / second"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 0
          yPos   = 14
          width  = 4
          height = 4
          widget = {
            title = "Kafka Connect availability"
            scorecard = {
              timeSeriesQuery = {
                prometheusQuery = "max(terrier_kafka_connect_up)"
              }
              gaugeView = {
                lowerBound = 0
                upperBound = 1
              }
            }
          }
        },
        {
          xPos   = 4
          yPos   = 14
          width  = 4
          height = 4
          widget = {
            title = "Kafka Connect failed connectors"
            xyChart = {
              dataSets = [
                {
                  plotType = "STACKED_BAR"
                  legendTemplate = "{{connector}}"
                  minAlignmentPeriod = "60s"
                  timeSeriesQuery = {
                    unitOverride    = "1"
                    prometheusQuery = "max by (connector) (terrier_kafka_connect_connector_state{state=\"FAILED\"})"
                  }
                }
              ]
              yAxis = {
                label = "Failed state"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 8
          yPos   = 14
          width  = 4
          height = 4
          widget = {
            title = "DLQ retained records"
            xyChart = {
              dataSets = [
                {
                  plotType = "LINE"
                  legendTemplate = "{{topic}}"
                  minAlignmentPeriod = "60s"
                  timeSeriesQuery = {
                    unitOverride    = "1"
                    prometheusQuery = "sum by (topic) (terrier_kafka_connect_dlq_records)"
                  }
                }
              ]
              yAxis = {
                label = "Records"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 0
          yPos   = 18
          width  = 12
          height = 3
          widget = {
            title = "Open incidents"
            incidentList = {}
          }
        },
      ]
    }
  })

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "gateway_high_error_ratio" {
  count        = var.enable_metric_alert_policies ? 1 : 0
  display_name = "Terrier Connect gateway high 5xx ratio"
  combiner     = "OR"
  severity     = "ERROR"

  conditions {
    display_name = "Gateway 5xx ratio > 5%"
    condition_prometheus_query_language {
      query = "sum(rate(gateway_http_requests_total{status_code=~\"5..\"}[5m])) / clamp_min(sum(rate(gateway_http_requests_total[5m])), 0.001) > 0.05"
      duration            = "300s"
      evaluation_interval = "60s"
      alert_rule          = "GatewayHigh5xxRatio"
      rule_group          = "terrier-connect"
    }
  }

  notification_channels = google_monitoring_notification_channel.ops_email[*].name

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    mime_type = "text/markdown"
    subject   = "Terrier Connect gateway error ratio is elevated"
    content   = "The gateway is returning more than 5% 5xx responses for at least 5 minutes. Check the gateway deployment, upstream Django availability, and recent trace samples in Cloud Trace."
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "gateway_high_latency" {
  count        = var.enable_metric_alert_policies ? 1 : 0
  display_name = "Terrier Connect gateway high p95 latency"
  combiner     = "OR"
  severity     = "WARNING"

  conditions {
    display_name = "Gateway p95 latency > 1s"
    condition_prometheus_query_language {
      query = "histogram_quantile(0.95, sum by (le) (rate(gateway_http_request_duration_seconds_bucket[5m]))) > 1"
      duration            = "300s"
      evaluation_interval = "60s"
      alert_rule          = "GatewayHighLatency"
      rule_group          = "terrier-connect"
    }
  }

  notification_channels = google_monitoring_notification_channel.ops_email[*].name

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    mime_type = "text/markdown"
    subject   = "Terrier Connect gateway latency is elevated"
    content   = "The gateway p95 request latency has stayed above 1 second for at least 5 minutes. Inspect recent traces for slow resolvers, Django upstream latency, and platform saturation."
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "async_pipeline_failures" {
  display_name = "Terrier Connect async pipeline failures"
  combiner     = "OR"
  severity     = "ERROR"

  conditions {
    display_name = "Outbox relay or consumer handler failure logs"
    condition_matched_log {
      filter = join("\n", [
        "resource.type=\"k8s_container\"",
        "severity>=ERROR",
        "(",
        "  jsonPayload.message:\"Outbox relay failed\"",
        "  OR jsonPayload.message:\"handler error\"",
        "  OR jsonPayload.message:\"Kafka delivery failed\"",
        "  OR textPayload:\"Outbox relay failed\"",
        "  OR textPayload:\"handler error\"",
        "  OR textPayload:\"Kafka delivery failed\"",
        ")",
      ])
    }
  }

  notification_channels = google_monitoring_notification_channel.ops_email[*].name

  alert_strategy {
    auto_close = "1800s"
    notification_rate_limit {
      period = "300s"
    }
  }

  documentation {
    mime_type = "text/markdown"
    subject   = "Terrier Connect async pipeline failure detected"
    content   = "An async projection, Kafka publish, or worker handler failure was logged. Inspect the outbox relay and consumer workloads, then use the propagated traces to follow the failed event across the async pipeline."
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "async_outbox_backlog_age_high" {
  count        = var.enable_metric_alert_policies ? 1 : 0
  display_name = "Terrier Connect async outbox backlog age high"
  combiner     = "OR"
  severity     = "WARNING"

  conditions {
    display_name = "Outbox oldest pending event age > 5 minutes"
    condition_prometheus_query_language {
      query = "max(terrier_async_outbox_oldest_event_age_seconds) > 300"
      duration            = "600s"
      evaluation_interval = "60s"
      alert_rule          = "AsyncOutboxBacklogAgeHigh"
      rule_group          = "terrier-connect"
    }
  }

  notification_channels = google_monitoring_notification_channel.ops_email[*].name

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    mime_type = "text/markdown"
    subject   = "Terrier Connect async outbox backlog is aging"
    content   = "The oldest pending event in the Cassandra outbox has been queued for more than 5 minutes for at least 10 minutes. Inspect the outbox relay deployment, Kafka connectivity, and worker saturation before user-visible async projections fall behind."
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "kafka_connect_down" {
  count        = var.enable_metric_alert_policies ? 1 : 0
  display_name = "Terrier Connect Kafka Connect down"
  combiner     = "OR"
  severity     = "ERROR"

  conditions {
    display_name = "Kafka Connect monitor reports down"
    condition_prometheus_query_language {
      query = "max(terrier_kafka_connect_up) < 1"
      duration            = "300s"
      evaluation_interval = "60s"
      alert_rule          = "KafkaConnectDown"
      rule_group          = "terrier-connect"
    }
  }

  notification_channels = google_monitoring_notification_channel.ops_email[*].name

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    mime_type = "text/markdown"
    subject   = "Terrier Connect Kafka Connect is unreachable"
    content   = "The Kafka Connect monitor has not been able to query the Kafka Connect API for at least 5 minutes. Inspect the Kafka Connect deployment, service, and platform Kafka health before CDC or sink connectors fall behind."
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "kafka_connect_connector_failed" {
  count        = var.enable_metric_alert_policies ? 1 : 0
  display_name = "Terrier Connect Kafka Connect connector failed"
  combiner     = "OR"
  severity     = "ERROR"

  conditions {
    display_name = "Kafka Connect connector entered FAILED state"
    condition_prometheus_query_language {
      query = "max(terrier_kafka_connect_connector_state{state=\"FAILED\"}) >= 1"
      duration            = "300s"
      evaluation_interval = "60s"
      alert_rule          = "KafkaConnectConnectorFailed"
      rule_group          = "terrier-connect"
    }
  }

  notification_channels = google_monitoring_notification_channel.ops_email[*].name

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    mime_type = "text/markdown"
    subject   = "Terrier Connect Kafka Connect connector failed"
    content   = "A Kafka Connect connector has remained in the FAILED state for at least 5 minutes. Inspect connector status, task traces, and Kafka Connect logs to restore CDC or sink processing."
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "kafka_connect_dlq_records_present" {
  count        = var.enable_metric_alert_policies ? 1 : 0
  display_name = "Terrier Connect Kafka Connect DLQ has retained records"
  combiner     = "OR"
  severity     = "WARNING"

  conditions {
    display_name = "DLQ retained records > 0"
    condition_prometheus_query_language {
      query = "sum(terrier_kafka_connect_dlq_records) > 0"
      duration            = "600s"
      evaluation_interval = "60s"
      alert_rule          = "KafkaConnectDlqRecordsPresent"
      rule_group          = "terrier-connect"
    }
  }

  notification_channels = google_monitoring_notification_channel.ops_email[*].name

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    mime_type = "text/markdown"
    subject   = "Terrier Connect Kafka Connect DLQ contains retained records"
    content   = "Kafka Connect dead-letter topics have retained records for at least 10 minutes. Inspect the failed sink/source connector payloads, fix the underlying schema or data issue, and clear the DLQ backlog deliberately."
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "public_homepage_uptime_failing" {
  display_name = "Terrier Connect public homepage uptime failing"
  combiner     = "OR"
  severity     = "CRITICAL"

  conditions {
    display_name = "Public homepage uptime fraction < 50%"

    condition_threshold {
      filter                  = local.public_homepage_uptime_filter
      comparison              = "COMPARISON_LT"
      threshold_value         = 0.5
      duration                = "300s"
      evaluation_missing_data = "EVALUATION_MISSING_DATA_ACTIVE"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_FRACTION_TRUE"
      }

      trigger {
        count = 1
      }
    }
  }

  notification_channels = google_monitoring_notification_channel.ops_email[*].name

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    mime_type = "text/markdown"
    subject   = "Terrier Connect public homepage is failing uptime checks"
    content   = "External uptime checks to `https://${var.domain_name}/` have shown fewer than half of probes succeeding for at least 5 minutes. Inspect the GKE ingress, frontend service, TLS certificate status, and any recent deploys affecting public traffic."
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "public_api_health_uptime_failing" {
  display_name = "Terrier Connect public API health uptime failing"
  combiner     = "OR"
  severity     = "CRITICAL"

  conditions {
    display_name = "Public API health uptime fraction < 50%"

    condition_threshold {
      filter                  = local.public_api_health_uptime_filter
      comparison              = "COMPARISON_LT"
      threshold_value         = 0.5
      duration                = "300s"
      evaluation_missing_data = "EVALUATION_MISSING_DATA_ACTIVE"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_FRACTION_TRUE"
      }

      trigger {
        count = 1
      }
    }
  }

  notification_channels = google_monitoring_notification_channel.ops_email[*].name

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    mime_type = "text/markdown"
    subject   = "Terrier Connect public API health check is failing"
    content   = "External uptime checks to `https://${var.domain_name}/api/posts/health/` have shown fewer than half of probes succeeding for at least 5 minutes. Inspect the ingress, Django deployment, and backend dependencies surfaced by the health endpoint before the user-facing API becomes unavailable."
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "gateway_availability_fast_burn" {
  count        = var.enable_gateway_slos ? 1 : 0
  display_name = "Terrier Connect gateway availability fast burn"
  combiner     = "OR"
  severity     = "CRITICAL"

  conditions {
    display_name = "Gateway availability burn rate > 10 over 1 hour"

    condition_threshold {
      filter          = "select_slo_burn_rate(\"${google_monitoring_slo.gateway_availability[0].name}\", \"60m\")"
      comparison      = "COMPARISON_GT"
      threshold_value = 10
      duration        = "0s"

      trigger {
        count = 1
      }
    }
  }

  notification_channels = google_monitoring_notification_channel.ops_email[*].name

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    mime_type = "text/markdown"
    subject   = "Terrier Connect gateway is burning availability budget quickly"
    content   = "Gateway availability is consuming error budget at more than 10x the sustainable rate over the last hour. Treat this as an urgent incident, inspect recent gateway and Django traces, and stabilize 5xx responses before the 30-day SLO is put at risk."
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "gateway_availability_slow_burn" {
  count        = var.enable_gateway_slos ? 1 : 0
  display_name = "Terrier Connect gateway availability slow burn"
  combiner     = "OR"
  severity     = "WARNING"

  conditions {
    display_name = "Gateway availability burn rate > 2 over 24 hours"

    condition_threshold {
      filter          = "select_slo_burn_rate(\"${google_monitoring_slo.gateway_availability[0].name}\", \"24h\")"
      comparison      = "COMPARISON_GT"
      threshold_value = 2
      duration        = "0s"

      trigger {
        count = 1
      }
    }
  }

  notification_channels = google_monitoring_notification_channel.ops_email[*].name

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    mime_type = "text/markdown"
    subject   = "Terrier Connect gateway availability budget is drifting down"
    content   = "Gateway availability is consuming error budget at more than 2x the sustainable rate over the last 24 hours. Investigate recurring 5xx causes, recent deployments, and the health of upstream Django and platform dependencies before the monthly SLO is missed."
  }

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
