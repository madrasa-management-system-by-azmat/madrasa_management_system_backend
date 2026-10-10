from django.apps import apps
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .context import get_audit_request
from .models import ArchiveBatch, ArchivePolicy, ArchivedRecord, AuditEvent, LegalHold
from .services import audit_event

EXCLUDED_APPS = {"auditlog", "admin", "auth", "contenttypes", "sessions", "token_blacklist"}

def snapshot(instance):
    data = {}
    for field in instance._meta.concrete_fields:
        value = getattr(instance, field.attname, None)
        data[field.name] = str(value) if value is not None else None
    return data

@receiver(pre_save)
def capture_before(sender, instance, **kwargs):
    if sender._meta.app_label in EXCLUDED_APPS or not instance.pk:
        return
    try:
        instance._audit_before = snapshot(sender.objects.get(pk=instance.pk))
    except sender.DoesNotExist:
        pass

@receiver(post_save)
def audit_save(sender, instance, created, raw=False, **kwargs):
    if raw or sender._meta.app_label in EXCLUDED_APPS or not hasattr(instance, "madrasa_id"):
        return
    request = get_audit_request()
    if not request:
        return
    after = snapshot(instance)
    before = getattr(instance, "_audit_before", {})
    changes = {key: {"before": before.get(key), "after": value} for key, value in after.items() if before.get(key) != value} if not created else {}
    audit_event(category="data", action="create" if created else "update", madrasa=getattr(instance, "madrasa", None), entity=instance, before=before, after=after, changes=changes)

@receiver(post_delete)
def audit_delete(sender, instance, **kwargs):
    if sender._meta.app_label in EXCLUDED_APPS or not hasattr(instance, "madrasa_id") or not get_audit_request():
        return
    audit_event(category="data", action="delete", madrasa=getattr(instance, "madrasa", None), entity_type=f"{sender._meta.app_label}.{sender._meta.model_name}", entity_id=str(instance.pk), entity_label=str(instance)[:300], before=snapshot(instance))
