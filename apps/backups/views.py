from pathlib import Path

from django.http import FileResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auditlog.services import audit_event
from apps.users.backup import restore_backup
from apps.users.rbac import user_has_permission
from apps.users.tenancy import current_madrasa

from .models import BackupRun, BackupSchedule
from .serializers import BackupRunSerializer, BackupScheduleSerializer
from .services import create_and_execute_backup


class BackupScheduleAPIView(APIView):
    def get(self, request):
        if not user_has_permission(request.user, "settings.view"):
            return Response({"detail": "Backup schedule permission required."}, status=403)
        schedule, _ = BackupSchedule.objects.get_or_create(madrasa=current_madrasa(request), defaults={"created_by": request.user})
        return Response(BackupScheduleSerializer(schedule).data)

    def put(self, request):
        if not user_has_permission(request.user, "settings.manage"):
            return Response({"detail": "Backup schedule management permission required."}, status=403)
        schedule, _ = BackupSchedule.objects.get_or_create(madrasa=current_madrasa(request), defaults={"created_by": request.user})
        serializer = BackupScheduleSerializer(schedule, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        audit_event(category="backup", action="backup_schedule_updated", madrasa=schedule.madrasa, actor=request.user, entity=schedule, after=serializer.data)
        return Response(serializer.data)


class BackupRunViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BackupRunSerializer

    def get_queryset(self):
        if not user_has_permission(self.request.user, "settings.view"):
            return BackupRun.objects.none()
        return BackupRun.objects.filter(madrasa=current_madrasa(self.request)).select_related("requested_by")

    def list(self, request, *args, **kwargs):
        if not user_has_permission(request.user, "settings.view"):
            return Response({"detail": "Backup history permission required."}, status=403)
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=["post"])
    def run_now(self, request):
        if not user_has_permission(request.user, "settings.backup"):
            return Response({"detail": "Backup execution permission required."}, status=403)
        tenant = current_madrasa(request)
        if BackupRun.objects.filter(madrasa=tenant, status__in=[BackupRun.Status.PENDING, BackupRun.Status.RUNNING]).exists():
            return Response({"detail": "A backup is already pending or running."}, status=409)
        schedule, _ = BackupSchedule.objects.get_or_create(madrasa=tenant, defaults={"created_by": request.user})
        run = create_and_execute_backup(madrasa=tenant, trigger=BackupRun.Trigger.MANUAL, requested_by=request.user, schedule=schedule)
        response_status = status.HTTP_201_CREATED if run.status == BackupRun.Status.COMPLETED else status.HTTP_500_INTERNAL_SERVER_ERROR
        return Response(self.get_serializer(run).data, status=response_status)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        if not user_has_permission(request.user, "settings.backup"):
            return Response({"detail": "Backup download permission required."}, status=403)
        run = self.get_object()
        path = Path(run.storage_path)
        if run.status != BackupRun.Status.COMPLETED or not path.is_file():
            return Response({"detail": "Backup artifact is unavailable."}, status=404)
        run.downloaded_at = timezone.now()
        run.save(update_fields=["downloaded_at"])
        audit_event(category="backup", action="backup_artifact_download", madrasa=run.madrasa, actor=request.user, entity=run)
        return FileResponse(path.open("rb"), as_attachment=True, filename=run.filename, content_type="application/zip")

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        if not user_has_permission(request.user, "settings.restore"):
            return Response({"detail": "Backup restore permission required."}, status=403)
        run = self.get_object()
        path = Path(run.storage_path)
        if run.status != BackupRun.Status.COMPLETED or not path.is_file():
            return Response({"detail": "Backup artifact is unavailable."}, status=404)
        safety = create_and_execute_backup(madrasa=run.madrasa, trigger=BackupRun.Trigger.PRE_RESTORE, requested_by=request.user)
        if safety.status != BackupRun.Status.COMPLETED:
            return Response({"detail": "The pre-restore safety backup failed; restore was cancelled."}, status=409)
        audit_event(category="restore", action="automated_restore_started", madrasa=run.madrasa, actor=request.user, entity=run)
        with path.open("rb") as archive:
            result = restore_backup(archive, run.madrasa)
        audit_event(category="restore", action="automated_restore_succeeded", madrasa=run.madrasa, actor=request.user, entity=run, metadata=result)
        return Response({"detail": "Backup restored successfully.", "safety_backup_id": safety.pk, **result})
