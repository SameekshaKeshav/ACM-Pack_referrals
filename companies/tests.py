from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import PastRole, Profile

from .models import Company
from .services import affiliated_users

User = get_user_model()


def member(username, first="", major="", grad_year=None, company=None, role="",
           account_status=Profile.AccountStatus.ACTIVE):
    """A verified member by default; pass account_status to make an exception.

    The model default is `unverified`, which is right for signup but wrong for
    a fixture, since an unverified account is invisible to the directory.
    """
    user = User.objects.create_user(username=username, first_name=first, last_name="Student")
    Profile.objects.create(
        user=user,
        major=major,
        grad_year=grad_year,
        current_company=company,
        current_role=role,
        account_status=account_status,
    )
    return user


class FindOrCreateTests(APITestCase):
    def test_spellings_of_the_same_name_resolve_to_one_row(self):
        first, created = Company.find_or_create("Google")
        self.assertTrue(created)

        for spelling in ("  google  ", "Google Inc.", "GOOGLE, LLC", "google corp"):
            with self.subTest(spelling=spelling):
                company, created = Company.find_or_create(spelling)
                self.assertEqual(company.pk, first.pk)
                self.assertFalse(created)

        self.assertEqual(Company.objects.count(), 1)

    def test_the_first_spelling_becomes_the_display_name(self):
        Company.find_or_create("  google  ")
        Company.find_or_create("GOOGLE, LLC")
        self.assertEqual(Company.objects.get().name, "google")

    def test_genuinely_different_names_stay_separate(self):
        Company.find_or_create("Google")
        Company.find_or_create("Google Cloud")
        Company.find_or_create("IBM")
        self.assertEqual(Company.objects.count(), 3)

    def test_a_blank_name_is_rejected(self):
        for blank in ("", "   ", "  .  ", ",,,", "\t\n"):
            with self.subTest(blank=blank):
                with self.assertRaises(ValueError):
                    Company.find_or_create(blank)

    def test_a_name_that_is_only_a_legal_suffix_is_rejected(self):
        """The suffix regex only strips one that trails a real name, so "Inc."
        would otherwise become a company called "Inc."."""
        for suffix in ("Inc.", "LLC", "  ltd ", "Corporation", "co"):
            with self.subTest(suffix=suffix):
                with self.assertRaises(ValueError):
                    Company.find_or_create(suffix)

    def test_a_suffix_still_strips_when_it_trails_a_real_name(self):
        company, _ = Company.find_or_create("Acme Inc.")
        self.assertEqual(company.name_normalized, "acme")


class AffiliatedUsersTests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Google")

    def test_past_roles_are_listed(self):
        user = member("alice", "Alice", "Computer Science", 2027)
        PastRole.objects.create(
            user=user, company=self.company, role_title="SWE Intern",
            start_date="2025-05-01", end_date="2025-08-01",
        )
        rows = affiliated_users(self.company)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Alice Student")
        self.assertEqual(rows[0]["role_title"], "SWE Intern")
        self.assertEqual(rows[0]["major"], "Computer Science")
        self.assertFalse(rows[0]["is_current"])

    def test_current_employees_are_listed_too(self):
        member("bob", "Bob", "Statistics", 2026, company=self.company, role="Analyst")
        rows = affiliated_users(self.company)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["is_current"])
        self.assertIsNone(rows[0]["start_date"])

    def test_someone_with_both_appears_once_as_current(self):
        user = member("carol", "Carol", "CS", 2025, company=self.company, role="SWE")
        PastRole.objects.create(user=user, company=self.company, role_title="Intern")

        rows = affiliated_users(self.company)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["is_current"])

    def test_other_companies_are_not_included(self):
        other = Company.objects.create(name="IBM")
        user = member("dave")
        PastRole.objects.create(user=user, company=other, role_title="Intern")
        self.assertEqual(affiliated_users(self.company), [])


class CompanyEndpointTests(APITestCase):
    def setUp(self):
        self.user = member("alice", "Alice", "Computer Science", 2027)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.user)}")

    def _add_role(self, client, company_name, role_title="Intern"):
        return client.post(
            "/api/accounts/past-roles/",
            {"company_name": company_name, "role_title": role_title},
            format="json",
        )

    def test_adding_a_role_creates_the_company(self):
        response = self._add_role(self.client, "Google")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Company.objects.count(), 1)
        self.assertEqual(response.data["company"]["name"], "Google")

    def test_two_users_typing_the_same_name_differently_share_a_company(self):
        """The tracker's stated deliverable."""
        first = self._add_role(self.client, "Google", "SWE Intern")

        other = member("bob", "Bob", "Statistics", 2026)
        client = self.client_class()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(other)}")
        second = self._add_role(client, "  google  ", "Data Analyst")

        self.assertEqual(first.data["company"]["id"], second.data["company"]["id"])
        self.assertEqual(Company.objects.count(), 1)

        detail = self.client.get(f"/api/companies/{first.data['company']['id']}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        names = {row["name"] for row in detail.data["affiliated_users"]}
        self.assertEqual(names, {"Alice Student", "Bob Student"})

    def test_a_blank_company_name_is_a_400(self):
        response = self._add_role(self.client, "   ")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Company.objects.count(), 0)

    def test_the_role_is_owned_by_the_caller_not_the_request_body(self):
        victim = member("victim")
        response = self.client.post(
            "/api/accounts/past-roles/",
            {"company_name": "Google", "role_title": "Intern", "user": victim.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PastRole.objects.get().user, self.user)

    def test_you_cannot_delete_someone_elses_role(self):
        other = member("bob")
        role = PastRole.objects.create(
            user=other, company=Company.objects.create(name="IBM"), role_title="Intern"
        )
        response = self.client.delete(f"/api/accounts/past-roles/{role.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(PastRole.objects.filter(pk=role.pk).exists())

    def test_companies_are_read_only_over_the_api(self):
        company = Company.objects.create(name="Google")
        self.assertEqual(
            self.client.post("/api/companies/", {"name": "Fake"}, format="json").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(
            self.client.delete(f"/api/companies/{company.pk}/").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_company_endpoints_require_a_token(self):
        anon = self.client_class()
        self.assertEqual(anon.get("/api/companies/").status_code, status.HTTP_401_UNAUTHORIZED)


class AffiliationVisibilityTests(APITestCase):
    """A company page is a directory view, so it hides the same people the
    people-directory hides."""

    def setUp(self):
        self.company = Company.objects.create(name="Google")
        from accounts.models import PastRole

        for username, state in (
            ("active_current", "active"),
            ("unverified_current", "unverified"),
            ("suspended_current", "suspended"),
        ):
            member(username, username.title(), company=self.company, role="SWE",
                   account_status=state)

        for username, state in (
            ("active_past", "active"),
            ("unverified_past", "unverified"),
            ("suspended_past", "suspended"),
        ):
            user = member(username, username.title(), account_status=state)
            PastRole.objects.create(user=user, company=self.company, role_title="Intern")

    def test_only_verified_members_are_listed(self):
        names = {row["name"] for row in affiliated_users(self.company)}
        self.assertEqual(names, {"Active_Current Student", "Active_Past Student"})

    def test_the_company_endpoint_hides_them_too(self):
        viewer = member("viewer")
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(viewer)}"
        )
        response = self.client.get(f"/api/companies/{self.company.pk}/")
        names = {row["name"] for row in response.data["affiliated_users"]}
        self.assertNotIn("Suspended_Current Student", names)
        self.assertNotIn("Unverified_Past Student", names)
        self.assertEqual(len(names), 2)


class CompanySearchTests(APITestCase):
    def setUp(self):
        for name in ("Google", "Google Cloud", "IBM", "Red Hat", "Goldman Sachs"):
            Company.objects.create(name=name)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(member('viewer'))}"
        )

    def names(self, query=""):
        response = self.client.get(f"/api/companies/{query}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return sorted(row["name"] for row in response.data)

    def test_no_search_returns_everything(self):
        self.assertEqual(len(self.names()), 5)

    def test_partial_match_is_case_insensitive(self):
        self.assertEqual(self.names("?search=goog"), ["Google", "Google Cloud"])
        self.assertEqual(self.names("?search=GOOG"), ["Google", "Google Cloud"])

    def test_a_suffixed_spelling_finds_the_stored_company(self):
        """Someone typing the legal name should still find "Google"."""
        self.assertIn("Google", self.names("?search=Google Inc."))

    def test_search_matches_anywhere_in_the_name(self):
        self.assertEqual(self.names("?search=hat"), ["Red Hat"])

    def test_no_matches_is_an_empty_list_not_an_error(self):
        self.assertEqual(self.names("?search=zzzz"), [])

    def test_a_blank_search_is_ignored(self):
        self.assertEqual(len(self.names("?search=%20%20")), 5)

    def test_search_requires_a_token(self):
        anon = self.client_class()
        self.assertEqual(
            anon.get("/api/companies/?search=goog").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class PastRoleDateTests(APITestCase):
    def setUp(self):
        self.user = member("alice", "Alice")
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.user)}"
        )

    def post(self, **extra):
        return self.client.post(
            "/api/accounts/past-roles/",
            {"company_name": "Google", "role_title": "Intern", **extra},
            format="json",
        )

    def test_end_before_start_is_rejected(self):
        response = self.post(start_date="2025-08-01", end_date="2025-05-01")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_date", response.data)

    def test_a_sensible_range_is_accepted(self):
        self.assertEqual(
            self.post(start_date="2025-05-01", end_date="2025-08-01").status_code,
            status.HTTP_201_CREATED,
        )

    def test_an_ongoing_role_needs_no_end_date(self):
        self.assertEqual(
            self.post(start_date="2025-05-01").status_code, status.HTTP_201_CREATED
        )

    def test_patching_one_date_is_checked_against_the_stored_other(self):
        created = self.post(start_date="2025-05-01", end_date="2025-08-01")
        role_id = created.data["id"]
        response = self.client.patch(
            f"/api/accounts/past-roles/{role_id}/", {"end_date": "2025-01-01"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
