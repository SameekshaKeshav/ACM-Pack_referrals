from django.test import TestCase
from rest_framework.test import APIClient


class ConnectionTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_create_connection_request_is_not_implemented(self):
        response = self.client.post("/api/connections/", {}, format="json")

        self.assertEqual(response.status_code, 501)

    def test_accept_connection_request_is_not_implemented(self: TestCase) -> None:
        response = self.client.patch(
            "/api/connections/123/accept/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 501)
