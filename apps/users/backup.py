"""Tenant-scoped backup and restore helpers."""

import io
import json
import os
import zipfile
from pathlib import Path

from django.conf import settings
from django.core import serializers
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

# Order matters for foreign keys; reverse order is used when clearing data.
MODEL_LABELS = [
    "students.department",
    "students.halaqa",
    "hostel.hostelwing",
    "finance.fund",
    "finance.donor",
    "users.madrasaprofile",
    "students.academicclass",
    "academics.subject",
    "staff.staff",
    "students.student",
    "hostel.hostelroom",
    "exams.internalexam",
    "exams.internalexampaper",
    "exams.internalexamresult",
    "staff.halaqaassignment",
    "staff.staffattendance",
    "students.studentattendance",
    "hifz.hifzdailylog",
    "hostel.hostelallocation",
    "hostel.gatepass",
    "exams.wafaqboardregistration",
    "exams.wafaqresult",
    "finance.donation",
    "finance.expense",
    "finance.studentfeelog",
    "finance.studentmonthlyfee",
    "finance.studentfeepayment",
    "finance.teachersalary",
    "finance.studentsponsorship",
]

MEDIA_FIELDS = {
    "users.madrasaprofile": ("logo",),
    "staff.staff": ("photo",),
    "students.student": ("photo",),
}


def _model(label):
    from django.apps import apps

    return apps.get_model(label)


def _tenant_queryset(model, tenant):
    return model.objects.filter(madrasa=tenant)


def _safe_media_path(name):
    root = Path(settings.MEDIA_ROOT).resolve()
    destination = (root / name).resolve()
    if root not in destination.parents and destination != root:
        raise ValidationError("Invalid media path in backup.")
    return destination


def create_backup(tenant):
    """Return a BytesIO ZIP containing a portable tenant-only snapshot."""
    records = []
    media_names = set()

    for label in MODEL_LABELS:
        model = _model(label)
        queryset = _tenant_queryset(model, tenant)
        records.extend(json.loads(serializers.serialize("json", queryset)))
        for field_name in MEDIA_FIELDS.get(label, ()):
            for instance in queryset.exclude(**{field_name: ""}).exclude(**{f"{field_name}__isnull": True}):
                name = getattr(instance, field_name).name
                if name:
                    media_names.add(name)

    payload = {
        "format": "madrasa-management-tenant-backup",
        "version": 1,
        "source": {
            "madrasa_id": tenant.id,
            "madrasa_slug": tenant.slug,
            "exported_at": timezone.now().isoformat(),
        },
        "records": records,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("backup.json", json.dumps(payload, ensure_ascii=False, default=str, indent=2))
        for name in sorted(media_names):
            path = _safe_media_path(name)
            if path.is_file():
                archive.write(path, f"media/{name.replace(os.sep, '/')}")
    output.seek(0)
    return output


def restore_backup(uploaded_file, tenant):
    """Replace current tenant data from a backup generated for that tenant."""
    try:
        with zipfile.ZipFile(uploaded_file) as archive:
            if "backup.json" not in archive.namelist():
                raise ValidationError("Backup archive does not contain backup.json.")
            payload = json.loads(archive.read("backup.json").decode("utf-8"))
            if payload.get("format") != "madrasa-management-tenant-backup" or payload.get("version") != 1:
                raise ValidationError("Unsupported backup format.")
            if payload.get("source", {}).get("madrasa_slug") != tenant.slug:
                raise ValidationError("This backup belongs to a different madrasa.")
            records = payload.get("records")
            if not isinstance(records, list):
                raise ValidationError("Backup records are invalid.")

            allowed = set(MODEL_LABELS)
            if any(record.get("model") not in allowed for record in records):
                raise ValidationError("Backup contains unsupported records.")

            # Preserve the archive in memory so media can be extracted after DB restore.
            media_entries = [name for name in archive.namelist() if name.startswith("media/") and not name.endswith("/")]
            media_data = {name[6:]: archive.read(name) for name in media_entries}
    except zipfile.BadZipFile as error:
        raise ValidationError("Invalid backup ZIP file.") from error
    except json.JSONDecodeError as error:
        raise ValidationError("Backup JSON is invalid.") from error

    by_model = {label: [] for label in MODEL_LABELS}
    for record in records:
        record = dict(record)
        fields = dict(record.get("fields", {}))
        fields["madrasa"] = tenant.id
        record["fields"] = fields
        by_model[record["model"]].append(record)

    with transaction.atomic():
        # Delete dependent records first; tenant itself and users are deliberately retained.
        for label in reversed(MODEL_LABELS):
            _tenant_queryset(_model(label), tenant).delete()

        for label in MODEL_LABELS:
            serialized = by_model[label]
            if not serialized:
                continue
            for deserialized in serializers.deserialize("json", json.dumps(serialized, ensure_ascii=False)):
                deserialized.save(save_m2m=True)

        for name, content in media_data.items():
            destination = _safe_media_path(name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)

    return {"records": len(records), "media_files": len(media_data), "exported_at": payload["source"].get("exported_at")}
