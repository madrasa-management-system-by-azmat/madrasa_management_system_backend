"""ASGI entry point for Django HTTP APIs."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.asgi import get_asgi_application

application = get_asgi_application()
