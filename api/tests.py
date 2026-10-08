from django.test import TestCase
from rest_framework.test import APIClient


class HealthCheckTests(TestCase):
    def test_global_health_returns_ok(self):
        client = APIClient()
        response = client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_domain_app_health_endpoints(self):
        client = APIClient()
        for path, app_name in (
            ("/api/accounts/health/", "accounts"),
            ("/api/companies/health/", "companies"),
            ("/api/connections/health/", "connections"),
            ("/api/chat/health/", "chat"),
        ):
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.json(),
                    {"app": app_name, "status": "ok"},
                )

    def test_domain_resource_routes(self):
        client = APIClient()
        for path in (
            "/api/accounts/profiles/",
            "/api/accounts/past-roles/",
            "/api/companies/",
            "/api/connections/connection-requests/",
            "/api/connections/reports/",
            "/api/chat/conversations/",
            "/api/chat/messages/",
        ):
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
