#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Waiting for database..."
# Simple check to see if we can reach the DB port (requires nothing but /dev/tcp)
# Or just let it fail and let Docker restart the container if it's not ready.
# For now, we'll just run migrations.
python << END
import os
import socket
import time
import sys

port = int(os.getenv("DB_PORT", "5432"))
host = os.getenv("DB_HOST", "db")

while True:
    try:
        with socket.create_connection((host, port), timeout=1):
            print("PostgreSQL started")
            break
    except OSError:
        print(f"PostgreSQL not ready at {host}:{port}, waiting...")
        time.sleep(1)
END

echo "Applying database migrations..."
python manage.py migrate --noinput

# Execute the passed command
exec "$@"
