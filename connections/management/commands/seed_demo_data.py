from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Profile
from companies.models import Company
from connections.models import ConnectionRequest


User = get_user_model()


class Command(BaseCommand):
    help = "Create repeatable local fixtures for API and Postman testing."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            self.stdout.write("Demo data seeding is disabled when DEBUG is false.")
            return

        company, _ = Company.objects.update_or_create(
            name="Acme",
            defaults={"industry_tag": "Technology"},
        )

        sender, _ = User.objects.get_or_create(
            username="postman_sender",
            defaults={
                "first_name": "Sender",
                "last_name": "User",
            },
        )
        sender.first_name = "Sender"
        sender.last_name = "User"
        sender.is_active = True
        sender.set_password("SenderPass123!")
        sender.save()

        recipient, _ = User.objects.get_or_create(
            username="postman_recipient",
        )
        recipient.is_active = True
        recipient.set_password("RecipientPass123!")
        recipient.save()

        # A logged-in user who is not part of the sender/recipient conversation,
        # used to check that chat endpoints refuse outsiders.
        outsider, _ = User.objects.get_or_create(username="postman_outsider")
        outsider.set_password("OutsiderPass123!")
        outsider.save()

        Profile.objects.update_or_create(
            user=sender,
            defaults={
                "current_company": company,
                "open_to_connect": True,
                "account_status": Profile.AccountStatus.ACTIVE,
            },
        )
        Profile.objects.update_or_create(
            user=recipient,
            defaults={
                "current_company": company,
                "open_to_connect": True,
                "account_status": Profile.AccountStatus.ACTIVE,
            },
        )
        Profile.objects.update_or_create(
            user=outsider,
            defaults={"open_to_connect": True},
        )

        ConnectionRequest.objects.filter(
            Q(sender=sender, recipient=recipient)
            | Q(sender=recipient, recipient=sender),
        ).delete()

        self.stdout.write(self.style.SUCCESS("Postman fixtures are ready."))
        self.stdout.write(f"sender: {sender.username} (id={sender.pk})")
        self.stdout.write(f"recipient: {recipient.username} (id={recipient.pk})")
        self.stdout.write("sender password: SenderPass123!")
        self.stdout.write("recipient password: RecipientPass123!")
        # There is no password login (auth is email code -> JWT), so print
        # Bearer tokens for these local-only users to paste into Postman.
        self.stdout.write(f"sender_token: {AccessToken.for_user(sender)}")
        self.stdout.write(f"recipient_token: {AccessToken.for_user(recipient)}")
        self.stdout.write(f"outsider_token: {AccessToken.for_user(outsider)}")
