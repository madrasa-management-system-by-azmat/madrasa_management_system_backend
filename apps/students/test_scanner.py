import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import Madrasa, UserProfile
from .models import AcademicClass, Department, Student, StudentAttendance, StudentAttendanceScan


class ScannerTests(TestCase):
    def setUp(self):
        self.tenant = Madrasa.objects.create(name="Scanner school", slug="scanner-test")
        self.user = get_user_model().objects.create_user(username="scanner-operator")
        UserProfile.objects.create(user=self.user, madrasa=self.tenant, role="operator")
        department = Department.objects.create(madrasa=self.tenant, name="Scanner department")
        classroom = AcademicClass.objects.create(madrasa=self.tenant, department=department, name="Class 1")
        self.student = Student.objects.create(madrasa=self.tenant, full_name="Test Student", guardian_name="Test Guardian", gender="male", phone="", current_class=classroom, admission_date="2026-01-01")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.permission = patch("apps.students.scan_views.user_has_permission", return_value=True)
        self.permission.start()
        self.addCleanup(self.permission.stop)
        self.start = datetime(2026, 10, 21, 4, 0, tzinfo=dt_timezone.utc)
        self.url = "/api/v1/student-attendance/scanner/"

    def scan(self, instant, request_id=None, student_id=None):
        with patch("apps.students.scan_views.timezone.now", return_value=instant):
            return self.client.post(self.url, {
                "student_id": student_id or self.student.registration_number,
                "request_id": str(request_id or uuid.uuid4()),
            }, format="json")

    def test_four_scans_and_daily_reset(self):
        for index, direction in enumerate(["entry", "exit", "entry", "exit"]):
            response = self.scan(self.start + timedelta(minutes=index))
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data["scan"]["direction"], direction)
            self.assertEqual(response.data["scan"]["sequence"], index + 1)
            self.assertEqual(StudentAttendance.objects.get(student=self.student).status, "present")
        self.assertEqual(self.scan(self.start + timedelta(minutes=5)).status_code, 400)
        self.assertEqual(StudentAttendanceScan.objects.count(), 4)
        next_day = self.scan(self.start + timedelta(days=1))
        self.assertEqual(next_day.data["scan"]["sequence"], 1)

    def test_duplicate_request_is_idempotent_and_cooldown(self):
        key = uuid.uuid4()
        first = self.scan(self.start, key)
        again = self.scan(self.start + timedelta(seconds=1), key)
        self.assertEqual(again.status_code, 200)
        self.assertTrue(again.data["replayed"])
        self.assertEqual(first.data["scan"]["id"], again.data["scan"]["id"])
        self.assertEqual(self.scan(self.start + timedelta(seconds=2)).status_code, 400)
        self.assertEqual(StudentAttendanceScan.objects.count(), 1)

    def test_permissions_and_cross_tenant_isolation(self):
        with patch("apps.students.scan_views.user_has_permission", return_value=False):
            self.assertEqual(self.scan(self.start).status_code, 403)
            self.assertEqual(self.client.get(self.url).status_code, 403)
        other = Madrasa.objects.create(name="Other", slug="other-scanner")
        self.student.madrasa = other
        self.student.save(update_fields=["madrasa"])
        self.assertEqual(self.scan(self.start).status_code, 404)
        self.assertEqual(StudentAttendanceScan.objects.count(), 0)

    def test_inactive_and_invalid_payload(self):
        self.student.status = "inactive"
        self.student.save(update_fields=["status"])
        self.assertEqual(self.scan(self.start).status_code, 400)
        self.assertEqual(self.client.post(self.url, {"student_id": "unknown"}, format="json").status_code, 400)

    def test_late_status_preserved_and_server_local_day(self):
        # 20:00 UTC is the following day in Asia/Karachi.
        instant = datetime(2026, 10, 21, 20, 0, tzinfo=dt_timezone.utc)
        StudentAttendance.objects.create(madrasa=self.tenant, student=self.student, date="2026-10-22", status="late")
        result = self.scan(instant)
        self.assertEqual(str(result.data["scan"]["date"]), "2026-10-22")
        self.assertEqual(StudentAttendance.objects.get().status, "late")

    def test_history_and_guardian_denial(self):
        self.scan(self.start)
        with patch("apps.students.scan_views.timezone.localdate", return_value=self.start.date()):
            result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["total_scans"], 1)
        self.assertNotIn("guardian_phone", result.data["results"][0])
        self.user.profile.role = "guardian"
        self.user.profile.save(update_fields=["role"])
        self.assertEqual(self.scan(self.start).status_code, 403)