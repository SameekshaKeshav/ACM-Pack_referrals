from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import path as url_path
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken


def raise_exception_view(request):
    raise Exception("test")


# Test-only URLs, used via override_settings(ROOT_URLCONF=__name__) so the
# raising view never exists in the real app.
urlpatterns = [url_path("raise-exception/", raise_exception_view)]


class HealthCheckTests(TestCase):
    def test_global_health_returns_ok(self):
        client = APIClient()
        response = client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "commit_hash": None})

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
                self.assertEqual(response.json(), {"app": app_name, "status": "ok"})

    @override_settings(COMMIT_HASH="abc123")
    def test_global_health_returns_commit_hash(self):
        client = APIClient()
        response = client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "commit_hash": "abc123"})

    DOMAIN_RESOURCE_ROUTES = (
        # /api/accounts/profiles/ removed: it was an uncurated third view
        # of people. Use /users/ (directory) or /me/ (own profile).
        "/api/accounts/past-roles/",
        "/api/companies/",
        # /api/connections/connection-requests/ is intentionally absent: #10
        # replaced the generic list route, so it 404s rather than 401s.
        "/api/connections/reports/",
        "/api/chat/conversations/",
        # /api/chat/messages/ is intentionally absent: it is POST-only (send a
        # message), so a GET returns 405 rather than 200.
    )

    def test_domain_resource_routes_reject_anonymous_callers(self):
        client = APIClient()
        for path in self.DOMAIN_RESOURCE_ROUTES:
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 401)

    def test_domain_resource_routes_accept_a_valid_token(self):
        user = get_user_model().objects.create_user(username="router", email="r@ncsu.edu")
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}"
        )
        for path in self.DOMAIN_RESOURCE_ROUTES:
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 200)


class ApiDocsTests(TestCase):
    def test_schema_is_public_and_lists_the_chat_routes(self):
        response = APIClient().get("/api/schema/?format=json")

        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        for path in (
            "/api/chat/conversations/",
            "/api/chat/conversations/{conversation_id}/messages/",
            "/api/chat/conversations/{conversation_id}/read/",
            "/api/chat/messages/",
        ):
            with self.subTest(path=path):
                self.assertIn(path, paths)

    def test_swagger_ui_is_public(self):
        self.assertEqual(APIClient().get("/api/docs/").status_code, 200)


class RequestLoggingMiddlewareTests(TestCase):
    def test_logs_successful_request(self):
        client = APIClient()
        with self.assertLogs("pack_referrals.middleware", level="INFO") as cm:
            client.get("/api/health/")

        self.assertEqual(len(cm.records), 1)
        record = cm.records[0]
        self.assertEqual(record.method, "GET")
        self.assertEqual(record.path, "/api/health/")
        self.assertEqual(record.status_code, 200)
        self.assertGreaterEqual(record.duration_ms, 0)

    def test_logs_actual_status_code(self):
        client = APIClient()
        with self.assertLogs("pack_referrals.middleware", level="INFO") as cm:
            client.post("/api/health/")

        self.assertEqual(len(cm.records), 1)
        record = cm.records[0]
        self.assertEqual(record.method, "POST")
        self.assertEqual(record.path, "/api/health/")
        self.assertEqual(record.status_code, 405)

    def test_query_string_is_not_logged(self):
        client = APIClient()
        with self.assertLogs("pack_referrals.middleware", level="INFO") as cm:
            client.get("/api/health/?token=secret")

        self.assertEqual(len(cm.records), 1)
        record = cm.records[0]
        self.assertEqual(record.path, "/api/health/")
        self.assertNotIn("secret", record.getMessage())

    @override_settings(ROOT_URLCONF=__name__)
    def test_logs_unhandled_exception_as_500(self):
        # By default the test client re-raises view exceptions; turn that off
        # so we get the 500 response a real user would get.
        client = APIClient(raise_request_exception=False)
        with self.assertLogs("pack_referrals.middleware", level="INFO") as cm:
            response = client.get("/raise-exception/")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(len(cm.records), 1)
        record = cm.records[0]
        self.assertEqual(record.path, "/raise-exception/")
        self.assertEqual(record.status_code, 500)
