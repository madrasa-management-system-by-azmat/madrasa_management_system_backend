from rest_framework import serializers

from .models import BackupRun, BackupSchedule
from .services import calculate_next_run


class BackupScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackupSchedule
        fields = ["id", "is_active", "frequency", "time_of_day", "weekday", "day_of_month", "timezone", "retention_count", "retention_days", "include_media", "next_run_at", "last_run_at", "last_success_at", "updated_at"]
        read_only_fields = ["id", "next_run_at", "last_run_at", "last_success_at", "updated_at"]

    def validate_weekday(self, value):
        if value > 6:
            raise serializers.ValidationError("Weekday must be between 0 and 6.")
        return value

    def validate_day_of_month(self, value):
        if value < 1 or value > 28:
            raise serializers.ValidationError("Day of month must be between 1 and 28.")
        return value

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        instance.next_run_at = calculate_next_run(instance) if instance.is_active else None
        instance.save(update_fields=["next_run_at"])
        return instance


class BackupRunSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = BackupRun
        fields = ["id", "trigger", "status", "scheduled_for", "started_at", "completed_at", "requested_by_name", "filename", "size_bytes", "sha256", "record_count", "media_count", "error_message", "expires_at", "downloaded_at", "created_at", "is_available"]

    def get_requested_by_name(self, run):
        if not run.requested_by:
            return "System"
        return run.requested_by.get_full_name() or run.requested_by.username

    def get_is_available(self, run):
        from pathlib import Path
        return run.status == BackupRun.Status.COMPLETED and bool(run.storage_path) and Path(run.storage_path).is_file()
