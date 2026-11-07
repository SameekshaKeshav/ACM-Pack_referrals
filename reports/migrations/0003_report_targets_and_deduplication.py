from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reports", "0002_alter_report_reason"),
    ]

    operations = [
        migrations.AlterField(
            model_name="report",
            name="target_type",
            field=models.CharField(
                choices=[
                    ("user", "User"),
                    ("message", "Message"),
                    ("experience", "Interview experience"),
                ],
                max_length=10,
            ),
        ),
        migrations.AddConstraint(
            model_name="report",
            constraint=models.UniqueConstraint(
                fields=("reporter", "target_type", "target_id"),
                name="unique_report_per_reporter_target",
            ),
        ),
    ]
