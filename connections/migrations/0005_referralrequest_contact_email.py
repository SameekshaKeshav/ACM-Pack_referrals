from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('connections', '0004_delete_report'),
    ]

    operations = [
        migrations.AddField(
            model_name='referralrequest',
            name='contact_email',
            field=models.EmailField(blank=True, max_length=254),
        ),
    ]
