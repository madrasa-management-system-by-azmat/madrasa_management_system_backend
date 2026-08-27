import os

from django.http import HttpResponse


class CorsMiddleware:
    """Minimal CORS support for the local Next.js frontend."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_origins = {
            origin.strip()
            for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
            if origin.strip()
        }

    def __call__(self, request):
        origin = request.headers.get("Origin")

        if request.method == "OPTIONS" and origin in self.allowed_origins:
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)

        if origin in self.allowed_origins:
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Credentials"] = "true"
            response["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response["Vary"] = "Origin"

        return response
