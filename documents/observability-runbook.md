# Terrier Connect Observability Runbook

This runbook is the operator-facing guide for the production observability stack.

It complements the Terraform-managed monitoring resources in [infrastructure/main.tf](../infrastructure/main.tf) and the infrastructure overview in [infrastructure/README.md](../infrastructure/README.md).

---

## Scope

The current production observability stack covers:

- OpenTelemetry traces for the Django API and GraphQL gateway
- trace propagation across the Cassandra outbox, Kafka relay, and Kafka consumers
- structured JSON logs with request and trace correlation
- Prometheus metrics from Django, the GraphQL gateway, async workers, and the Kafka Connect monitor
- Cloud Monitoring dashboards and alert policies
- gateway SLOs and burn-rate alerts
- public uptime checks for the homepage and API health endpoint

---

## Primary Signals

### Public availability

Use these first when the report is "the site is down":

- homepage uptime check
- API health uptime check
- GKE ingress health
- managed certificate readiness

### User-facing request path

Use these when requests are slow or failing:

- gateway request rate
- gateway 5xx ratio
- gateway p95 latency
- Django request volume
- gateway availability and latency SLOs

### Async pipeline

Use these when timelines, notifications, likes, or search appear stale:

- outbox pending events
- outbox oldest event age
- async consumer failures
- worker error logs

### CDC and connector health

Use these when follow projections or sink pipelines break:

- Kafka Connect availability
- Kafka Connect failed connectors
- DLQ retained records

---

## Key Endpoints

Production endpoints:

- frontend: `https://<domain>/`
- REST API: `https://<domain>/api/`
- GraphQL gateway: `https://<domain>/graphql`
- API health: `https://<domain>/api/posts/health/`

Application health and metrics inside the cluster:

- Django health: `/api/posts/health/`
- gateway health: `/healthz`
- Django metrics: `/metrics`
- gateway metrics: `/metrics`
- worker metrics: `/metrics` on the worker metrics port

---

## Alert Inventory

### Edge and user-facing alerts

- gateway high 5xx ratio
- gateway high p95 latency
- gateway availability fast burn
- gateway availability slow burn
- public homepage uptime failing
- public API health uptime failing

### Async pipeline alerts

- async pipeline failures
- async outbox backlog age high

### Connector alerts

- Kafka Connect down
- Kafka Connect connector failed
- Kafka Connect DLQ has retained records

---

## Triage Playbooks

### 1. Public site appears down

Check in this order:

1. homepage uptime alert/check
2. API health uptime alert/check
3. ingress IP, DNS, and TLS certificate state
4. client, gateway, and server pod readiness
5. recent deploys from Cloud Build and Helm

If the homepage fails but API health passes, suspect frontend or ingress routing.

If both fail, suspect ingress, certificate, namespace-wide outage, or shared platform failure.

### 2. Requests are failing or slow

Check in this order:

1. gateway 5xx ratio
2. gateway p95 latency
3. gateway availability burn-rate alerts
4. recent traces spanning gateway to Django
5. Django health endpoint and backend dependency checks

The health endpoint already validates:

- PostgreSQL
- Cassandra
- Redis
- Elasticsearch

If the gateway is healthy but traces show backend delays, inspect downstream database or cache latency.

### 3. Feeds, notifications, likes, or search are stale

Check in this order:

1. outbox pending events
2. outbox oldest event age
3. async consumer error rate
4. outbox relay logs
5. consumer worker logs
6. Kafka broker health

Typical interpretations:

- rising pending events + rising oldest age: outbox relay stalled or Kafka unavailable
- low backlog + high consumer failures: handlers are running but failing
- search issues only: inspect `consumer-search-indexer` and Elasticsearch health

### 4. Follow CDC or connector flows are broken

Check in this order:

1. Kafka Connect availability
2. failed connector state panel
3. DLQ retained records
4. connector logs in the Kafka Connect deployment
5. connector status from the Kafka Connect REST API

Typical interpretations:

- Connect down: platform/runtime problem
- connector failed: connector config or dependency problem
- DLQ records present: data/schema issue requiring replay or manual cleanup

---

## Post-Deploy Verification Checklist

After a production deploy, verify:

1. `terraform validate` and `terraform plan` are clean for monitoring resources
2. Helm rollout completed for server, gateway, workers, and `connect-monitor`
3. `/api/posts/health/` returns healthy externally
4. `/graphql` responds through the public domain
5. dashboard panels populate with fresh data
6. no connector is in `FAILED` state
7. DLQ retained records remain at zero or expected baseline
8. uptime checks are green

---

## Useful Commands

```bash
terraform -chdir=infrastructure plan -no-color
terraform -chdir=infrastructure apply -auto-approve -no-color
helm lint helm/terrier-connect
kubectl get pods -n terrier-connect
kubectl get pods -n terrier-platform
kubectl logs deploy/terrier-kafka-connect -n terrier-platform
```

---

## Notes

- Public uptime checks are intentionally black-box and validate the deployed surface, not just in-cluster pod health.
- The API health endpoint is a dependency-aware health check and is the quickest backend sanity test during an incident.
- Async trace propagation lets traces cross the request → outbox → Kafka → worker boundary, so recent incidents should be correlated through trace IDs in logs and Cloud Trace.
