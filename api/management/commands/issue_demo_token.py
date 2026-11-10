import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Profile
from api import demo

User = get_user_model()

# The key the React app reads its session from (frontend/src/auth/session.js).
SESSION_KEY = "pack-referrals.session.v1"


class Command(BaseCommand):
    help = (
        "Print a login for one of the demo accounts, so the presenter can sign in without "
        "waiting for an emailed code. Demo accounts only. Needs ALLOW_DEMO_TOOLS=1."
    )

    def add_arguments(self, parser):
        parser.add_argument("email", help=f"One of: {', '.join(demo.CAST_EMAILS)}")

    def handle(self, *args, email, **options):
        demo.require_demo_tools()
        email = email.strip().lower()
        if email not in demo.CAST_EMAILS:
            # A token is a login. This only ever mints one for an address in the demo cast
            # (which includes some team members' real accounts), never for any other member
            # or an admin. Anyone with shell access on the server can still sign in as the cast.
            raise CommandError(
                "Only the demo accounts can be signed in this way: " + ", ".join(demo.CAST_EMAILS)
            )
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        demo.refuse_staff(user, "sign in as it")
        profile = getattr(user, "profile", None)
        if profile is None or profile.account_status != Profile.AccountStatus.ACTIVE:
            raise CommandError(
                f"{email} does not exist yet. "
                "Run: ALLOW_DEMO_TOOLS=1 python manage.py reset_demo_data"
            )

        refresh = RefreshToken.for_user(user)
        session = {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {"id": user.pk, "email": user.email},
        }
        self.stdout.write(
            f"Signed in as {user.get_full_name()} <{user.email}>. "
            f"The access token is valid for about {settings.ACCESS_TOKEN_LIFETIME_HOURS} hours, "
            "and the refresh token printed with it for up to "
            f"{settings.REFRESH_TOKEN_LIFETIME_DAYS} days."
        )
        self.stdout.write("Treat it like a password: do not paste it in chat or commit it.")
        self.stdout.write("")
        self.stdout.write(
            "In the browser, open the app, open the developer console, "
            "paste this line, and press Enter:"
        )
        self.stdout.write("")
        self.stdout.write(
            f"localStorage.setItem({json.dumps(SESSION_KEY)}, "
            f"{json.dumps(json.dumps(session))}); location.href = '/chat';"
        )
