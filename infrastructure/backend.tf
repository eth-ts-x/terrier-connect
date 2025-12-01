terraform {
  backend "gcs" {
    prefix  = "terraform/state"
    # bucket is configured via -backend-config in cloudbuild.yaml
  }
}
