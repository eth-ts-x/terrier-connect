#!/bin/sh
set -e

# ── Wait for PostgreSQL ──────────────────────────────────────────
echo "Waiting for PostgreSQL..."
python << 'END'
import os, socket, time
host = os.getenv("DB_HOST", "db")
port = int(os.getenv("DB_PORT", "5432"))
for _ in range(60):
    try:
        with socket.create_connection((host, port), timeout=2):
            print("PostgreSQL is ready")
            break
    except OSError:
        print(f"PostgreSQL not ready at {host}:{port}, retrying...")
        time.sleep(1)
else:
    print("WARNING: PostgreSQL did not become ready in time.")
END

# ── Wait for Cassandra ───────────────────────────────────────────
echo "Waiting for Cassandra..."
python << 'END'
import os, socket, time
host = os.getenv("CASSANDRA_HOSTS", "cassandra").split(",")[0]
port = int(os.getenv("CASSANDRA_PORT", "9042"))
for _ in range(120):
    try:
        with socket.create_connection((host, port), timeout=2):
            print("Cassandra is ready")
            break
    except OSError:
        print(f"Cassandra not ready at {host}:{port}, retrying...")
        time.sleep(2)
else:
    print("WARNING: Cassandra did not become ready in time.")
END

# ── Django migrations (PostgreSQL) ───────────────────────────────
echo "Running PostgreSQL migrations..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

# ── Cassandra schema initialisation ──────────────────────────────
echo "Initialising Cassandra keyspace and tables..."
python manage.py init_cassandra || echo "WARNING: Cassandra init failed (will retry at app startup)"

# ── Elasticsearch index initialisation ───────────────────────────
echo "Initialising Elasticsearch index..."
python manage.py init_elasticsearch || echo "WARNING: ES init failed (search will be unavailable until index is created)"

# ── Run the main command ─────────────────────────────────────────
exec "$@"
