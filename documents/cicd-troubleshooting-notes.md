# CI/CD Troubleshooting Notes

## Overview

This document records all problems encountered and solutions applied while setting up the
Cloud Build CI/CD pipeline (local + GitOps) for the terrier-connect project.

---

## Problem 1: `envsubst` not available in Cloud Build image

**Symptom:** `cluster-vars.env` was created but empty. Kustomize failed with
`fieldPath data.DOMAIN_NAME is missing`.

**Root cause:** `gcr.io/cloud-builders/gcloud` does not have `envsubst` installed.
The shell redirect `>` creates the file before the missing command fails, so the
file exists but is empty.

**Fix:** Replaced `envsubst` with a bash heredoc using Cloud Build's native
`${_VAR}` substitutions — no external tools needed.

```yaml
- name: 'gcr.io/cloud-builders/gcloud'
  entrypoint: 'bash'
  args:
    - '-c'
    - |
      cat > k8s/overlays/prod/cluster-vars.env << EOF
      DOMAIN_NAME=${_DOMAIN_NAME}
      ...
      EOF
```

---

## Problem 2: Cloud Build rejected `${VAR}` in envsubst argument list

**Symptom:** `INVALID_ARGUMENT` error on `gcloud builds submit`.

**Root cause:** Cloud Build parses all `${VAR}` syntax at submit time. Any variable
not prefixed with `_` or not a built-in is rejected.

**Fix:** Removed the explicit variable list from the `envsubst` call (later replaced
entirely by the heredoc fix above).

---

## Problem 3: `_ZONE` substitution not matched in template

**Symptom:**
```
INVALID_ARGUMENT: key "_ZONE" in the substitution data is not matched in the template
```

**Root cause:** `_ZONE` was declared under `substitutions:` but never referenced
anywhere in the build steps.

**Fix:** Removed `_ZONE` from `substitutions` in `cloudbuild-local.yaml` and later
from `cloudbuild.yaml`.

---

## Problem 4: Terraform `replication { auto {} }` syntax error

**Symptom:** `terraform init` failed with a syntax error on Secret Manager secret
resources.

**Root cause:** Terraform does not allow two nested blocks on one line.

**Fix:** Expanded to multi-line:
```hcl
replication {
  auto {}
}
```

---

## Problem 5: `google_cloudbuild_trigger` returned `400 invalid argument` with `github {}` block

**Symptom:** `terraform apply` failed when creating the Cloud Build trigger.

**Root cause:** The `github {}` block is 1st gen only. GCP Console creates 2nd gen
connections, which require `repository_event_config` + `google_cloudbuildv2_repository`.

**Fix:** Replaced `github {}` with:
```hcl
resource "google_cloudbuildv2_repository" "github_repo" { ... }

resource "google_cloudbuild_trigger" "gitops_main" {
  repository_event_config {
    repository = google_cloudbuildv2_repository.github_repo.id
    push { branch = "^main$" }
  }
  ...
}
```

---

## Problem 6: `filename` field invalid with `repository_event_config`

**Symptom:** Trigger still returned `400 invalid argument` after switching to 2nd gen.

**Root cause:** The `filename` field is only valid for 1st gen triggers
(`trigger_template` or `github` block). For 2nd gen (`repository_event_config`),
`git_file_source` must be used.

**Fix:**
```hcl
git_file_source {
  path       = "cloudbuild.yaml"
  repository = google_cloudbuildv2_repository.github_repo.id
  revision   = "refs/heads/main"
  repo_type  = "GITHUB"
}
```

---

## Problem 7: `google_cloudbuild_trigger` `400 invalid argument` caused by `service_account` field

**Symptom:** `terraform apply` returned `400 invalid argument` when creating
`google_cloudbuild_trigger`, even after fixing the 1st gen / 2nd gen issues.

**Root cause:** When `service_account` is set on a Cloud Build trigger, GCP requires
the **Cloud Build service agent** (`service-NUMBER@gcp-sa-cloudbuild.iam.gserviceaccount.com`)
to hold `roles/iam.serviceAccountTokenCreator` on the target SA **before** the trigger
can be created. Without this binding, GCP silently rejects the request with `400`
instead of a descriptive permission error — making it very hard to diagnose.

This is separate from the roles the SA itself holds. It is a handshake that lets the
Cloud Build control plane generate short-lived tokens as the user-managed SA.

**Fix:** Add the token creator binding in Terraform before the trigger resource:

```hcl
resource "google_service_account_iam_member" "cloudbuild_agent_token_creator" {
  service_account_id = google_service_account.cloudbuild_sa.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
}
```

And ensure the trigger `depends_on` it:

```hcl
resource "google_cloudbuild_trigger" "gitops_main" {
  ...
  service_account = google_service_account.cloudbuild_sa.id

  depends_on = [
    google_project_service.apis,
    google_project_iam_member.cloudbuild_roles,
    google_service_account_iam_member.cloudbuild_agent_token_creator,
  ]
}
```

**Key insight:** GCP validates the `service_account` field at trigger *creation* time,
not at build runtime. The binding must exist before `terraform apply` — not just before
the build runs.

---

## Problem 8: Secret Manager `PermissionDenied` on Cloud Build SA

**Symptom:**
```
Permission 'secretmanager.versions.access' denied for resource
'projects/.../secrets/terrier-connect-maps-api-key/versions/latest'
```

**Root cause (layered):**
1. The project never auto-created `PROJECT_NUMBER@cloudbuild.gserviceaccount.com`
   (modern GCP projects don't). Builds ran as the Compute Engine default SA
   (`PROJECT_NUMBER-compute@developer.gserviceaccount.com`).
2. IAM grants were targeting the legacy Cloud Build SA that didn't exist.
3. `gcloud builds submit` does not respect the `serviceAccount` field in the YAML
   unless a user-managed SA is specified.

**Fix:** Created a dedicated Cloud Build SA in Terraform:
```hcl
resource "google_service_account" "cloudbuild_sa" {
  account_id   = "terrier-connect-cloudbuild-sa"
  display_name = "Terrier Connect Cloud Build SA"
}

# Required: lets the Cloud Build service agent impersonate our SA
resource "google_service_account_iam_member" "cloudbuild_agent_token_creator" {
  service_account_id = google_service_account.cloudbuild_sa.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
}
```

Consolidated all IAM roles into a single `for_each` resource:
```hcl
locals {
  cloudbuild_sa = "serviceAccount:${google_service_account.cloudbuild_sa.email}"
  cloudbuild_roles = toset([
    "roles/editor",
    "roles/container.admin",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.serviceAccountUser",
    "roles/cloudsql.admin",
    "roles/dns.admin",
    "roles/artifactregistry.writer",
    "roles/secretmanager.secretAccessor",
    "roles/storage.admin",
    "roles/logging.logWriter",
  ])
}

resource "google_project_iam_member" "cloudbuild_roles" {
  for_each   = local.cloudbuild_roles
  project    = var.project_id
  role       = each.value
  member     = local.cloudbuild_sa
  depends_on = [google_project_service.apis]
}
```

Pinned `serviceAccount` in `cloudbuild-local.yaml` using `${PROJECT_ID}` built-in:
```yaml
serviceAccount: 'projects/${PROJECT_ID}/serviceAccounts/terrier-connect-cloudbuild-sa@${PROJECT_ID}.iam.gserviceaccount.com'
```

---

## Problem 9: `serviceAccount` placed under `options` in YAML

**Symptom:**
```
ERROR: interpreting cloudbuild-local.yaml as build config: .options.serviceAccount: unused
```

**Root cause:** `serviceAccount` is a **top-level** Cloud Build YAML field, not a
field under `options`.

**Fix:** Moved `serviceAccount` out of the `options` block to the top level.

---

## Problem 10: GitOps Terraform Plan failed — missing variables

**Symptom:** Terraform Plan step in Cloud Build failed:
```
Error: No value for required variable
  on variables.tf line 130: variable "github_owner"
```

**Root cause:** `terraform.tfvars` is gitignored (correct — it contains secrets).
Running Terraform inside Cloud Build means the file is never present in the build
environment.

**Fix + best practice:** Removed Terraform steps entirely from `cloudbuild.yaml`.
Infra and app deploys are now separate concerns:

| Action | Method |
|---|---|
| App deploy (code push) | GitOps — push to `main` triggers `cloudbuild.yaml` |
| App deploy (manual) | `gcloud builds submit --config cloudbuild-local.yaml` |
| Infra change | `terraform apply` locally (has `terraform.tfvars`) |

---

## Problem 11: GitOps trigger fired on `master` branch, not `main`

**Symptom:** Trigger was not firing on pushes to the default branch.

**Root cause:** The repo's default branch was still named `master`, but the Terraform
trigger was configured with `branch = "^main$"`.

**Fix:** Renamed the branch to `main`:
```bash
git branch -m master main
git push origin -u main
git push origin --delete master
# Set default branch in GitHub: Settings → Branches → Default branch → main
```

---

## Problem 12: Backend health check, readinessProbe and livenessProbe problem

**Symptom:** Backend returns code 502, health check are UNHEALTHY

**Root cause:** Backend health check failed, since readinessProbe and livenessProbe are
checking path /, which has no API returns code 200. Also the pods IP address are blocked by Django.

**Fix:** Adjust readinessProbe and livenessProbe to check a code 200 guarenteed API, and add code
in setting.py to add internal pods IP address to the ALLOWED_HOSTS.
```bash
try:
    pod_ip = socket.gethostbyname(socket.gethostname())
    ALLOWED_HOSTS.append(pod_ip)
except Exception:
    pass
```

---

## Key Lessons

- **`gcloud builds submit` ignores `serviceAccount` in YAML** unless it is a
  user-managed SA. Always create a dedicated SA and set `serviceAccount` at the
  top level in the YAML.
- **`roles/iam.serviceAccountTokenCreator`** must be granted on the custom SA to
  the Cloud Build service agent (`service-NUMBER@gcp-sa-cloudbuild`), otherwise
  Cloud Build cannot impersonate it.
- **`filename` vs `git_file_source`**: `filename` is 1st gen only. Use
  `git_file_source` with `repository_event_config` (2nd gen).
- **Don't run Terraform in app CI/CD.** Separate infra changes (manual Terraform)
  from app deploys (Cloud Build). `terraform.tfvars` should never be in git.
- **`${PROJECT_ID}`** is a built-in Cloud Build variable available in every build —
  use it instead of hardcoding project IDs in YAML files.
- **`.terraform.lock.hcl`** should be committed to git. It locks provider versions
  and is not sensitive. Only `.terraform/`, `*.tfstate`, and `*.tfvars` should be
  gitignored.
