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
    "finance.financialcategory",
    "library.librarycategory",
    "library.libraryshelf",
    "fatwas.fatwacategory",
    "fatwas.fatwatag",
    "fatwas.fatwanumbersequence",
    "meetings.meetingtype",
    "meetings.meetingnumbersequence",
    "tasks.taskcategory",
    "tasks.tasknumbersequence",
    "documents.documentcategory",
    "documents.documentfolder",
    "documents.documentnumbersequence",
    "guardians.guardianprofile",
    "leaves.institutioncalendarday",
    "leaves.leavetype",
    "leaves.leavepolicy",
    "leaves.leavepolicyrule",
    "development.disciplinecategory",
    "development.rewardcategory",
    "certificates.certificatenumbersequence",
    "operations.operationslocation",
    "operations.itemcategory",
    "operations.vendor",
    "users.madrasaprofile",
    "students.academicclass",
    "students.academicyear",
    "academics.subject",
    "academics.classoffering",
    "academics.curriculumplan",
    "academics.curriculumbook",
    "academics.curriculumunit",
    "academics.timetableperiod",
    "academics.timetableentry",
    "academics.dailylesson",
    "academics.lessonstudentattention",
    "staff.staff",
    "staff.teachingassignment",
    "staff.syllabusplan",
    "staff.syllabusprogressentry",
    "staff.staffcontribution",
    "staff.performancereview",
    "staff.performancegoal",
    "students.student",
    "library.librarybook",
    "library.librarybookcopy",
    "library.librarymember",
    "fatwas.fatwainquiry",
    "fatwas.fatwarequester",
    "fatwas.fatwarevision",
    "fatwas.fatwareference",
    "fatwas.fatwaattachment",
    "fatwas.fatwaworkflowevent",
    "fatwas.fatwapublication",
    "meetings.meeting",
    "meetings.meetingagendaitem",
    "meetings.meetingparticipant",
    "meetings.meetingminutesrevision",
    "meetings.meetingdecision",
    "meetings.meetingactionitem",
    "meetings.meetingattachment",
    "meetings.meetingauditevent",
    "tasks.taskproject",
    "tasks.administrativetask",
    "tasks.taskassignment",
    "tasks.taskchecklistitem",
    "tasks.taskdependency",
    "tasks.taskcomment",
    "tasks.taskattachment",
    "tasks.taskrecurrence",
    "tasks.taskauditevent",
    "documents.document",
    "documents.documentversion",
    "documents.documentaccessgrant",
    "documents.documentlink",
    "documents.documentcomment",
    "documents.documentacknowledgement",
    "documents.documentauditevent",
    "guardians.guardianstudentlink",
    "guardians.guardianinvitation",
    "guardians.guardianconsent",
    "guardians.guardiannotificationpreference",
    "guardians.parentmeetingslot",
    "guardians.parentmeetingbooking",
    "guardians.guardianannouncement",
    "guardians.guardianannouncementread",
    "leaves.leavebalance",
    "leaves.leaverequest",
    "leaves.leaverequestday",
    "leaves.leavesubstitution",
    "leaves.leaveattachment",
    "leaves.leaveauditevent",
    "development.disciplineincident",
    "development.disciplineaction",
    "development.disciplineappeal",
    "development.trainingprogram",
    "development.trainingenrollment",
    "development.rewardnomination",
    "development.alumniengagement",
    "certificates.certificate",
    "certificates.certificateevent",
    "certificates.certificateverificationlog",
    "operations.inventoryitem",
    "operations.stocklot",
    "operations.stocktransaction",
    "operations.purchaseorder",
    "operations.purchaseorderline",
    "operations.asset",
    "operations.assetmaintenance",
    "operations.vehicle",
    "operations.transportroute",
    "operations.routestop",
    "operations.studenttransportassignment",
    "operations.vehiclelog",
    "operations.mealplan",
    "operations.mealingredient",
    "students.admissionapplication",
    "students.admissioninterview",
    "students.admissiontest",
    "students.admissiondecision",
    "students.studentenrollment",
    "students.rollnumberchange",
    "students.studentlifecycleevent",
    "students.promotiondecision",
    "students.graduationrecord",
    "students.alumniprofile",
    "hostel.hostelroom",
    "exams.internalexam",
    "exams.internalexampaper",
    "exams.internalexamresult",
    "exams.examduty",
    "exams.examattendance",
    "exams.examresultchange",
    "exams.annualresult",
    "staff.halaqaassignment",
    "staff.staffattendance",
    "students.studentattendance",
    "students.attendancealertrule",
    "students.attendancealert",
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
    "finance.fundtransfer",
    "finance.budget",
    "finance.budgetline",
    "finance.staffcompensation",
    "finance.payrollrun",
    "finance.payrollitem",
    "library.libraryloan",
    "library.libraryfine",
    "library.libraryreservation",
]

MEDIA_FIELDS = {
    "users.madrasaprofile": ("logo",),
    "staff.staff": ("photo",),
    "students.student": ("photo",),
    "fatwas.fatwaattachment": ("file",),
    "meetings.meetingattachment": ("file",),
    "tasks.taskattachment": ("file",),
    "documents.documentversion": ("file",),
    "leaves.leaveattachment": ("file",),
}


def _model(label):
    from django.apps import apps

    return apps.get_model(label)


def _tenant_queryset(model, tenant):
    field_names = {field.name for field in model._meta.concrete_fields}
    if "madrasa" in field_names:
        return model.objects.filter(madrasa=tenant)
    tenant_paths = {
        "staff.performancemetric": "review__madrasa",
    }
    lookup = tenant_paths.get(model._meta.label_lower)
    if lookup:
        return model.objects.filter(**{lookup: tenant})
    raise ValidationError(f"Backup model {model._meta.label_lower} has no tenant ownership path.")


def _safe_media_path(name):
    root = Path(settings.MEDIA_ROOT).resolve()
    destination = (root / name).resolve()
    if root not in destination.parents and destination != root:
        raise ValidationError("Invalid media path in backup.")
    return destination


def create_backup(tenant, include_media=True):
    """Return a BytesIO ZIP containing a portable tenant-only snapshot."""
    records = []
    media_names = set()

    for label in MODEL_LABELS:
        model = _model(label)
        queryset = _tenant_queryset(model, tenant)
        records.extend(json.loads(serializers.serialize("json", queryset)))
        for field_name in MEDIA_FIELDS.get(label, ()) if include_media else ():
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
