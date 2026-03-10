# Terrier Connect - GCP Infrastructure

This directory provisions the full production infrastructure on GCP using Terraform:

- **GKE** — Kubernetes cluster for app workloads
- **Cloud SQL (Postgres)** — Private IP database
- **Redis** — In-cluster cache and session store
- **Kafka + Kafka Connect** — In-cluster event streaming and Debezium runtime
- **Cassandra** — In-cluster projection store
- **Elasticsearch** — In-cluster search index
- **Cloud Storage** — Media uploads bucket
- **Artifact Registry** — Docker image storage
- **Cloud DNS** + **GKE Ingress** + **Managed Certificates** — HTTPS routing
- **Secret Manager** — Secrets storage (DB password, Django key, Maps API key, Google OAuth client ID/secret)
- **Cloud Build Trigger** — GitOps: auto-deploy on push to `main`
- **GCS backend** — Remote Terraform state

Production application deploys are rendered from the Helm chart in [helm/terrier-connect](../helm/terrier-connect).
The older Kustomize manifests under [k8s/](../k8s/) remain as legacy reference material.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   GitHub Repo   │────▶│   Cloud Build    │────▶│ Artifact Reg.   │
│  (push to main) │     │  (GitOps trigger)│     │ (Docker Images) │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                │                         │
                                ▼                         ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │  Secret Manager  │     │       GKE       │
                        │  (secrets injected     │  (Workloads)    │
                        │   at build time) │     └────────┬────────┘
                        └──────────────────┘              │
                                                          ▼
                                               ┌────────────────────┐
                                               │ Cloud SQL + GCS +  │
                                               │ platform services  │
                                               └────────────────────┘
```

## Prerequisites

1. **GCP Project** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Terraform** (v1.3+) installed locally
4. **A domain name**
5. **GitHub Cloud Build connection** created in GCP Console (one-time OAuth step):
   Cloud Build → Repositories (2nd gen) → Create host connection → GitHub

## Initial Setup

### 1. Create the GCS bucket for Terraform state (one-time)

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"

gcloud services enable storage.googleapis.com --project=$PROJECT_ID
gsutil mb -p $PROJECT_ID -l $REGION gs://${PROJECT_ID}-tf-state
gsutil versioning set on gs://${PROJECT_ID}-tf-state
```

### 2. Configure Terraform variables

```bash
cd infrastructure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values (project_id, domain, github_owner, etc.)
```

### 3. Initialize and apply Terraform

```bash
terraform init -backend-config="bucket=${PROJECT_ID}-tf-state"
terraform apply
```

This creates all infrastructure including:
- The dedicated Cloud Build SA (`terrier-connect-cloudbuild-sa`) with all required IAM roles
- Secret Manager secret shells (empty — must be populated in step 4)
- The GitOps Cloud Build trigger (fires on push to `main`)
- A shared Kubernetes namespace for Redis, Kafka, Kafka Connect, Cassandra, and Elasticsearch

### 4. Populate Secret Manager secrets (one-time, after first apply)

```bash
echo -n "your-db-password" | gcloud secrets versions add terrier-connect-db-password --data-file=-
echo -n "your-django-secret-key" | gcloud secrets versions add terrier-connect-django-secret-key --data-file=-
echo -n "your-maps-api-key" | gcloud secrets versions add terrier-connect-maps-api-key --data-file=-
echo -n "your-google-client-id" | gcloud secrets versions add terrier-connect-google-client-id --data-file=-
echo -n "your-google-client-secret" | gcloud secrets versions add terrier-connect-google-client-secret --data-file=-
echo -n "your-debezium-db-user" | gcloud secrets versions add terrier-connect-debezium-db-user --data-file=-
echo -n "your-debezium-db-password" | gcloud secrets versions add terrier-connect-debezium-db-password --data-file=-
```

## Deploying

### App deploy — GitOps (automatic)
```bash
git push origin main
# Cloud Build trigger fires, builds images, deploys to GKE
```

### App deploy — manual (without a git push)
```bash
# From the repo root:
gcloud builds submit \
  --project "$PROJECT_ID" \
  --config cloudbuild-local.yaml \
  --substitutions=_DOMAIN_NAME="yourdomain.com" \
  .
```

To also register the Debezium follow connector during deploy, add substitutions like:

```bash
--substitutions=_DOMAIN_NAME="yourdomain.com",_ENABLE_DEBEZIUM_CONNECTOR_REGISTRATION="true",_KAFKA_CONNECT_URL="http://terrier-kafka-connect.terrier-platform.svc.cluster.local:8083",_DEBEZIUM_DB_HOST="$(terraform output -raw cloudsql_private_ip_address)"
```

### Trigger GitOps manually via CLI
```bash
gcloud builds triggers run terrier-connect-main \
  --region=us-central1 \
  --project=$PROJECT_ID \
  --branch=main
```

### Infrastructure changes
```bash
cd infrastructure
terraform apply   # terraform.tfvars is loaded automatically
```

## Helm Deployment

Production manifests are rendered from [helm/terrier-connect](../helm/terrier-connect).

At build time, Cloud Build generates Helm values that inject:

- image tags for `client`, `server`, and `gateway`
- ingress, CORS, and Workload Identity settings
- Secret Manager values for DB password, Django secret key, and Google OAuth credentials
- runtime backend endpoints for the Terraform-managed Cassandra, Redis, Elasticsearch, Kafka, and Kafka Connect services

If Debezium connector registration is enabled, Cloud Build also reads dedicated Secret Manager credentials for Kafka Connect registration and passes them into an in-cluster Helm hook job.

Use [helm/terrier-connect/values.yaml](../helm/terrier-connect/values.yaml) as the baseline contract for deploy-time configuration.

Useful Terraform outputs after apply:

- `terraform output cassandra_host`
- `terraform output redis_url`
- `terraform output kafka_bootstrap_servers`
- `terraform output kafka_connect_url`
- `terraform output elasticsearch_url`
- `terraform output cloudsql_private_ip_address`

## Accessing the Application

Once DNS A records propagate and the ManagedCertificate is active:

- **Frontend**: `https://<your-domain>`
- **Backend API**: `https://<your-domain>/api/`

Check the Load Balancer IP:
```bash
terraform output ingress_ip_address
```

## Cleanup

```bash
cd infrastructure
terraform destroy
gsutil rm -r gs://${PROJECT_ID}-tf-state
```

## Troubleshooting

- **ManagedCertificate pending**: verify the domain A records point to the Ingress IP.
- **Cloud SQL connection errors**: confirm `CLOUDSQL_INSTANCE` value and Workload Identity binding.
- **GCS media access**: if private, use signed URLs or set `media_bucket_public = true` in `terraform.tfvars`.
- **Secret access denied in build**: verify `terrier-connect-cloudbuild-sa` has `roles/secretmanager.secretAccessor` — run `terraform apply` to reconcile.
- **GitOps trigger 400 error**: ensure the Cloud Build service agent has `roles/iam.serviceAccountTokenCreator` on the Cloud Build SA (managed by Terraform).
- **Build uses wrong SA**: confirm `serviceAccount` field in `cloudbuild-local.yaml` and `service_account` in the Terraform trigger resource both reference `terrier-connect-cloudbuild-sa`.
- **Platform pod scheduling pressure**: if Redis, Kafka, Cassandra, or Elasticsearch stay Pending, increase `gke_node_count` and/or `gke_node_machine_type` before re-applying.
