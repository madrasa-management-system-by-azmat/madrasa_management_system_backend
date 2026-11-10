from rest_framework import serializers

from .models import DutyAssignment, DutyCategory, GuestInvitation, Taqreeb


class DutyCategorySerializer(serializers.ModelSerializer):
    duties_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = DutyCategory
        fields = [
            "id",
            "name",
            "code",
            "description",
            "color",
            "sort_order",
            "is_active",
            "duties_count",
        ]


class TaqreebListSerializer(serializers.ModelSerializer):
    duties_count = serializers.IntegerField(read_only=True, default=0)
    invitations_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Taqreeb
        fields = [
            "id",
            "title",
            "event_type",
            "status",
            "event_date",
            "hijri_date",
            "start_time",
            "end_time",
            "venue",
            "chief_guest",
            "president",
            "budget",
            "duties_count",
            "invitations_count",
            "created_at",
            "updated_at",
        ]


class TaqreebDetailSerializer(serializers.ModelSerializer):
    duties_count = serializers.IntegerField(read_only=True, default=0)
    invitations_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Taqreeb
        fields = [
            "id",
            "title",
            "event_type",
            "status",
            "event_date",
            "hijri_date",
            "start_time",
            "end_time",
            "venue",
            "chief_guest",
            "president",
            "description",
            "budget",
            "duties_count",
            "invitations_count",
            "created_at",
            "updated_at",
        ]


class DutyAssignmentSerializer(serializers.ModelSerializer):
    assignee_name = serializers.SerializerMethodField()
    assignee_role_or_class = serializers.SerializerMethodField()
    assignee_photo = serializers.SerializerMethodField()
    assignee_phone = serializers.SerializerMethodField()
    category_name = serializers.CharField(source="duty_category.name", read_only=True)
    category_color = serializers.CharField(source="duty_category.color", read_only=True)
    taqreeb_title = serializers.CharField(source="taqreeb.title", read_only=True)
    taqreeb_date = serializers.DateField(source="taqreeb.event_date", read_only=True)
    taqreeb_venue = serializers.CharField(source="taqreeb.venue", read_only=True)

    class Meta:
        model = DutyAssignment
        fields = [
            "id",
            "taqreeb",
            "taqreeb_title",
            "taqreeb_date",
            "taqreeb_venue",
            "duty_category",
            "category_name",
            "category_color",
            "duty_title",
            "assignee_type",
            "student",
            "staff",
            "assignee_name",
            "assignee_role_or_class",
            "assignee_photo",
            "assignee_phone",
            "card_number",
            "location",
            "reporting_time",
            "instructions",
            "status",
            "created_at",
            "updated_at",
        ]

    def get_assignee_name(self, obj):
        if obj.assignee_type == DutyAssignment.AssigneeType.STUDENT and obj.student:
            return getattr(obj.student, "full_name", "—")
        if obj.assignee_type == DutyAssignment.AssigneeType.TEACHER and obj.staff:
            return getattr(obj.staff, "full_name", "—")
        return "—"

    def get_assignee_role_or_class(self, obj):
        if obj.assignee_type == DutyAssignment.AssigneeType.STUDENT and obj.student:
            enrollment = obj.student.enrollments.filter(status="active").first() if hasattr(obj.student, "enrollments") else None
            if enrollment and enrollment.academic_class:
                return enrollment.academic_class.name
            return "طالب علم"
        if obj.assignee_type == DutyAssignment.AssigneeType.TEACHER and obj.staff:
            if hasattr(obj.staff, "get_role_display"):
                return obj.staff.get_role_display()
            return getattr(obj.staff, "role", "استاد / عملہ")
        return "—"

    def get_assignee_photo(self, obj):
        request = self.context.get("request")
        photo_field = None
        if obj.assignee_type == DutyAssignment.AssigneeType.STUDENT and obj.student:
            photo_field = getattr(obj.student, "photo", None)
        elif obj.assignee_type == DutyAssignment.AssigneeType.TEACHER and obj.staff:
            photo_field = getattr(obj.staff, "photo", None)

        if photo_field:
            try:
                url = photo_field.url
                return request.build_absolute_uri(url) if request else url
            except Exception:
                return None
        return None

    def get_assignee_phone(self, obj):
        if obj.assignee_type == DutyAssignment.AssigneeType.STUDENT and obj.student:
            return getattr(obj.student, "phone", "") or getattr(obj.student, "guardian_phone", "") or ""
        if obj.assignee_type == DutyAssignment.AssigneeType.TEACHER and obj.staff:
            return getattr(obj.staff, "phone", "") or ""
        return ""

    def validate(self, attrs):
        taqreeb = attrs.get("taqreeb", getattr(self.instance, "taqreeb", None))
        assignee_type = attrs.get("assignee_type", getattr(self.instance, "assignee_type", None))
        student = attrs.get("student", getattr(self.instance, "student", None))
        staff = attrs.get("staff", getattr(self.instance, "staff", None))

        if assignee_type == DutyAssignment.AssigneeType.STUDENT:
            if not student:
                raise serializers.ValidationError({"student": "طالب علم کا انتخاب لازمی ہے۔"})
            qs = DutyAssignment.objects.filter(taqreeb=taqreeb, student=student)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            existing = qs.first()
            if existing:
                student_name = getattr(student, "full_name", str(student))
                raise serializers.ValidationError({
                    "student": f"اس طالب علم ({student_name}) کو پہلے ہی اس تقریب میں ڈیوٹی '{existing.duty_title}' تفویض کی جا چکی ہے۔ ایک فرد کو صرف ایک ڈیوٹی دی جا سکتی ہے۔"
                })

        elif assignee_type == DutyAssignment.AssigneeType.TEACHER:
            if not staff:
                raise serializers.ValidationError({"staff": "استاد / عملہ کا انتخاب لازمی ہے۔"})
            qs = DutyAssignment.objects.filter(taqreeb=taqreeb, staff=staff)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            existing = qs.first()
            if existing:
                staff_name = getattr(staff, "full_name", str(staff))
                raise serializers.ValidationError({
                    "staff": f"اس استاد / ملازم ({staff_name}) کو پہلے ہی اس تقریب میں ڈیوٹی '{existing.duty_title}' تفویض کی جا چکی ہے۔ ایک فرد کو صرف ایک ڈیوٹی دی جا سکتی ہے۔"
                })

        return attrs


class GuestInvitationSerializer(serializers.ModelSerializer):
    taqreeb_title = serializers.CharField(source="taqreeb.title", read_only=True)
    taqreeb_date = serializers.DateField(source="taqreeb.event_date", read_only=True)
    taqreeb_hijri_date = serializers.CharField(source="taqreeb.hijri_date", read_only=True)
    taqreeb_start_time = serializers.TimeField(source="taqreeb.start_time", read_only=True)
    taqreeb_venue = serializers.CharField(source="taqreeb.venue", read_only=True)
    taqreeb_chief_guest = serializers.CharField(source="taqreeb.chief_guest", read_only=True)
    taqreeb_president = serializers.CharField(source="taqreeb.president", read_only=True)

    class Meta:
        model = GuestInvitation
        fields = [
            "id",
            "taqreeb",
            "taqreeb_title",
            "taqreeb_date",
            "taqreeb_hijri_date",
            "taqreeb_start_time",
            "taqreeb_venue",
            "taqreeb_chief_guest",
            "taqreeb_president",
            "guest_name",
            "designation",
            "organization",
            "phone",
            "city",
            "invitation_number",
            "seat_number",
            "is_special_guest",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]

