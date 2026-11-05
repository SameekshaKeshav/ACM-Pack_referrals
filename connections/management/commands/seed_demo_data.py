from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import AlumniAccessRequest, PastRole, Profile, VerificationCode
from chat.models import Conversation
from companies.models import Company
from connections.models import ConnectionRequest, ReferralRequest, Report


User = get_user_model()

# Addresses the Postman collection uses for the public auth routes. Signup needs
# an address with no account yet; verify needs an unverified account whose code
# is known, since locally the real one only reaches the runserver console.
SIGNUP_EMAIL = "postman.signup@ncsu.edu"
VERIFY_EMAIL = "postman.verify@ncsu.edu"
ALUMNI_EMAIL = "postman.alumni@example.com"


class Command(BaseCommand):
    help = "Create repeatable local fixtures for API and Postman testing."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            self.stdout.write("Demo data seeding is disabled when DEBUG is false.")
            return

        with transaction.atomic():
            company, _ = Company.objects.update_or_create(
                name="Acme",
                defaults={"industry_tag": "Technology"},
            )
            sender = self._user("postman_sender", "Sender", "SenderPass123!")
            recipient = self._user("postman_recipient", "Recipient", "RecipientPass123!")
            # A logged-in user who is not part of the sender/recipient
            # conversation, used to check that endpoints refuse outsiders.
            outsider = self._user("postman_outsider", "Outsider", "OutsiderPass123!")

            # Active, or the directory hides them and referral asks are refused.
            # The recipient works at Acme too, so a referral ask can name it.
            for user, major in (
                (sender, "Computer Science"),
                (recipient, "Computer Engineering"),
                (outsider, "Statistics"),
            ):
                Profile.objects.update_or_create(
                    user=user,
                    defaults={
                        "current_company": company,
                        "open_to_connect": True,
                        "account_status": Profile.AccountStatus.ACTIVE,
                        "major": major,
                        "grad_year": 2027,
                    },
                )

            # Clear whatever an earlier run left behind, so every run starts the
            # same and the collection's 201s and 409s mean the same thing.
            users = [sender, recipient, outsider]
            involving = Q(sender__in=users) | Q(recipient__in=users)
            # Conversations survive a deleted connection request (SET_NULL), so
            # they are removed first while the link to them still exists.
            Conversation.objects.filter(
                participants__in=users
            ).distinct().delete()
            ConnectionRequest.objects.filter(involving).delete()
            ReferralRequest.objects.filter(involving).delete()
            PastRole.objects.filter(user__in=users).delete()
            Report.objects.filter(reporter__in=users).delete()
            AlumniAccessRequest.objects.filter(email=ALUMNI_EMAIL).delete()
            User.objects.filter(email__in=[SIGNUP_EMAIL, VERIFY_EMAIL]).delete()

            verify_user = User(username=VERIFY_EMAIL, email=VERIFY_EMAIL, is_active=False)
            verify_user.set_unusable_password()
            verify_user.save()
            Profile.objects.create(user=verify_user)
            _, verify_code = VerificationCode.issue(verify_user)

        self.stdout.write(self.style.SUCCESS("Postman fixtures are ready."))
        self.stdout.write(f"sender: {sender.username} (id={sender.pk})")
        self.stdout.write(f"recipient: {recipient.username} (id={recipient.pk})")
        self.stdout.write("sender password: SenderPass123!")
        self.stdout.write("recipient password: RecipientPass123!")
        # One "name: value" per line from here on, so scripts can read them.
        self.stdout.write(f"sender_id: {sender.pk}")
        self.stdout.write(f"recipient_id: {recipient.pk}")
        self.stdout.write(f"outsider_id: {outsider.pk}")
        self.stdout.write(f"company_id: {company.pk}")
        self.stdout.write(f"signup_email: {SIGNUP_EMAIL}")
        self.stdout.write(f"verify_email: {VERIFY_EMAIL}")
        self.stdout.write(f"verify_code: {verify_code}")
        self.stdout.write(f"alumni_email: {ALUMNI_EMAIL}")
        # There is no password login (auth is email code -> JWT), so print
        # Bearer tokens for these local-only users to paste into Postman.
        self.stdout.write(f"sender_token: {AccessToken.for_user(sender)}")
        self.stdout.write(f"recipient_token: {AccessToken.for_user(recipient)}")
        self.stdout.write(f"outsider_token: {AccessToken.for_user(outsider)}")

    def _user(self, username, first_name, password):
        user, _ = User.objects.get_or_create(username=username)
        user.first_name = first_name
        user.last_name = "User"
        user.set_password(password)
        user.save()
        return user
