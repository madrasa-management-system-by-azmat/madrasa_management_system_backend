from rest_framework import serializers

from .models import HifzDailyLog


class HifzDailyLogSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    verified_by_name = serializers.CharField(source="verified_by.full_name", read_only=True)

    class Meta:
        model = HifzDailyLog
        fields = [
            "id", "student", "student_name", "date", "sabaq_portion", "sabaqi_portion",
            "manzil_portion", "verified_by", "verified_by_name",
        ]
