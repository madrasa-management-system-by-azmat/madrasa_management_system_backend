from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import AdministrativeTask, TaskAssignment, TaskAttachment, TaskAuditEvent, TaskCategory, TaskChecklistItem, TaskComment, TaskDependency, TaskProject, TaskRecurrence


class TaskCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskCategory
        fields = ["id", "name", "code", "description", "color_key", "is_active"]


class TaskProjectSerializer(serializers.ModelSerializer):
    owner_name = serializers.SerializerMethodField()
    task_count = serializers.IntegerField(source="tasks.count", read_only=True)

    class Meta:
        model = TaskProject
        fields = ["id", "name", "code", "description", "owner", "owner_name", "status", "starts_on", "due_on", "completed_at", "created_by", "created_at", "task_count"]
        read_only_fields = ["completed_at", "created_by", "created_at"]

    def get_owner_name(self, project):
        return project.owner.get_full_name() or project.owner.username

    def validate(self, attrs):
        attrs = super().validate(attrs)
        starts = attrs.get("starts_on", getattr(self.instance, "starts_on", None))
        due = attrs.get("due_on", getattr(self.instance, "due_on", None))
        if starts and due and due < starts:
            raise serializers.ValidationError({"due_on": "Project due date cannot precede start date."})
        return attrs


class TaskAssignmentSerializer(serializers.ModelSerializer):
    assignee_name = serializers.SerializerMethodField()

    class Meta:
        model = TaskAssignment
        fields = ["id", "task", "assignee", "assignee_name", "role", "assigned_by", "assigned_at", "accepted_at"]
        read_only_fields = ["assigned_by", "assigned_at", "accepted_at"]

    def get_assignee_name(self, assignment):
        return assignment.assignee.get_full_name() or assignment.assignee.username


class TaskChecklistItemSerializer(serializers.ModelSerializer):
    completed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TaskChecklistItem
        fields = ["id", "task", "sequence", "title", "is_completed", "completed_by", "completed_by_name", "completed_at"]
        read_only_fields = ["completed_by", "completed_at"]

    def get_completed_by_name(self, item):
        return (item.completed_by.get_full_name() or item.completed_by.username) if item.completed_by else ""


class TaskDependencySerializer(serializers.ModelSerializer):
    depends_on_title = serializers.CharField(source="depends_on.title", read_only=True)
    depends_on_status = serializers.CharField(source="depends_on.status", read_only=True)

    class Meta:
        model = TaskDependency
        fields = ["id", "task", "depends_on", "depends_on_title", "depends_on_status"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        task = attrs.get("task")
        depends_on = attrs.get("depends_on")
        if task and depends_on and task.madrasa_id != depends_on.madrasa_id:
            raise serializers.ValidationError("Dependent tasks must belong to the same madrasa.")
        if task and depends_on and depends_on.dependencies.filter(depends_on=task).exists():
            raise serializers.ValidationError("This dependency would create a direct cycle.")
        return attrs


class TaskCommentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TaskComment
        fields = ["id", "task", "body", "is_internal", "created_by", "created_by_name", "created_at"]
        read_only_fields = ["created_by", "created_at"]

    def get_created_by_name(self, comment):
        return (comment.created_by.get_full_name() or comment.created_by.username) if comment.created_by else "سسٹم"


class TaskAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskAttachment
        fields = ["id", "task", "file", "original_name", "description", "uploaded_by", "uploaded_at"]
        read_only_fields = ["original_name", "uploaded_by", "uploaded_at"]

    def validate_file(self, upload):
        if upload.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Attachment size cannot exceed 10 MB.")
        return upload


class TaskRecurrenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskRecurrence
        fields = ["id", "template_task", "frequency", "interval", "next_run_on", "ends_on", "is_active"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get("interval", getattr(self.instance, "interval", 1)) < 1:
            raise serializers.ValidationError({"interval": "Interval must be at least one."})
        if attrs.get("ends_on") and attrs["ends_on"] < attrs.get("next_run_on", getattr(self.instance, "next_run_on", attrs["ends_on"])):
            raise serializers.ValidationError({"ends_on": "End date cannot precede the next run date."})
        return attrs


class TaskAuditEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = TaskAuditEvent
        fields = ["id", "task", "action", "from_status", "to_status", "actor", "actor_name", "comment", "metadata", "created_at"]
        read_only_fields = fields

    def get_actor_name(self, event):
        return (event.actor.get_full_name() or event.actor.username) if event.actor else "سسٹم"


class AdministrativeTaskListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    assignee_names = serializers.SerializerMethodField()
    checklist_total = serializers.IntegerField(source="checklist_items.count", read_only=True)
    checklist_completed = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = AdministrativeTask
        fields = ["id", "task_number", "title", "description", "category", "category_name", "project", "project_name", "meeting_action", "parent", "status", "priority", "visibility", "starts_on", "due_at", "estimated_hours", "progress_percentage", "requires_review", "reviewer", "assignee_names", "checklist_total", "checklist_completed", "is_overdue", "completed_at", "verified_at", "created_at", "updated_at"]

    def get_assignee_names(self, task):
        return [assignment.assignee.get_full_name() or assignment.assignee.username for assignment in task.assignments.all()]

    def get_checklist_completed(self, task):
        return task.checklist_items.filter(is_completed=True).count()

    def get_is_overdue(self, task):
        return bool(task.due_at and task.due_at < timezone.now() and task.status not in [AdministrativeTask.Status.COMPLETED, AdministrativeTask.Status.CANCELLED, AdministrativeTask.Status.ARCHIVED])


class AdministrativeTaskDetailSerializer(AdministrativeTaskListSerializer):
    assignments = TaskAssignmentSerializer(many=True, read_only=True)
    checklist_items = TaskChecklistItemSerializer(many=True, read_only=True)
    dependencies = TaskDependencySerializer(many=True, read_only=True)
    comments = TaskCommentSerializer(many=True, read_only=True)
    attachments = TaskAttachmentSerializer(many=True, read_only=True)
    recurrence = TaskRecurrenceSerializer(read_only=True)
    audit_events = TaskAuditEventSerializer(many=True, read_only=True)

    class Meta(AdministrativeTaskListSerializer.Meta):
        fields = AdministrativeTaskListSerializer.Meta.fields + ["assignments", "checklist_items", "dependencies", "comments", "attachments", "recurrence", "audit_events", "completion_notes", "verified_by", "cancellation_reason", "created_by", "updated_by"]
        read_only_fields = ["task_number", "status", "progress_percentage", "completed_at", "verified_at", "verified_by", "created_by", "updated_by"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance and self.instance.status in [AdministrativeTask.Status.COMPLETED, AdministrativeTask.Status.CANCELLED, AdministrativeTask.Status.ARCHIVED]:
            raise serializers.ValidationError("Completed, cancelled, or archived tasks are locked.")
        tenant = self.context["request"].user.profile.madrasa
        for related in [attrs.get("category"), attrs.get("project"), attrs.get("parent"), attrs.get("meeting_action")]:
            if related and related.madrasa_id != tenant.id:
                raise serializers.ValidationError("Related records must belong to the active madrasa.")
        reviewer = attrs.get("reviewer")
        if reviewer and getattr(getattr(reviewer, "profile", None), "madrasa_id", None) != tenant.id:
            raise serializers.ValidationError({"reviewer": "Reviewer must belong to the active madrasa."})
        if attrs.get("parent") and self.instance and attrs["parent"].id == self.instance.id:
            raise serializers.ValidationError({"parent": "A task cannot be its own parent."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        tenant = validated_data.pop("madrasa", self.context["request"].user.profile.madrasa)
        year, number, task_number = AdministrativeTask.issue_number(tenant)
        return AdministrativeTask.objects.create(madrasa=tenant, sequence_year=year, sequence_number=number, task_number=task_number, created_by=self.context["request"].user, updated_by=self.context["request"].user, **validated_data)
