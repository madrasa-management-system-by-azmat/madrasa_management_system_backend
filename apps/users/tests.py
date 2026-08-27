from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class AuthenticationApiTests(APITestCase):
    def test_register_login_and_current_user(self):
        registration = self.client.post(
            reverse("auth-register"),
            {
                "username": "admin",
                "password": "safe-password-123",
                "first_name": "محمد",
                "phone": "03001234567",
            },
            format="json",
        )

        self.assertEqual(registration.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", registration.data)
        self.assertIn("refresh", registration.data)

        login = self.client.post(
            reverse("auth-login"),
            {"identifier": "admin", "password": "safe-password-123"},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)

        self.assertIn("access", login.data)
        self.assertIn("refresh", login.data)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        current_user = self.client.get(reverse("auth-me"))
        self.assertEqual(current_user.status_code, status.HTTP_200_OK)
        self.assertEqual(current_user.data["username"], "admin")

        refresh = self.client.post(
            reverse("auth-token-refresh"),
            {"refresh": login.data["refresh"]},
            format="json",
        )
        self.assertEqual(refresh.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh.data)
        self.assertIn("refresh", refresh.data)

        logout = self.client.post(
            reverse("auth-logout"),
            {"refresh": refresh.data["refresh"]},
            format="json",
        )
        self.assertEqual(logout.status_code, status.HTTP_204_NO_CONTENT)

        revoked_refresh = self.client.post(
            reverse("auth-token-refresh"),
            {"refresh": refresh.data["refresh"]},
            format="json",
        )
        self.assertEqual(revoked_refresh.status_code, status.HTTP_401_UNAUTHORIZED)
