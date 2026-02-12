# Terrier Connect - GCP Infrastructure (GKE + Cloud SQL + GCS)

This directory now provisions a production-style GKE setup:

- **GKE** (Kubernetes) for app workloads
- **Cloud SQL (Postgres)** with **private IP**
- **Cloud Storage** for media uploads
- **Artifact Registry** for Docker images
- **Cloud DNS** + **GKE Ingress** with **Managed Certificates**
- **GCS** bucket for Terraform state

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   GitHub Repo   │────▶│   Cloud Build    │────▶│ Artifact Reg.   │
│   (Source)      │     │   (CI/CD)        │     │ (Docker Images) │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                │                         │
                                ▼                         ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │  Terraform State │     │       GKE        │
                        │     (GCS)        │     │  (Workloads)     │
                        └──────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                                              ┌────────────────────┐
                                              │ Cloud SQL + GCS     │
                                              └────────────────────┘
```

## Prerequisites

1. **GCP Project** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Terraform** (v1.3+) installed locally (initial setup)
4. **A domain name** (Cloud DNS zone created by Terraform)

## Initial Setup

### 1. Create the GCS bucket for Terraform state (one-time setup)

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
# Edit terraform.tfvars with your values
```

### 3. Initialize and apply Terraform

```bash
terraform init -backend-config="bucket=${PROJECT_ID}-tf-state"
terraform plan -var="project_id=${PROJECT_ID}"
terraform apply -var="project_id=${PROJECT_ID}"
```

## Kubernetes Manifests

Production manifests use Kustomize at [k8s/overlays/prod](../k8s/overlays/prod). Update these placeholders before deploying:

- `ALLOWED_HOSTS`, `domain` in [k8s/overlays/prod/ingress.yaml](../k8s/overlays/prod/ingress.yaml)
- `ManagedCertificate` domains in [k8s/overlays/prod/managed-cert.yaml](../k8s/overlays/prod/managed-cert.yaml)
- `CLOUDSQL_INSTANCE`, `GS_BUCKET_NAME`, `GS_PROJECT_ID` in [k8s/overlays/prod/kustomization.yaml](../k8s/overlays/prod/kustomization.yaml)
- `iam.gke.io/gcp-service-account` in [k8s/overlays/prod/patch-server-serviceaccount.yaml](../k8s/overlays/prod/patch-server-serviceaccount.yaml)
- Secrets in [k8s/overlays/prod/kustomization.yaml](../k8s/overlays/prod/kustomization.yaml)

## Cloud Build Pipeline

The pipeline in [cloudbuild.yaml](../cloudbuild.yaml) builds images, applies Terraform, then deploys the prod overlay to GKE.

## Accessing the Application

Once the DNS A records propagate and the ManagedCertificate is active:

- **Frontend**: https://<your-domain>
- **Backend API**: https://<your-domain>/api/

You can also check the Load Balancer IP:

```bash
terraform output ingress_ip_address
```

## Cleanup

```bash
cd infrastructure
terraform destroy -var="project_id=${PROJECT_ID}"
gsutil rm -r gs://${PROJECT_ID}-tf-state
```

## Troubleshooting

- **ManagedCertificate pending**: verify the domain A records point to the Ingress IP.
- **Cloud SQL connection errors**: confirm `CLOUDSQL_INSTANCE` and Workload Identity binding.
- **GCS media access**: if private, use signed URLs or set `media_bucket_public = true`.
