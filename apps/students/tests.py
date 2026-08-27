from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import AcademicClass, Department, Halaqa, Student


class StudentApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="api-user", password="safe-password-123")
        self.client.force_authenticate(self.user)
        self.department = Department.objects.create(name="شعبہ حفظ")
        self.academic_class = AcademicClass.objects.create(
            name="حفظ اول",
            department=self.department,
        )
        self.halaqa = Halaqa.objects.create(name="حلقہ نور", ustad_name="قاری عبدالرحمن")

    def test_create_student_assigns_registration_number(self):
        response = self.client.post(
            reverse("student-list"),
            {
                "full_name": "احمد رضا",
                "guardian_name": "محمد یوسف",
                "phone": "03001234567",
                "gender": "male",
                "residential_status": "day_scholar",
                "current_class": self.academic_class.id,
                "current_halaqa": self.halaqa.id,
                "admission_date": date.today().isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["registration_number"], "ST-0001")
        self.assertEqual(Student.objects.count(), 1)

    def test_student_list_supports_search(self):
        Student.objects.create(
            full_name="مریم فاطمہ",
            guardian_name="عبدالرحمن",
            phone="03127654321",
            gender="female",
            current_class=self.academic_class,
            admission_date=date.today(),
        )

        response = self.client.get(reverse("student-list"), {"search": "مریم"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["full_name"], "مریم فاطمہ")
