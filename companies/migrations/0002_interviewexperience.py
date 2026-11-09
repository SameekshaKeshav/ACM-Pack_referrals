from django.conf import settings
from django.db import migrations, models
from django.core.validators import MaxValueValidator, MinValueValidator
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("companies", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="InterviewExperience",
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
                ("role_title", models.CharField(max_length=255)),
                (
                    "outcome",
                    models.CharField(
                        choices=[
                            ("offer", "Offer"),
                            ("rejected", "Rejected"),
                            ("no_response", "No response"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "difficulty",
                    models.PositiveSmallIntegerField(
                        validators=[MinValueValidator(1), MaxValueValidator(5)]
                    ),
                ),
                ("process_text", models.TextField(max_length=5000)),
                ("is_hidden", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="interview_experiences",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="interview_experiences",
                        to="companies.company",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
