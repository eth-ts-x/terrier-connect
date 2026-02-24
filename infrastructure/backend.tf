terraform {
  backend "gcs" {
    prefix  = "terraform/state"
    # bucket should be configured at the first step of the initialization
  }
}
