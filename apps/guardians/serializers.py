import re

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import GuardianAnnouncement, GuardianProfile, GuardianStudentLink, ParentMeetingBooking, ParentMeetingSlot

User = get_user_model()


def normalize_phone(value):
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("0092"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = "92" + digits[1:]
    return digits


class GuardianStudentLinkSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    registration_number = serializers.CharField(source="student.registration_number", read_only=True)
    class_name = serializers.CharField(source="student.current_class.name", read_only=True)

    class Meta:
        model = GuardianStudentLink
        fields = ["id", "guardian", "student", "student_name", "registration_number", "class_name", "relationship", "is_primary", "is_legal_guardian", "pickup_authorized", "portal_access_enabled", "starts_on", "ends_on", "verified_by", "verified_at", "revoked_at"]
        read_only_fields = ["verified_by", "verified_at", "revoked_at"]


class GuardianProfileSerializer(serializers.ModelSerializer):
    students = GuardianStudentLinkSerializer(source="student_links", many=True, read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = GuardianProfile
        fields = ["id", "user", "username", "full_name", "phone", "email", "cnic_last_four", "preferred_language", "status", "phone_verified_at", "email_verified_at", "students", "created_at", "updated_at"]
        read_only_fields = ["user", "status", "phone_verified_at", "email_verified_at", "created_at", "updated_at"]


class CreateGuardianSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=30)
    email = serializers.EmailField(required=False, allow_blank=True)
    student_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    relationship = serializers.CharField(max_length=100, default="سرپرست")
    is_primary = serializers.BooleanField(default=True)

    def validate(self, attrs):
        from apps.students.models import Student
        tenant = self.context["request"].user.profile.madrasa
        attrs["normalized_phone"] = normalize_phone(attrs["phone"])
        if len(attrs["normalized_phone"]) < 10:
            raise serializers.ValidationError({"phone": "Enter a valid phone number."})
        students = list(Student.objects.filter(madrasa=tenant, pk__in=attrs["student_ids"]))
        if len(students) != len(set(attrs["student_ids"])):
            raise serializers.ValidationError({"student_ids": "One or more students are invalid."})
        attrs["students"] = students
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        from apps.users.models import UserProfile
        tenant = self.context["request"].user.profile.madrasa
        students = validated_data.pop("students")
        validated_data.pop("student_ids")
        relationship = validated_data.pop("relationship")
        is_primary = validated_data.pop("is_primary")
        normalized_phone = validated_data.pop("normalized_phone")
        guardian = GuardianProfile.objects.filter(madrasa=tenant, normalized_phone=normalized_phone).select_related("user").first()
        if not guardian:
            base_username = f"parent_{tenant.id}_{normalized_phone[-10:]}"
            username = base_username
            counter = 2
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1
            user = User.objects.create_user(username=username, email=validated_data.get("email", ""), first_name=validated_data["full_name"], is_active=False)
            UserProfile.objects.create(user=user, madrasa=tenant, role=UserProfile.Role.GUARDIAN, phone=validated_data["phone"])
            guardian = GuardianProfile.objects.create(madrasa=tenant, user=user, normalized_phone=normalized_phone, **validated_data)
        for student in students:
            GuardianStudentLink.objects.update_or_create(madrasa=tenant, guardian=guardian, student=student, defaults={"relationship": relationship, "is_primary": is_primary, "portal_access_enabled": True, "verified_by": self.context["request"].user, "verified_at": timezone.now()})
        return guardian


class ParentMeetingSlotSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True)
    class_name = serializers.CharField(source="academic_class.name", read_only=True)
    booked_count = serializers.IntegerField(source="bookings.count", read_only=True)
    available = serializers.SerializerMethodField()

    class Meta:
        model = ParentMeetingSlot
        fields = ["id", "teacher", "teacher_name", "academic_class", "class_name", "starts_at", "ends_at", "venue", "online_url", "capacity", "status", "notes", "created_by", "created_at", "booked_count", "available"]
        read_only_fields = ["created_by", "created_at"]

    def get_available(self, slot):
        return slot.status == ParentMeetingSlot.Status.OPEN and slot.bookings.exclude(status=ParentMeetingBooking.Status.CANCELLED).count() < slot.capacity

    def validate(self, attrs):
        attrs = super().validate(attrs)
        start = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        end = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"ends_at": "Meeting end must be later than start."})
        return attrs


class ParentMeetingBookingSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="slot.teacher.full_name", read_only=True)
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    guardian_name = serializers.CharField(source="guardian.full_name", read_only=True)
    starts_at = serializers.DateTimeField(source="slot.starts_at", read_only=True)
    ends_at = serializers.DateTimeField(source="slot.ends_at", read_only=True)
    venue = serializers.CharField(source="slot.venue", read_only=True)

    class Meta:
        model = ParentMeetingBooking
        fields = ["id", "slot", "teacher_name", "guardian", "guardian_name", "student", "student_name", "starts_at", "ends_at", "venue", "status", "agenda", "guardian_notes", "teacher_notes", "follow_up", "follow_up_due", "booked_at", "completed_at", "cancelled_at", "cancellation_reason"]
        read_only_fields = ["guardian", "status", "teacher_notes", "follow_up", "follow_up_due", "booked_at", "completed_at", "cancelled_at", "cancellation_reason"]


class GuardianAnnouncementSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = GuardianAnnouncement
        fields = ["id", "title", "body", "audience", "academic_class", "student", "published_at", "expires_at", "is_read"]

    def get_is_read(self, announcement):
        guardian = self.context.get("guardian")
        return bool(guardian and announcement.reads.filter(guardian=guardian).exists())
