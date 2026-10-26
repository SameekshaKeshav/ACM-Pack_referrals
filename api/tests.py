import tempfile
from pathlib import Path

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


class FrontendIndexTests(TestCase):
    """The catch-all URL serves the React app's index.html for non-API paths."""

    INDEX_HTML = "<!doctype html><title>test app</title>"

    def setUp(self):
        # A fake build, so these tests don't depend on running npm run build.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dist = Path(tmp.name)
        (self.dist / "index.html").write_text(self.INDEX_HTML)
        settings_override = override_settings(FRONTEND_DIST=self.dist)
        settings_override.enable()
        self.addCleanup(settings_override.disable)

    def test_app_routes_return_index_html(self):
        for path in ("/", "/chat/5", "/profile"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "text/html")
                self.assertEqual(response["Cache-Control"], "no-cache")
                self.assertEqual(response.getvalue().decode(), self.INDEX_HTML)

    def test_unknown_api_path_is_still_404(self):
        response = self.client.get("/api/nope/")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b"test app", response.content)

    def test_missing_files_are_404_not_index_html(self):
        for path in ("/favicon.ico", "/robots.txt", "/chat/old-bundle.js", "/.env"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn(b"test app", response.content)

    def test_admin_without_slash_still_redirects(self):
        response = self.client.get("/admin")
        self.assertRedirects(
            response, "/admin/", status_code=301, fetch_redirect_response=False
        )

    def test_only_get_and_head_are_allowed(self):
        self.assertEqual(self.client.post("/chat").status_code, 405)

    def test_missing_build_returns_503(self):
        with override_settings(FRONTEND_DIST=self.dist / "missing"):
            response = self.client.get("/chat")
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"npm run build", response.content)
