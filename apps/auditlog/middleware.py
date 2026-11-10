import uuid
import logging

from django.db import OperationalError

from .context import reset_audit_request, set_audit_request

logger = logging.getLogger(__name__)


class AuditContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.audit_request_id = uuid.uuid4()
        token = set_audit_request(request)
        try:
            response = self.get_response(request)
            request.audit_status_code = response.status_code
            response["X-Request-ID"] = str(request.audit_request_id)
            user = getattr(request, "user", None)
            if request.path.startswith("/api/v1/") and user and user.is_authenticated:
                from .services import audit_event
                try:
                    audit_event(category="access", action="request_completed", actor=user, metadata={"status_code": response.status_code})
                except OperationalError as error:
                    # Access logging must never turn a successful read request
                    # into a 500 response when SQLite is briefly write-locked.
                    logger.warning("Skipped access audit event: %s", error)
            return response
        finally:
            reset_audit_request(token)
