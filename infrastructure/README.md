# Terrier Connect - GCP Infrastructure

This directory contains Terraform configurations to deploy the Terrier Connect application on Google Cloud Platform (GCP) using:

- **Google Compute Engine (GCE)** - VM instance to run the application
- **Google Artifact Registry (GAR)** - Docker image storage
- **Google Cloud Storage (GCS)** - Terraform state backend
- **Google Cloud Build** - CI/CD pipeline automation

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   GitHub Repo   │────▶│   Cloud Build    │────▶│ Artifact Reg.   │
│   (Source)      │     │   (CI/CD)        │     │ (Docker Images) │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                │                         │
                                ▼                         ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │  Terraform State │     │   GCE Instance  │
                        │     (GCS)        │     │  (Application)  │
                        └──────────────────┘     └─────────────────┘
```

## Prerequisites

1. **GCP Project** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Terraform** (v1.0+) installed locally (for initial setup)
4. **GitHub repository** connected to Cloud Build

## Initial Setup

### 1. Create the GCS bucket for Terraform state (one-time setup)

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"

# Enable required APIs
gcloud services enable storage.googleapis.com --project=$PROJECT_ID

# Create the bucket for Terraform state
gsutil mb -p $PROJECT_ID -l $REGION gs://${PROJECT_ID}-tf-state
gsutil versioning set on gs://${PROJECT_ID}-tf-state
```

### 2. Configure Terraform variables

```bash
cd infrastructure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
```

### 3. Initialize and apply Terraform (first time)

```bash
# Initialize Terraform with the GCS backend
terraform init -backend-config="bucket=${PROJECT_ID}-tf-state"

# Review the plan
terraform plan -var="project_id=${PROJECT_ID}"

# Apply the configuration
terraform apply -var="project_id=${PROJECT_ID}"
```

### 4. Connect GitHub to Cloud Build

1. Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers)
2. Connect your GitHub repository
3. The trigger will be automatically created by Terraform, or you can create one manually

## Files Overview

| File | Description |
|------|-------------|
| `main.tf` | Main infrastructure resources (VPC, VM, IAM, GAR, etc.) |
| `variables.tf` | Input variable definitions |
| `outputs.tf` | Output values (IPs, URLs, etc.) |
| `backend.tf` | Terraform GCS backend configuration |
| `startup.sh` | VM startup script (installs Docker, pulls images) |
| `terraform.tfvars.example` | Example variable values |

## Cloud Build Pipeline

The `cloudbuild.yaml` file in the root directory defines the CI/CD pipeline:

1. **Build** - Builds Docker images for client and server
2. **Push** - Pushes images to Artifact Registry (tagged with commit SHA and `latest`)
3. **Terraform Init** - Initializes Terraform with GCS backend
4. **Terraform Plan** - Creates execution plan
5. **Terraform Apply** - Applies infrastructure changes
6. **Update Containers** - Updates running containers on the VM

## Manual Deployment

To manually trigger a build:

```bash
gcloud builds submit --config=cloudbuild.yaml \
  --substitutions=_REGION=us-central1,_ZONE=us-central1-a
```

## Accessing the Application

After deployment:

- **Frontend**: `http://<PUBLIC_IP>:3002`
- **Backend API**: `http://<PUBLIC_IP>:8000`

Get the public IP:
```bash
terraform output public_ip
```

SSH into the VM:
```bash
gcloud compute ssh terrier-connect-vm --zone=us-central1-a
```

## Viewing Logs

### VM Startup Script Logs
```bash
gcloud compute ssh terrier-connect-vm --zone=us-central1-a \
  --command="sudo cat /var/log/startup-script.log"
```

### Docker Container Logs
```bash
gcloud compute ssh terrier-connect-vm --zone=us-central1-a \
  --command="cd /opt/terrier-connect && docker compose logs -f"
```

### Cloud Build Logs
View in [Cloud Build History](https://console.cloud.google.com/cloud-build/builds)

## Cleanup

To destroy all resources:

```bash
cd infrastructure
terraform destroy -var="project_id=${PROJECT_ID}"

# Optionally delete the state bucket
gsutil rm -r gs://${PROJECT_ID}-tf-state
```

## Cost Estimate

- **GCE e2-medium**: ~$25/month
- **Artifact Registry**: ~$0.10/GB/month
- **Cloud Build**: 120 free build-minutes/day
- **Static IP**: ~$3/month (when not attached to running VM)

## Troubleshooting

### Images not pulling on VM
```bash
# SSH into VM and check Docker authentication
gcloud compute ssh terrier-connect-vm --zone=us-central1-a
gcloud auth configure-docker us-central1-docker.pkg.dev
docker compose pull
```

### Terraform state lock
```bash
terraform force-unlock <LOCK_ID>
```

### Cloud Build permission errors
Ensure the Cloud Build service account has the required IAM roles (these are created by Terraform).
