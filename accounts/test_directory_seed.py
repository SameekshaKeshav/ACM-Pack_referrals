"""The seeded directory: what it creates, that it is repeatable, and that it
leaves every real member alone.
"""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from companies.models import Company

from . import directory_seed as seed
from .models import PastRole, Profile

User = get_user_model()
DIRECTORY = "/api/accounts/users/"


def run(*args):
    out = StringIO()
    call_command("seed_directory_data", *args, stdout=out)
    return out.getvalue()


class SeedDirectoryTests(TestCase):
    def test_it_creates_the_companies_and_the_people(self):
        run()
        self.assertEqual(seed.seeded_users().count(), len(seed.MEMBERS))
        for name in seed.COMPANIES:
            self.assertTrue(
                Company.objects.filter(name_normalized=Company.normalize_name(name)).exists(),
                name,
            )

    def test_every_seeded_person_is_visible_in_the_directory(self):
        run()
        # The directory hides anyone not ACTIVE, so this is also a check that
        # the seed sets account_status.
        self.assertEqual(
            Profile.objects.filter(
                user__in=seed.seeded_users(), account_status=Profile.AccountStatus.ACTIVE
            ).count(),
            len(seed.MEMBERS),
        )

    def test_running_it_twice_changes_nothing_the_second_time(self):
        run()
        before = (
            User.objects.count(), Profile.objects.count(),
            Company.objects.count(), PastRole.objects.count(),
        )
        run()
        after = (
            User.objects.count(), Profile.objects.count(),
            Company.objects.count(), PastRole.objects.count(),
        )
        self.assertEqual(before, after)

    def test_a_dry_run_changes_nothing(self):
        output = run("--dry-run")
        self.assertIn("nothing was changed", output.lower())
        self.assertEqual(seed.seeded_users().count(), 0)
        self.assertEqual(Company.objects.count(), 0)

    def test_it_leaves_a_real_member_completely_alone(self):
        """The reason this is safe to run on staging."""
        real = User.objects.create_user(username="kmpanick@ncsu.edu", email="kmpanick@ncsu.edu")
        profile = Profile.objects.create(
            user=real, bio="MY REAL BIO", major="Physics", grad_year=2026,
            account_status=Profile.AccountStatus.ACTIVE,
        )
        acme = Company.find_or_create("Acme")[0]
        PastRole.objects.create(user=real, company=acme, role_title="Intern")

        run()

        profile.refresh_from_db()
        self.assertEqual(profile.bio, "MY REAL BIO")
        self.assertEqual(profile.major, "Physics")
        self.assertEqual(PastRole.objects.filter(user=real).count(), 1)
        self.assertTrue(User.objects.filter(pk=real.pk).exists())

    def test_remove_deletes_the_seeded_people_but_keeps_the_companies(self):
        run()
        companies = Company.objects.count()

        run("--remove", "--yes")

        self.assertEqual(seed.seeded_users().count(), 0)
        self.assertEqual(Company.objects.count(), companies)
        self.assertEqual(PastRole.objects.count(), 0)

    def test_remove_leaves_a_real_member_alone_too(self):
        real = User.objects.create_user(username="real@ncsu.edu", email="real@ncsu.edu")
        run()
        run("--remove", "--yes")
        self.assertTrue(User.objects.filter(pk=real.pk).exists())

    def test_an_account_dropped_from_the_list_is_cleaned_up(self):
        """Editing MEMBERS must not leave an orphan in the directory."""
        stray = User.objects.create_user(
            username="seed.goneaway@ncsu.edu", email="seed.goneaway@ncsu.edu"
        )
        Profile.objects.create(user=stray, account_status=Profile.AccountStatus.ACTIVE)

        run()

        self.assertFalse(User.objects.filter(pk=stray.pk).exists())
        self.assertEqual(seed.seeded_users().count(), len(seed.MEMBERS))

    def test_nobody_can_sign_in_as_a_seeded_person(self):
        run()
        for user in seed.seeded_users()[:5]:
            self.assertFalse(user.has_usable_password(), user.email)


class SeededDirectoryBrowsingTests(TestCase):
    """The filters the demo actually clicks, against the seeded data."""

    @classmethod
    def setUpTestData(cls):
        run()
        cls.viewer = User.objects.create_user(username="viewer@ncsu.edu", email="viewer@ncsu.edu")
        Profile.objects.create(user=cls.viewer, account_status=Profile.AccountStatus.ACTIVE)

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.viewer)}")

    def get(self, query=""):
        response = self.client.get(f"{DIRECTORY}{query}")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_the_directory_needs_more_than_one_page(self):
        """A one-page directory does not show the demo that paging works."""
        body = self.get()
        self.assertGreater(body["count"], 20)
        self.assertEqual(len(body["results"]), 20)
        self.assertIsNotNone(body["next"])

    def test_filtering_by_major_narrows_it(self):
        everyone = self.get()["count"]
        cs = self.get("?major=Computer%20Science")
        self.assertGreater(cs["count"], 1)
        self.assertLess(cs["count"], everyone)
        for row in cs["results"]:
            self.assertIn("Computer Science", row["major"])

    def test_filtering_by_grad_year_narrows_it(self):
        body = self.get("?grad_year=2022")
        self.assertGreater(body["count"], 1)
        for row in body["results"]:
            self.assertEqual(row["grad_year"], 2022)

    def test_two_majors_at_once_returns_both(self):
        stats = self.get("?major=Statistics")["count"]
        physics = self.get("?major=Physics")["count"]
        both = self.get("?major=Statistics&major=Physics")["count"]
        self.assertEqual(both, stats + physics)

    def test_a_company_filter_finds_current_employees(self):
        red_hat = Company.objects.get(name_normalized=Company.normalize_name("Red Hat"))
        body = self.get(f"?company_id={red_hat.pk}")
        self.assertGreater(body["count"], 1)

    def test_a_company_filter_also_finds_people_through_a_past_role(self):
        """The other half of the company filter, and the reason the seed has past roles."""
        deere = Company.objects.get(name_normalized=Company.normalize_name("John Deere"))
        current = Profile.objects.filter(current_company=deere).count()
        body = self.get(f"?company_id={deere.pk}")
        self.assertEqual(body["count"], current)

        epic = Company.objects.get(name_normalized=Company.normalize_name("Epic Games"))
        via_past = PastRole.objects.filter(company=epic).count()
        at_epic = Profile.objects.filter(current_company=epic).count()
        self.assertGreater(via_past, 0)
        self.assertEqual(self.get(f"?company_id={epic.pk}")["count"], at_epic + via_past)

    def test_the_directory_never_shows_an_email_address(self):
        body = self.get()
        for row in body["results"]:
            self.assertNotIn("email", row)
