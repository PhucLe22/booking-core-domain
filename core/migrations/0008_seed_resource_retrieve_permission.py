from django.db import migrations

# GET /resources/{id}/ (see docs/api_permission.md and 0005)
PERMISSIONS = [
    ("RESOURCE.RETRIEVE", "View resource"),
]

# same roles as RESOURCE.LIST; ADMIN passes every check without permissions
ROLE_PERMISSIONS = {
    "STAFF": ["RESOURCE.RETRIEVE"],
    "CUSTOMER": ["RESOURCE.RETRIEVE"],
}


def seed(apps, schema_editor):
    Role = apps.get_model("core", "Role")
    Permission = apps.get_model("core", "Permission")
    RolePermission = apps.get_model("core", "RolePermission")

    permissions = {}
    for code, name in PERMISSIONS:
        permissions[code], _ = Permission.objects.get_or_create(code=code, defaults={"name": name})

    for role_code, codes in ROLE_PERMISSIONS.items():
        role = Role.objects.filter(code=role_code).first()
        if role is None:
            continue
        for code in codes:
            RolePermission.objects.get_or_create(role=role, permission=permissions[code])


def unseed(apps, schema_editor):
    apps.get_model("core", "Permission").objects.filter(
        code__in=[code for code, _ in PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_seed_resource_type_retrieve_permission"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
