# Terrier Connect - GCP Infrastructure

This directory is the Terraform source of truth for the production environment.

It provisions the **base GCP infrastructure**, the **shared platform services** used by the app, and the **Cloud Build GitOps trigger** that deploys the Helm chart.

Production application manifests are rendered from [helm/terrier-connect](../helm/terrier-connect). The older manifests in [k8s/](../k8s/) are legacy reference material only.

---

## What Terraform Manages

### GCP foundation

- regional **GKE** cluster
- autoscaling **node pool** with auto-repair and auto-upgrade
- dedicated **VPC**, subnet, and secondary pod/service ranges
- **Cloud SQL** PostgreSQL instance with private IP
- **Artifact Registry** repository for Docker images
- **Cloud Storage** media bucket
- **Secret Manager** secret shells
- **Cloud DNS** managed zone and records
- global static IP for the production Ingress

### Kubernetes platform layer

Terraform also provisions the shared runtime services in the `terrier-platform` namespace:

- **Redis** via Helm
- **Kafka** via Helm
- **Elasticsearch** via Helm
- **Cassandra** via Kubernetes deployment + PVC
- **Kafka Connect / Debezium runtime** via Kubernetes deployment

### Delivery and identity

- dedicated **Cloud Build service account** and IAM bindings
- **GitHub 2nd-gen Cloud Build repository connection** reference
- **Cloud Build trigger** for push-to-main deployments
- **Workload Identity** service account for app workloads

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│ GitHub                                                             │
│ push to main                                                       │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
                    ┌──────────────────────────┐
                    │ Cloud Build trigger      │
                    │ cloudbuild.yaml          │
                    └────────────┬─────────────┘
                                 │
                ┌────────────────┴────────────────┐
                ▼                                 ▼
       ┌─────────────────────┐           ┌──────────────────────┐
       │ Artifact Registry   │           │ Secret Manager       │
       │ client/server/      │           │ build-time secrets   │
       │ gateway images      │           │ + Debezium creds     │
       └──────────┬──────────┘           └──────────┬───────────┘
                  │                                 │
                  └────────────────┬────────────────┘
                                   ▼
                        ┌──────────────────────────┐
                        │ GKE (regional)           │
                        │ terrier-connect          │
                        └────────────┬─────────────┘
                                     │
             ┌───────────────────────┴────────────────────────┐
             ▼                                                ▼
  ┌─────────────────────────────┐                 ┌─────────────────────────────┐
  │ terrier-connect namespace   │                 │ terrier-platform namespace  │
  │ client / gateway / server   │                 │ Redis / Kafka / Cassandra   │
  │ workers / ingress           │                 │ Kafka Connect / Elastic     │
  └─────────────────────────────┘                 └─────────────────────────────┘
                                     │
                                     ▼
                     ┌─────────────────────────────────┐
                     │ Cloud SQL + GCS + Cloud DNS    │
                     └─────────────────────────────────┘
```

---

## Namespaces and Responsibilities

| Namespace | Purpose |
|----------|---------|
| `terrier-connect` | application workloads deployed by Helm |
| `terrier-platform` | shared platform dependencies managed by Terraform |

---

## Prerequisites

1. A **GCP project** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Terraform** installed locally
4. A domain name for the public frontend/API
5. A **2nd-gen GitHub host connection** created in Cloud Build:
   - Cloud Build → Repositories → Create host connection → GitHub

---

## Initial Setup

### 1. Create the Terraform state bucket

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"

gcloud services enable storage.googleapis.com --project="$PROJECT_ID"
gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://${PROJECT_ID}-tf-state"
gsutil versioning set on "gs://${PROJECT_ID}-tf-state"
```

### 2. Configure variables

```bash
cd infrastructure
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your project, domain, GitHub, and sizing values.

Important node-pool settings:

- `gke_node_machine_type`
- `gke_node_count` (minimum)
- `gke_node_max_count` (autoscaler maximum)

### 3. Initialize and apply

```bash
terraform init -backend-config="bucket=${PROJECT_ID}-tf-state"
terraform apply
```

This creates:

- the GKE cluster and autoscaling node pool
- Cloud SQL, GCS, DNS, Artifact Registry, and Secret Manager resources
- the `terrier-platform` namespace and its shared services
- the dedicated `terrier-connect-cloudbuild-sa`
- the `terrier-connect-main` Cloud Build trigger

### 4. Populate Secret Manager versions

The first apply only creates the secret containers. Add versions after that:

```bash
echo -n "your-db-password" | gcloud secrets versions add terrier-connect-db-password --data-file=-
echo -n "your-django-secret-key" | gcloud secrets versions add terrier-connect-django-secret-key --data-file=-
echo -n "your-maps-api-key" | gcloud secrets versions add terrier-connect-maps-api-key --data-file=-
echo -n "your-google-client-id" | gcloud secrets versions add terrier-connect-google-client-id --data-file=-
echo -n "your-google-client-secret" | gcloud secrets versions add terrier-connect-google-client-secret --data-file=-
echo -n "your-debezium-db-user" | gcloud secrets versions add terrier-connect-debezium-db-user --data-file=-
echo -n "your-debezium-db-password" | gcloud secrets versions add terrier-connect-debezium-db-password --data-file=-
```

---

## Deployment Model

### Infrastructure changes

```bash
cd infrastructure
terraform apply
```

Use Terraform when you need to change:

- cluster sizing or autoscaling
- Cloud SQL / storage / networking
- platform services in `terrier-platform`
- IAM, secrets, DNS, or the Cloud Build trigger

### Application deploy — GitOps

```bash
git push origin main
```

The trigger builds images, renders Helm values, and upgrades the release in GKE.

### Application deploy — manual, same pipeline

```bash
gcloud builds submit \
  --project "$PROJECT_ID" \
  --config cloudbuild.yaml \
  --substitutions=_DOMAIN_NAME="yourdomain.com" \
  .
```

`cloudbuild-local.yaml` remains a compatibility alias and should stay aligned with `cloudbuild.yaml`.

### Trigger GitOps manually from CLI

```bash
gcloud builds triggers run terrier-connect-main \
  --region=us-central1 \
  --project="$PROJECT_ID" \
  --branch=main
```

---

## Helm Deployment Contract

Cloud Build deploys [helm/terrier-connect](../helm/terrier-connect) and injects runtime values for:

- `client`, `server`, and `gateway` image tags
- ingress hosts and CORS settings
- Workload Identity annotations
- Cloud SQL proxy settings
- Redis, Kafka, Cassandra, Elasticsearch, and Kafka Connect endpoints
- Secret Manager values for DB password, Django secret key, Google OAuth, and Maps API

If Debezium connector registration is enabled, Cloud Build also injects the Kafka Connect URL and database connection details into the Helm hook job.

To enable connector registration during a deploy:

```bash
gcloud builds submit \
  --project "$PROJECT_ID" \
  --config cloudbuild.yaml \
  --substitutions=_DOMAIN_NAME="yourdomain.com",_ENABLE_DEBEZIUM_CONNECTOR_REGISTRATION="true",_KAFKA_CONNECT_URL="http://terrier-kafka-connect.terrier-platform.svc.cluster.local:8083",_DEBEZIUM_DB_HOST="$(terraform output -raw cloudsql_private_ip_address)" \
  .
```

---

## Useful Terraform Outputs

After `terraform apply`, these outputs are commonly used during debugging and deploy validation:

- `terraform output cassandra_host`
- `terraform output redis_url`
- `terraform output kafka_bootstrap_servers`
- `terraform output kafka_connect_url`
- `terraform output elasticsearch_url`
- `terraform output cloudsql_private_ip_address`
- `terraform output ingress_ip_address`

---

## Accessing the Application

Once DNS records propagate and the Ingress is healthy:

- frontend: `https://<your-domain>`
- REST API: `https://<your-domain>/api/`
- GraphQL gateway: `https://<your-domain>/graphql`

Check the load balancer IP with:

```bash
terraform output ingress_ip_address
```

---

## Cleanup

```bash
cd infrastructure
terraform destroy
gsutil rm -r "gs://${PROJECT_ID}-tf-state"
```

---

## Troubleshooting

- **Pods stay Pending**: check cluster capacity and GCE quota first. The node pool can autoscale between `gke_node_count` and `gke_node_max_count`, but scale-out still depends on available quota.
- **Managed certificate not becoming ready**: confirm your DNS A records point to the Ingress IP.
- **Cloud SQL connection errors**: verify Workload Identity, Cloud SQL proxy settings, and `instanceConnectionName`.
- **Secret access denied during builds**: run `terraform apply` and verify the Cloud Build SA still has `roles/secretmanager.secretAccessor`.
- **Build running under the wrong service account**: verify the `serviceAccount` field in `cloudbuild.yaml` and the Terraform-managed trigger both reference `terrier-connect-cloudbuild-sa`.
- **Debezium registration fails**: confirm the Debezium DB secrets have at least one secret version and the `_DEBEZIUM_DB_HOST` / `_KAFKA_CONNECT_URL` substitutions are provided.
- **Platform services unhealthy**: inspect the `terrier-platform` namespace before debugging the app namespace.
