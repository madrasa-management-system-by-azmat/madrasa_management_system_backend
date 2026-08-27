from rest_framework import serializers

from .models import HalaqaAssignment, Staff, StaffAttendance


class StaffSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Staff
        fields = [
            "id", "user", "user_username", "full_name", "photo", "cnic", "phone", "role",
            "hire_date", "is_residential", "is_active",
        ]


class StaffAttendanceSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="staff.full_name", read_only=True)

    class Meta:
        model = StaffAttendance
        fields = ["id", "staff", "staff_name", "date", "status"]


class HalaqaAssignmentSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="staff.full_name", read_only=True)
    halaqa_name = serializers.CharField(source="halaqa.name", read_only=True)

    class Meta:
        model = HalaqaAssignment
        fields = ["id", "staff", "staff_name", "halaqa", "halaqa_name", "assigned_on", "is_active"]
        read_only_fields = ["assigned_on"]
