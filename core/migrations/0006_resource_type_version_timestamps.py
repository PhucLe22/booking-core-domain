import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    """ResourceType: version (optimistic locking), created_at, updated_at."""

    dependencies = [
        ("core", "0005_seed_resource_permissions"),
    ]

    operations = [
        migrations.AddField(
            model_name="resourcetype",
            name="version",
            field=models.PositiveIntegerField(default=1),
        ),
        # existing resource types get the time of the migration
        migrations.AddField(
            model_name="resourcetype",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="resourcetype",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
