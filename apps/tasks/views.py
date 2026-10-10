from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.users.tenancy import TenantScopedViewSetMixin

from .models import AdministrativeTask, TaskAssignment, TaskAttachment, TaskAuditEvent, TaskCategory, TaskChecklistItem, TaskComment, TaskDependency, TaskProject, TaskRecurrence
from .serializers import AdministrativeTaskDetailSerializer, AdministrativeTaskListSerializer, TaskAssignmentSerializer, TaskAttachmentSerializer, TaskAuditEventSerializer, TaskCategorySerializer, TaskChecklistItemSerializer, TaskCommentSerializer, TaskDependencySerializer, TaskProjectSerializer, TaskRecurrenceSerializer


class TaskBaseViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]


@extend_schema(tags=["Administrative Tasks"])
class TaskCategoryViewSet(TaskBaseViewSet):
    queryset = TaskCategory.objects.all()
    serializer_class = TaskCategorySerializer
    search_fields = ["name", "code"]
    ordering_fields = ["name"]


@extend_schema(tags=["Administrative Tasks"])
class TaskProjectViewSet(TaskBaseViewSet):
    queryset = TaskProject.objects.select_related("owner", "created_by")
    serializer_class = TaskProjectSerializer
    search_fields = ["name", "code", "description", "owner__username", "owner__first_name"]
    ordering_fields = ["status", "starts_on", "due_on", "name"]

    def perform_create(self, serializer):
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(madrasa=self.get_madrasa(), created_by=self.request.user)

    def perform_update(self, serializer):
        project_status = serializer.validated_data.get("status", serializer.instance.status)
        extra = {}
        if project_status == TaskProject.Status.COMPLETED:
            extra["completed_at"] = serializer.instance.completed_at or timezone.now()
        elif serializer.instance.status == TaskProject.Status.COMPLETED:
            extra["completed_at"] = None
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(**extra)


@extend_schema(tags=["Administrative Tasks"])
class AdministrativeTaskViewSet(TaskBaseViewSet):
    queryset = AdministrativeTask.objects.select_related("category", "project", "meeting_action", "parent", "reviewer", "verified_by", "created_by").prefetch_related("assignments__assignee", "checklist_items", "dependencies__depends_on", "comments__created_by", "attachments", "audit_events__actor")
    search_fields = ["task_number", "title", "description", "category__name", "project__name", "assignments__assignee__username", "assignments__assignee__first_name"]
    ordering_fields = ["due_at", "priority", "status", "progress_percentage", "created_at", "updated_at"]

    def get_serializer_class(self):
        return AdministrativeTaskDetailSerializer if self.action in ["retrieve", "create", "update", "partial_update"] else AdministrativeTaskListSerializer

    def get_queryset(self):
        queryset = super().get_queryset().distinct()
        for field in ["status", "priority", "category", "project", "reviewer"]:
            value = self.request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        assignee = self.request.query_params.get("assignee")
        if assignee:
            queryset = queryset.filter(assignments__assignee_id=assignee)
        if self.request.query_params.get("mine") == "true":
            queryset = queryset.filter(Q(assignments__assignee=self.request.user) | Q(reviewer=self.request.user)).distinct()
        if self.request.query_params.get("overdue") == "true":
            queryset = queryset.filter(due_at__lt=timezone.now()).exclude(status__in=[AdministrativeTask.Status.COMPLETED, AdministrativeTask.Status.CANCELLED, AdministrativeTask.Status.ARCHIVED])
        return queryset

    def perform_update(self, serializer):
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        if instance.status != AdministrativeTask.Status.DRAFT:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Only draft tasks can be deleted.")
        super().perform_destroy(instance)

    def _event(self, task, action_name, old_status, comment="", metadata=None):
        TaskAuditEvent.objects.create(madrasa=self.get_madrasa(), task=task, action=action_name, from_status=old_status, to_status=task.status, actor=self.request.user, comment=comment, metadata=metadata or {})

    def _transition(self, task, allowed, target, action_name, comment="", fields=None):
        if task.status not in allowed:
            return Response({"detail": "This workflow action is not allowed in the current state."}, status=status.HTTP_400_BAD_REQUEST)
        old = task.status
        task.status = target
        task.updated_by = self.request.user
        update_fields = ["status", "updated_by", "updated_at"]
        for key, value in (fields or {}).items():
            setattr(task, key, value)
            update_fields.append(key)
        task.save(update_fields=update_fields)
        self._event(task, action_name, old, comment)
        return Response(AdministrativeTaskDetailSerializer(task, context={"request": self.request}).data)

    @action(detail=False, methods=["get"])
    def people_lookup(self, request):
        from apps.users.models import UserProfile
        profiles = UserProfile.objects.filter(madrasa=self.get_madrasa(), user__is_active=True).select_related("user")
        return Response([{"id": item.user_id, "name": item.user.get_full_name() or item.user.username, "role": item.role} for item in profiles])

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        task = self.get_object()
        if task.status not in [AdministrativeTask.Status.DRAFT, AdministrativeTask.Status.ASSIGNED]:
            return Response({"detail": "Assignments can only be changed before work starts."}, status=status.HTTP_400_BAD_REQUEST)
        from django.contrib.auth import get_user_model
        ids = request.data.get("assignees", [])
        if not isinstance(ids, list) or not ids:
            return Response({"assignees": ["Select at least one assignee."]}, status=status.HTTP_400_BAD_REQUEST)
        users = list(get_user_model().objects.filter(pk__in=ids, profile__madrasa=self.get_madrasa(), is_active=True))
        if len(users) != len(set(ids)):
            return Response({"assignees": ["One or more assignees are invalid."]}, status=status.HTTP_400_BAD_REQUEST)
        task.assignments.all().delete()
        for index, user in enumerate(users):
            TaskAssignment.objects.create(madrasa=self.get_madrasa(), task=task, assignee=user, role=TaskAssignment.Role.OWNER if index == 0 else TaskAssignment.Role.COLLABORATOR, assigned_by=request.user)
        if task.status == AdministrativeTask.Status.DRAFT:
            return self._transition(task, [AdministrativeTask.Status.DRAFT], AdministrativeTask.Status.ASSIGNED, "assigned", request.data.get("comment", ""), {"starts_on": task.starts_on or timezone.localdate()})
        self._event(task, "reassigned", task.status, request.data.get("comment", ""), {"assignees": ids})
        return Response(AdministrativeTaskDetailSerializer(task, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        task = self.get_object()
        if request.user.profile.role != "admin" and not task.assignments.filter(assignee=request.user).exists():
            return Response({"detail": "Only an assignee can start this task."}, status=status.HTTP_403_FORBIDDEN)
        blocked = task.dependencies.exclude(depends_on__status=AdministrativeTask.Status.COMPLETED).exists()
        if blocked:
            return Response({"detail": "Complete task dependencies first."}, status=status.HTTP_400_BAD_REQUEST)
        return self._transition(task, [AdministrativeTask.Status.ASSIGNED, AdministrativeTask.Status.CHANGES_REQUESTED, AdministrativeTask.Status.BLOCKED], AdministrativeTask.Status.IN_PROGRESS, "started", request.data.get("comment", ""), {"starts_on": task.starts_on or timezone.localdate()})

    @action(detail=True, methods=["post"])
    def block(self, request, pk=None):
        task = self.get_object()
        comment = str(request.data.get("comment", "")).strip()
        if not comment:
            return Response({"comment": ["Blocking reason is required."]}, status=status.HTTP_400_BAD_REQUEST)
        return self._transition(task, [AdministrativeTask.Status.ASSIGNED, AdministrativeTask.Status.IN_PROGRESS], AdministrativeTask.Status.BLOCKED, "blocked", comment)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        task = self.get_object()
        if request.user.profile.role != "admin" and not task.assignments.filter(assignee=request.user).exists():
            return Response({"detail": "Only an assignee can submit this task."}, status=status.HTTP_403_FORBIDDEN)
        if task.checklist_items.filter(is_completed=False).exists():
            return Response({"detail": "Complete every checklist item first."}, status=status.HTTP_400_BAD_REQUEST)
        if task.requires_review:
            if not task.reviewer_id:
                return Response({"detail": "Assign a reviewer first."}, status=status.HTTP_400_BAD_REQUEST)
            return self._transition(task, [AdministrativeTask.Status.IN_PROGRESS], AdministrativeTask.Status.PENDING_REVIEW, "submitted_for_review", request.data.get("comment", ""), {"progress_percentage": 100, "completion_notes": request.data.get("completion_notes", task.completion_notes)})
        return self._transition(task, [AdministrativeTask.Status.IN_PROGRESS], AdministrativeTask.Status.COMPLETED, "completed", request.data.get("comment", ""), {"progress_percentage": 100, "completion_notes": request.data.get("completion_notes", task.completion_notes), "completed_at": timezone.now(), "verified_at": timezone.now(), "verified_by": request.user})

    @action(detail=True, methods=["post"])
    def request_changes(self, request, pk=None):
        task = self.get_object()
        if request.user.profile.role != "admin" and task.reviewer_id != request.user.id:
            return Response({"detail": "Only the assigned reviewer can request changes."}, status=status.HTTP_403_FORBIDDEN)
        comment = str(request.data.get("comment", "")).strip()
        if not comment:
            return Response({"comment": ["A reason is required."]}, status=status.HTTP_400_BAD_REQUEST)
        return self._transition(task, [AdministrativeTask.Status.PENDING_REVIEW], AdministrativeTask.Status.CHANGES_REQUESTED, "changes_requested", comment, {"progress_percentage": 90})

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        task = self.get_object()
        if request.user.profile.role != "admin" and task.reviewer_id != request.user.id:
            return Response({"detail": "Only the assigned reviewer can verify this task."}, status=status.HTTP_403_FORBIDDEN)
        return self._transition(task, [AdministrativeTask.Status.PENDING_REVIEW], AdministrativeTask.Status.COMPLETED, "verified", request.data.get("comment", ""), {"progress_percentage": 100, "completed_at": timezone.now(), "verified_at": timezone.now(), "verified_by": request.user})

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        task = self.get_object()
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            return Response({"reason": ["Cancellation reason is required."]}, status=status.HTTP_400_BAD_REQUEST)
        return self._transition(task, [AdministrativeTask.Status.DRAFT, AdministrativeTask.Status.ASSIGNED, AdministrativeTask.Status.IN_PROGRESS, AdministrativeTask.Status.BLOCKED], AdministrativeTask.Status.CANCELLED, "cancelled", reason, {"cancellation_reason": reason})

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        if request.user.profile.role != "admin":
            return Response({"detail": "Only administrators can archive tasks."}, status=status.HTTP_403_FORBIDDEN)
        return self._transition(self.get_object(), [AdministrativeTask.Status.COMPLETED, AdministrativeTask.Status.CANCELLED], AdministrativeTask.Status.ARCHIVED, "archived", request.data.get("comment", ""))

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def generate_recurring(self, request):
        today = timezone.localdate()
        recurrences = TaskRecurrence.objects.select_for_update().filter(madrasa=self.get_madrasa(), is_active=True, next_run_on__lte=today).select_related("template_task")
        generated = []
        for recurrence in recurrences:
            template = recurrence.template_task
            if recurrence.ends_on and recurrence.next_run_on > recurrence.ends_on:
                recurrence.is_active = False
                recurrence.save(update_fields=["is_active"])
                continue
            year, number, task_number = AdministrativeTask.issue_number(self.get_madrasa(), recurrence.next_run_on.year)
            task = AdministrativeTask.objects.create(madrasa=self.get_madrasa(), task_number=task_number, sequence_year=year, sequence_number=number, title=template.title, description=template.description, category=template.category, project=template.project, priority=template.priority, visibility=template.visibility, starts_on=recurrence.next_run_on, due_at=timezone.make_aware(timezone.datetime.combine(recurrence.next_run_on, timezone.datetime.max.time())), estimated_hours=template.estimated_hours, requires_review=template.requires_review, reviewer=template.reviewer, status=AdministrativeTask.Status.ASSIGNED if template.assignments.exists() else AdministrativeTask.Status.DRAFT, created_by=request.user, updated_by=request.user)
            for assignment in template.assignments.all():
                TaskAssignment.objects.create(madrasa=self.get_madrasa(), task=task, assignee=assignment.assignee, role=assignment.role, assigned_by=request.user)
            for checklist in template.checklist_items.all():
                TaskChecklistItem.objects.create(madrasa=self.get_madrasa(), task=task, sequence=checklist.sequence, title=checklist.title)
            generated.append(task)
            if recurrence.frequency == TaskRecurrence.Frequency.DAILY:
                recurrence.next_run_on += timedelta(days=recurrence.interval)
            elif recurrence.frequency == TaskRecurrence.Frequency.WEEKLY:
                recurrence.next_run_on += timedelta(weeks=recurrence.interval)
            elif recurrence.frequency == TaskRecurrence.Frequency.MONTHLY:
                recurrence.next_run_on += timedelta(days=30 * recurrence.interval)
            else:
                recurrence.next_run_on = recurrence.next_run_on.replace(year=recurrence.next_run_on.year + recurrence.interval)
            recurrence.save(update_fields=["next_run_on"])
        return Response(AdministrativeTaskListSerializer(generated, many=True, context={"request": request}).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Administrative Tasks"])
class TaskAssignmentViewSet(TaskBaseViewSet):
    queryset = TaskAssignment.objects.select_related("task", "assignee", "assigned_by")
    serializer_class = TaskAssignmentSerializer

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        assignment = self.get_object()
        if assignment.assignee_id != request.user.id:
            return Response({"detail": "Only the assigned user can accept this assignment."}, status=status.HTTP_403_FORBIDDEN)
        assignment.accepted_at = timezone.now()
        assignment.save(update_fields=["accepted_at"])
        return Response(self.get_serializer(assignment).data)


@extend_schema(tags=["Administrative Tasks"])
class TaskChecklistItemViewSet(TaskBaseViewSet):
    queryset = TaskChecklistItem.objects.select_related("task", "completed_by")
    serializer_class = TaskChecklistItemSerializer
    ordering_fields = ["sequence", "is_completed"]

    def perform_create(self, serializer):
        task = serializer.validated_data["task"]
        if task.status in [AdministrativeTask.Status.COMPLETED, AdministrativeTask.Status.CANCELLED, AdministrativeTask.Status.ARCHIVED]:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Closed task checklists are locked.")
        super().perform_create(serializer)

    def perform_update(self, serializer):
        if serializer.instance.task.status in [AdministrativeTask.Status.COMPLETED, AdministrativeTask.Status.CANCELLED, AdministrativeTask.Status.ARCHIVED]:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Closed task checklists are locked.")
        completed = serializer.validated_data.get("is_completed", serializer.instance.is_completed)
        extras = {"completed_by": self.request.user, "completed_at": timezone.now()} if completed else {"completed_by": None, "completed_at": None}
        serializer.save(**extras)
        task = serializer.instance.task
        total = task.checklist_items.count()
        if total:
            task.progress_percentage = round(task.checklist_items.filter(is_completed=True).count() / total * 100)
            task.save(update_fields=["progress_percentage", "updated_at"])


@extend_schema(tags=["Administrative Tasks"])
class TaskDependencyViewSet(TaskBaseViewSet):
    queryset = TaskDependency.objects.select_related("task", "depends_on")
    serializer_class = TaskDependencySerializer

    def perform_create(self, serializer):
        if serializer.validated_data["task"].status not in [AdministrativeTask.Status.DRAFT, AdministrativeTask.Status.ASSIGNED]:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Dependencies can only be added before work starts.")
        super().perform_create(serializer)


@extend_schema(tags=["Administrative Tasks"])
class TaskCommentViewSet(TaskBaseViewSet):
    queryset = TaskComment.objects.select_related("task", "created_by")
    serializer_class = TaskCommentSerializer
    search_fields = ["task__task_number", "task__title", "body"]

    def perform_create(self, serializer):
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(madrasa=self.get_madrasa(), created_by=self.request.user)


@extend_schema(tags=["Administrative Tasks"])
class TaskAttachmentViewSet(TaskBaseViewSet):
    queryset = TaskAttachment.objects.select_related("task", "uploaded_by")
    serializer_class = TaskAttachmentSerializer

    def perform_create(self, serializer):
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        upload = serializer.validated_data["file"]
        serializer.save(madrasa=self.get_madrasa(), original_name=upload.name, uploaded_by=self.request.user)


@extend_schema(tags=["Administrative Tasks"])
class TaskRecurrenceViewSet(TaskBaseViewSet):
    queryset = TaskRecurrence.objects.select_related("template_task")
    serializer_class = TaskRecurrenceSerializer


class TaskDashboardViewSet(TenantScopedViewSetMixin, viewsets.ViewSet):
    queryset = AdministrativeTask.objects.none()

    def list(self, request):
        tenant = self.get_madrasa()
        tasks = AdministrativeTask.objects.filter(madrasa=tenant)
        active = tasks.exclude(status__in=[AdministrativeTask.Status.COMPLETED, AdministrativeTask.Status.CANCELLED, AdministrativeTask.Status.ARCHIVED])
        projects = TaskProject.objects.filter(madrasa=tenant)
        return Response({
            "total": tasks.count(),
            "open": active.count(),
            "mine": active.filter(assignments__assignee=request.user).distinct().count(),
            "in_progress": tasks.filter(status=AdministrativeTask.Status.IN_PROGRESS).count(),
            "pending_review": tasks.filter(status=AdministrativeTask.Status.PENDING_REVIEW).count(),
            "overdue": active.filter(due_at__lt=timezone.now()).count(),
            "completed": tasks.filter(status=AdministrativeTask.Status.COMPLETED).count(),
            "completion_rate": round(tasks.filter(status=AdministrativeTask.Status.COMPLETED).count() / tasks.count() * 100, 1) if tasks.exists() else 0,
            "active_projects": projects.filter(status=TaskProject.Status.ACTIVE).count(),
            "by_status": list(tasks.values("status").annotate(count=Count("id")).order_by("status")),
            "recent": AdministrativeTaskListSerializer(tasks[:10], many=True, context={"request": request}).data,
            "my_tasks": AdministrativeTaskListSerializer(active.filter(assignments__assignee=request.user).distinct()[:10], many=True, context={"request": request}).data,
        })
