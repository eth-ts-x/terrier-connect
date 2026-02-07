#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Waiting for database..."
# Simple check to see if we can reach the DB port (requires nothing but /dev/tcp)
# Or just let it fail and let Docker restart the container if it's not ready.
# For now, we'll just run migrations.
python << END
import socket
import time
import sys

port = 5432
host = "db" # This should match the DB_HOST in .env

while True:
    try:
        with socket.create_connection((host, port), timeout=1):
            print("PostgreSQL started")
            break
    except OSError:
        print("PostgreSQL not ready, waiting...")
        time.sleep(1)
END

echo "Applying database migrations..."
python manage.py migrate --noinput

# Execute the passed command
exec "$@"
