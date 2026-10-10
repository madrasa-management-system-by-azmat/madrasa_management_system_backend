import uuid

from django.db import transaction
from django.utils import timezone

from .context import get_audit_request
from .models import AuditEvent

SENSITIVE_KEYS = {"password", "token", "refresh", "access", "secret", "cnic", "guardian_cnic"}


def redact(value):
    if isinstance(value, dict):
        return {key: "[REDACTED]" if any(word in key.lower() for word in SENSITIVE_KEYS) else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def event_hash_payload(*, request_id, category, action, madrasa_id, actor_id, entity_type, entity_id, before, after, changes, metadata, previous_hash, created_at):
    return {
        "request_id": str(request_id), "category": category, "action": action,
        "madrasa": madrasa_id, "actor": actor_id, "entity_type": entity_type,
        "entity_id": entity_id, "before": before, "after": after,
        "changes": changes, "metadata": metadata, "previous_hash": previous_hash,
        "created_at": created_at.isoformat(),
    }


@transaction.atomic
def audit_event(*, category, action, madrasa=None, actor=None, entity=None, entity_type="", entity_id="", entity_label="", before=None, after=None, changes=None, metadata=None):
    request = get_audit_request()
    actor = actor or (getattr(request, "user", None) if request and getattr(request, "user", None) and request.user.is_authenticated else None)
    if not madrasa and actor:
        madrasa = getattr(getattr(actor, "profile", None), "madrasa", None)
    if entity:
        entity_type = f"{entity._meta.app_label}.{entity._meta.model_name}"
        entity_id = str(entity.pk)
        entity_label = str(entity)[:300]
    previous = AuditEvent.objects.select_for_update().filter(madrasa=madrasa).order_by("-id").values_list("event_hash", flat=True).first() or ""
    request_id = getattr(request, "audit_request_id", uuid.uuid4())
    created_at = timezone.now()
    clean_before, clean_after = redact(before or {}), redact(after or {})
    clean_changes, clean_metadata = redact(changes or {}), redact(metadata or {})
    payload = event_hash_payload(request_id=request_id, category=category, action=action,
        madrasa_id=getattr(madrasa, "pk", None), actor_id=getattr(actor, "pk", None),
        entity_type=entity_type, entity_id=entity_id, before=clean_before, after=clean_after,
        changes=clean_changes, metadata=clean_metadata, previous_hash=previous, created_at=created_at)
    event_hash = AuditEvent.compute_hash(payload)
    return AuditEvent.objects.create(madrasa=madrasa, request_id=request_id, category=category, action=action, actor=actor, actor_label=(actor.get_full_name() or actor.username) if actor else "system", entity_type=entity_type, entity_id=entity_id, entity_label=entity_label, before=clean_before, after=clean_after, changes=clean_changes, metadata=clean_metadata, method=getattr(request, "method", ""), path=getattr(request, "path", ""), status_code=getattr(request, "audit_status_code", None), ip_address=request.META.get("REMOTE_ADDR") if request else None, user_agent=request.META.get("HTTP_USER_AGENT", "")[:500] if request else "", previous_hash=previous, event_hash=event_hash, created_at=created_at)
