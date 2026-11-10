from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone
from .test_scanner import ScannerTests
from .models import StudentAttendance, StudentAttendanceScan


class DailyAttendanceTests(ScannerTests):
    def setUp(self):
        super().setUp()
        permission = patch("apps.students.attendance_daily.user_has_permission", return_value=True)
        permission.start()
        self.addCleanup(permission.stop)
        self.day = self.start.date().isoformat()

    def manual(self, times, count=0, **extra):
        with patch("apps.students.attendance_daily.timezone.now", return_value=self.start + timedelta(hours=12)):
            return self.client.post("/api/v1/student-attendance/manual-events/", {
                "student": self.student.pk, "date": self.day,
                "expected_count": count, "times": times, "reason": "Scanner unavailable", **extra,
            }, format="json")

    def test_manual_four_times_and_duration(self):
        response = self.manual(["08:00", "12:00", "14:00", "16:00"])
        self.assertEqual(response.status_code, 201, response.data)
        row = response.data["daily"]
        self.assertTrue(row["complete"])
        self.assertEqual(row["completed_minutes"], 360)
        self.assertEqual(row["location"], "outside")
        self.assertTrue(all(event["source"] == "manual" for event in row["events"]))
        self.assertEqual(StudentAttendance.objects.get().status, "present")
        self.assertEqual(self.manual(["17:00"], 4).status_code, 400)

    def test_mixed_scan_manual_and_stale_count(self):
        scan = self.scan(self.start)  # 09:00 local
        self.assertEqual(scan.data["daily"]["event_count"], 1)
        self.assertIsNotNone(scan.data["daily"]["entry_1"])
        self.assertIsNone(scan.data["daily"]["exit_1"])
        self.assertEqual(self.manual(["10:00"], 0).status_code, 409)
        response = self.manual(["10:00", "14:00", "15:00"], 1)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["daily"]["completed_minutes"], 120)
        self.assertEqual([event["source"] for event in response.data["daily"]["events"]], ["scan", "manual", "manual", "manual"])
        self.assertEqual(StudentAttendanceScan.objects.count(), 4)

    def test_invalid_manual_times_atomic(self):
        for times in (["10:00", "09:00"], ["10:00", "10:00"], ["23:00"]):
            self.assertEqual(self.manual(times).status_code, 400)
            self.assertEqual(StudentAttendanceScan.objects.count(), 0)
        self.assertEqual(self.manual(["08:00"], reason="").status_code, 400)

    def test_daily_roster_unmarked_and_all_slots(self):
        endpoint = "/api/v1/student-attendance/daily/"
        params = {"date_from": self.day, "date_to": self.day}
        row = self.client.get(endpoint, params).data["results"][0]
        self.assertEqual(row["status"], "unmarked")
        self.assertEqual(row["event_count"], 0)
        self.manual(["08:00", "12:00", "14:00", "16:00"])
        response = self.client.get(endpoint, params)
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]
        self.assertTrue(all(row[slot] for slot in ("entry_1", "exit_1", "entry_2", "exit_2")))
        self.assertEqual(self.client.get(endpoint, {"date_from": "invalid"}).status_code, 400)

    def test_status_cannot_erase_movements(self):
        self.manual(["08:00"])
        with patch("apps.users.permissions.user_has_permission", return_value=True):
            response = self.client.post("/api/v1/student-attendance/bulk-save/", {"records": [{
                "student": self.student.pk, "date": self.day, "status": "absent",
            }]}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(StudentAttendance.objects.get().status, "present")
        self.assertEqual(StudentAttendanceScan.objects.count(), 1)

    def test_period_report_includes_all_four_timestamps(self):
        self.manual(["08:00", "12:00", "14:00", "16:00"])
        with patch("apps.users.permissions.user_has_permission", return_value=True):
            response = self.client.get("/api/v1/student-attendance/report/", {
                "academic_class": self.student.current_class_id, "period": "weekly", "end_date": self.day,
            })
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["movement_totals"]["events"], 4)
        self.assertEqual(response.data["movement_totals"]["completed_days"], 1)
        self.assertEqual(response.data["movements"][0]["event_count"], 4)

    def test_no_open_pair_duration_invented(self):
        response = self.manual(["08:00", "12:00", "14:00"])
        row = response.data["daily"]
        self.assertFalse(row["complete"])
        self.assertEqual(row["location"], "inside")
        self.assertEqual(row["completed_minutes"], 240)