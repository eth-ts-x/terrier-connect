"""
WSGI config for terrierconnect project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os

from core.tracing import initialize_telemetry
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "terrierconnect.settings")
initialize_telemetry()

application = get_wsgi_application()
