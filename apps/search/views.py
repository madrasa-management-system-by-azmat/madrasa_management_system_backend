from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.rbac import effective_permissions
from apps.users.tenancy import current_madrasa


LIMIT = 5


def result(record_id, title, subtitle, href, status=""):
    return {"id": str(record_id), "title": title, "subtitle": subtitle, "href": href, "status": status}


class GlobalSearchAPIView(APIView):
    """Permission-filtered, tenant-scoped search over primary business records."""

    def get(self, request):
        query = " ".join(request.query_params.get("q", "").strip().split())
        if len(query) < 2:
            return Response({"query": query, "groups": [], "total": 0})
        tenant = current_madrasa(request)
        permissions = effective_permissions(request.user)
        groups = []

        def add(key, label, permission, rows):
            if permission not in permissions:
                return
            items = list(rows)[:LIMIT]
            if items:
                groups.append({"key": key, "label": label, "items": items})

        if "students.view" in permissions:
            from apps.students.models import AdmissionApplication, Student
            students = Student.objects.filter(madrasa=tenant).filter(Q(registration_number__icontains=query) | Q(full_name__icontains=query) | Q(guardian_name__icontains=query)).select_related("current_class")[:LIMIT]
            add("students", "طلبہ", "students.view", (result(x.pk, x.full_name, f"{x.registration_number} · {x.current_class.name}", f"/dashboard/students/{x.pk}", x.lifecycle_status) for x in students))
            applications = AdmissionApplication.objects.filter(madrasa=tenant).filter(Q(application_number__icontains=query) | Q(full_name__icontains=query) | Q(guardian_name__icontains=query))[:LIMIT]
            add("admissions", "داخلہ درخواستیں", "students.view", (result(x.pk, x.full_name, x.application_number, "/dashboard/students/admissions", x.status) for x in applications))

        if "staff.view" in permissions:
            from apps.staff.models import Staff
            rows = Staff.objects.filter(madrasa=tenant).filter(Q(full_name__icontains=query) | Q(phone__icontains=query) | Q(role__icontains=query))[:LIMIT]
            add("staff", "اساتذہ و عملہ", "staff.view", (result(x.pk, x.full_name, x.get_role_display(), f"/dashboard/teachers/{x.pk}", "active" if x.is_active else "inactive") for x in rows))

        if "exams.view" in permissions:
            from apps.exams.models import InternalExam
            rows = InternalExam.objects.filter(madrasa=tenant).filter(Q(name__icontains=query) | Q(exam_type__icontains=query)).distinct()[:LIMIT]
            add("exams", "امتحانات", "exams.view", (result(x.pk, x.name, str(x.exam_date or ""), "/dashboard/exams/control", x.status) for x in rows))

        if "library.view" in permissions:
            from apps.library.models import LibraryBook
            rows = LibraryBook.objects.filter(madrasa=tenant).filter(Q(title__icontains=query) | Q(author__icontains=query) | Q(isbn__icontains=query))[:LIMIT]
            add("library", "لائبریری", "library.view", (result(x.pk, x.title, x.author or x.isbn, "/dashboard/library") for x in rows))

        if "fatwas.view" in permissions:
            from apps.fatwas.models import FatwaInquiry
            rows = FatwaInquiry.objects.filter(madrasa=tenant).filter(Q(case_number__icontains=query) | Q(subject__icontains=query))[:LIMIT]
            add("fatwas", "فتاویٰ", "fatwas.view", (result(x.pk, x.subject, x.case_number, "/dashboard/fatwas", x.status) for x in rows))

        if "meetings.view" in permissions:
            from apps.meetings.models import Meeting
            rows = Meeting.objects.filter(madrasa=tenant).filter(Q(meeting_number__icontains=query) | Q(title__icontains=query)).filter(Q(visibility="staff") | Q(chairperson=request.user) | Q(secretary=request.user) | Q(approver=request.user) | Q(participants__user=request.user) | Q(created_by=request.user)).distinct()[:LIMIT]
            add("meetings", "اجلاس", "meetings.view", (result(x.pk, x.title, x.meeting_number, "/dashboard/meetings", x.status) for x in rows))

        if "tasks.view" in permissions:
            from apps.tasks.models import AdministrativeTask
            rows = AdministrativeTask.objects.filter(madrasa=tenant).filter(Q(task_number__icontains=query) | Q(title__icontains=query)).filter(Q(visibility="staff") | Q(created_by=request.user) | Q(reviewer=request.user) | Q(assignments__assignee=request.user)).distinct()[:LIMIT]
            add("tasks", "انتظامی کام", "tasks.view", (result(x.pk, x.title, x.task_number, "/dashboard/tasks", x.status) for x in rows))

        if "documents.view" in permissions:
            from apps.documents.models import Document
            rows = Document.objects.filter(madrasa=tenant).filter(Q(document_number__icontains=query) | Q(title__icontains=query) | Q(keywords__icontains=query)).filter(Q(owner=request.user) | Q(reviewer=request.user) | Q(access_grants__user=request.user) | Q(confidentiality__in=["internal", "public"])).distinct()[:LIMIT]
            add("documents", "دستاویزات", "documents.view", (result(x.pk, x.title, x.document_number, "/dashboard/documents", x.status) for x in rows))

        if "leaves.view" in permissions:
            from apps.leaves.models import LeaveRequest
            rows = LeaveRequest.objects.filter(madrasa=tenant).filter(Q(request_number__icontains=query) | Q(staff__full_name__icontains=query) | Q(student__full_name__icontains=query)).select_related("staff", "student")[:LIMIT]
            add("leaves", "رخصتیں", "leaves.view", (result(x.pk, x.staff.full_name if x.staff_id else x.student.full_name, x.request_number, "/dashboard/leaves", x.status) for x in rows))

        if "certificates.view" in permissions:
            from apps.certificates.models import Certificate
            rows = Certificate.objects.filter(madrasa=tenant).filter(Q(serial_number__icontains=query) | Q(recipient_name_snapshot__icontains=query) | Q(title__icontains=query))[:LIMIT]
            add("certificates", "اسناد", "certificates.view", (result(x.pk, x.recipient_name_snapshot, f"{x.serial_number} · {x.title}", "/dashboard/certificate-verification", x.status) for x in rows))

        if "operations.view" in permissions:
            from apps.operations.models import Asset, InventoryItem, Vehicle
            items = InventoryItem.objects.filter(madrasa=tenant).filter(Q(sku__icontains=query) | Q(name__icontains=query))[:LIMIT]
            assets = Asset.objects.filter(madrasa=tenant).filter(Q(asset_number__icontains=query) | Q(name__icontains=query) | Q(serial_number__icontains=query))[:LIMIT]
            vehicles = Vehicle.objects.filter(madrasa=tenant).filter(Q(registration_number__icontains=query) | Q(name__icontains=query))[:LIMIT]
            combined = [result(x.pk, x.name, x.sku, "/dashboard/operations") for x in items] + [result(x.pk, x.name, x.asset_number, "/dashboard/operations", x.status) for x in assets] + [result(x.pk, x.name, x.registration_number, "/dashboard/operations", x.status) for x in vehicles]
            add("operations", "عملی انتظام", "operations.view", combined[:LIMIT])

        if "users.view" in permissions:
            User = get_user_model()
            rows = User.objects.filter(profile__madrasa=tenant).filter(Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(email__icontains=query)).select_related("profile")[:LIMIT]
            add("users", "صارفین", "users.view", (result(x.pk, x.get_full_name() or x.username, x.username, "/dashboard/users", x.profile.role) for x in rows))

        total = sum(len(group["items"]) for group in groups)
        return Response({"query": query, "groups": groups, "total": total})
