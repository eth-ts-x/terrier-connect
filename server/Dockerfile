# Start from an official Python image.
FROM python:3.10-slim

# Set working directory inside the container.
WORKDIR /app

# Install system dependencies required by Django or other libraries.
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install them first to leverage Docker's layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the working directory.
COPY . .

# Set environment variables (you can override these with docker-compose).
ENV PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=terrierconnect.settings

# Collect static files for production (if needed).
RUN python manage.py collectstatic --noinput

# Expose the port on which Django/Gunicorn will listen.
EXPOSE 8000

# Copy entrypoint script and set permissions
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Use entrypoint script to automate migrations
ENTRYPOINT ["/entrypoint.sh"]

# Run the Django development server or Gunicorn in production.
# For local development/testing, you might use `python manage.py runserver 0.0.0.0:8000`
# For production, we recommend Gunicorn:
CMD ["gunicorn", "terrierconnect.wsgi:application", "--bind", "0.0.0.0:8000"]
