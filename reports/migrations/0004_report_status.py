from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reports", "0003_report_targets_and_deduplication"),
    ]

    operations = [
        migrations.AddField(
            model_name="report",
            name="status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("reviewed", "Reviewed")],
                default="pending",
                max_length=20,
            ),
        ),
    ]