#!/bin/bash
set -e

# Log output to file for debugging
exec > >(tee /var/log/startup-script.log) 2>&1
echo "Starting VM setup at $(date)"

# Update and install dependencies
apt-get update
apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git

# Install Docker
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Authenticate Docker with Google Artifact Registry
gcloud auth configure-docker ${region}-docker.pkg.dev --quiet

# Create app directory
mkdir -p /opt/terrier-connect
cd /opt/terrier-connect

# Create docker-compose.yml
cat <<EOF > docker-compose.yml
version: "3.8"
services:
  client:
    image: ${docker_image_client}
    container_name: client
    ports:
      - "3002:80"
    restart: always
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  server:
    image: ${docker_image_server}
    container_name: server
    ports:
      - "8000:8000"
    command: gunicorn terrierconnect.wsgi:application --bind 0.0.0.0:8000
    restart: always
    environment:
      - DEBUG=0
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
EOF

# Pull latest images
echo "Pulling Docker images..."
docker compose pull

# Start services
echo "Starting services..."
docker compose up -d

echo "VM setup completed at $(date)"
