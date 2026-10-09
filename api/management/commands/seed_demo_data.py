from django.core.management.base import BaseCommand

from accounts.models import Profile
from companies.models import Company
from connections.models import ConnectionRequest
from django.contrib.auth import get_user_model


User = get_user_model()


class Command(BaseCommand):
    help = "Create repeatable local fixtures for API and Postman testing."

    def handle(self, *args, **options):
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
        sender.set_password("SenderPass123!")
        sender.save()

        recipient, _ = User.objects.get_or_create(
            username="postman_recipient",
        )
        recipient.set_password("RecipientPass123!")
        recipient.save()

        Profile.objects.update_or_create(
            user=sender,
            defaults={
                "current_company": company,
                "open_to_connect": True,
            },
        )
        Profile.objects.update_or_create(
            user=recipient,
            defaults={"open_to_connect": True},
        )

        ConnectionRequest.objects.filter(
            sender=sender,
            recipient=recipient,
        ).delete()

        self.stdout.write(self.style.SUCCESS("Postman fixtures are ready."))
        self.stdout.write(f"sender: {sender.username} (id={sender.pk})")
        self.stdout.write(f"recipient: {recipient.username} (id={recipient.pk})")
        self.stdout.write("sender password: SenderPass123!")
        self.stdout.write("recipient password: RecipientPass123!")
