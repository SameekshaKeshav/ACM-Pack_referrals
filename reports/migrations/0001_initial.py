from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Report",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "target_type",
                    models.CharField(
                        choices=[("user", "User"), ("message", "Message")],
                        max_length=10,
                    ),
                ),
                (
                    "target_id",
                    models.PositiveBigIntegerField(),
                ),
                (
                    "reason",
                    models.CharField(
                        choices=[
                            ("spam", "Spam"),
                            ("harassment", "Harassment"),
                            ("inappropriate_content", "Inappropriate content"),
                            ("misinformation", "Misinformation"),
                            ("other", "Other"),
                        ],
                        max_length=30,
                    ),
                ),
                ("details", models.CharField(blank=True, max_length=1000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "reporter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="submitted_reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
