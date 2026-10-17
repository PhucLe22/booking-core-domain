from django.db import migrations


def seed(apps, schema_editor):
    StorageConfig = apps.get_model("core", "StorageConfig")
    if not StorageConfig.objects.filter(is_default=True).exists():
        StorageConfig.objects.update_or_create(
            code="LOCAL",
            defaults={
                "name": "Local storage",
                "provider": "LOCAL",
                "configuration": {"path": "files"},
                "max_file_size_bytes": 10 * 1024 * 1024,
                "allowed_extensions": [
                    "jpg", "jpeg", "png", "webp", "gif",
                    "pdf", "doc", "docx", "xls", "xlsx", "csv", "txt",
                ],
                "is_default": True,
            },
        )


def unseed(apps, schema_editor):
    apps.get_model("core", "StorageConfig").objects.filter(
        code="LOCAL", files__isnull=True
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_seed_roles_and_enums"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
