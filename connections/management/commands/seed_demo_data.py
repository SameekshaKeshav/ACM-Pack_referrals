from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q

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

        ConnectionRequest.objects.filter(
            Q(sender=sender, recipient=recipient)
            | Q(sender=recipient, recipient=sender),
        ).delete()

        self.stdout.write(self.style.SUCCESS("Postman fixtures are ready."))
        self.stdout.write(f"sender: {sender.username} (id={sender.pk})")
        self.stdout.write(f"recipient: {recipient.username} (id={recipient.pk})")
        self.stdout.write("sender password: SenderPass123!")
        self.stdout.write("recipient password: RecipientPass123!")
