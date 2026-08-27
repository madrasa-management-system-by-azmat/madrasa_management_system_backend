from rest_framework import serializers

from .models import GatePass, HostelAllocation, HostelRoom, HostelWing


class HostelWingSerializer(serializers.ModelSerializer):
    class Meta:
        model = HostelWing
        fields = ["id", "name"]


class HostelRoomSerializer(serializers.ModelSerializer):
    wing_name = serializers.CharField(source="wing.name", read_only=True)

    class Meta:
        model = HostelRoom
        fields = ["id", "wing", "wing_name", "room_number", "capacity"]


class HostelAllocationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    room_number = serializers.CharField(source="room.room_number", read_only=True)

    class Meta:
        model = HostelAllocation
        fields = ["id", "student", "student_name", "room", "room_number", "bed_number", "allocated_date", "is_active"]


class GatePassSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    authorized_by_name = serializers.CharField(source="authorized_by.full_name", read_only=True)

    class Meta:
        model = GatePass
        fields = ["id", "student", "student_name", "purpose", "out_date", "in_date", "authorized_by", "authorized_by_name"]
