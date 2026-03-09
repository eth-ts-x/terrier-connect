# Debezium connector templates

Files under [connectors/](connectors) are committed as templates and may contain `${ENV_VAR}` placeholders for secrets.

Render a connector file before submitting it to Kafka Connect:

```bash
DB_PASSWORD=your-secret python3 debezium/render_connector.py \
  debezium/connectors/postgres-follow-source.json \
  /tmp/postgres-follow-source.rendered.json
```

For production, the Helm chart can register the follow connector automatically with a post-install/post-upgrade job when `debezium.enabled=true` and `debezium.connectUrl` is set. The job reads dedicated Secret Manager values for `terrier-connect-debezium-db-user` and `terrier-connect-debezium-db-password` through the Cloud Build deploy step.

For a manual deploy, enable that path with Cloud Build substitutions such as `_ENABLE_DEBEZIUM_CONNECTOR_REGISTRATION=true`, `_KAFKA_CONNECT_URL=http://terrier-kafka-connect.terrier-platform.svc.cluster.local:8083`, and `_DEBEZIUM_DB_HOST=<cloud-sql-private-ip>`.
