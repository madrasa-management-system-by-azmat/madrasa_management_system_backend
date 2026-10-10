from rest_framework.routers import DefaultRouter

from .views import AdministrativeTaskViewSet, TaskAssignmentViewSet, TaskAttachmentViewSet, TaskCategoryViewSet, TaskChecklistItemViewSet, TaskCommentViewSet, TaskDashboardViewSet, TaskDependencyViewSet, TaskProjectViewSet, TaskRecurrenceViewSet

router = DefaultRouter()
router.register("tasks/categories", TaskCategoryViewSet, basename="task-category")
router.register("tasks/projects", TaskProjectViewSet, basename="task-project")
router.register("tasks/records", AdministrativeTaskViewSet, basename="administrative-task")
router.register("tasks/assignments", TaskAssignmentViewSet, basename="task-assignment")
router.register("tasks/checklist", TaskChecklistItemViewSet, basename="task-checklist")
router.register("tasks/dependencies", TaskDependencyViewSet, basename="task-dependency")
router.register("tasks/comments", TaskCommentViewSet, basename="task-comment")
router.register("tasks/attachments", TaskAttachmentViewSet, basename="task-attachment")
router.register("tasks/recurrences", TaskRecurrenceViewSet, basename="task-recurrence")
router.register("tasks/dashboard", TaskDashboardViewSet, basename="task-dashboard")

urlpatterns = router.urls
