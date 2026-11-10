from django.db import migrations

# one permission per resource API: "<BASENAME>.<ACTION>" (see docs/api_permission.md)
PERMISSIONS = [
    ("RESOURCE.LIST", "List resources"),
    ("RESOURCE.CREATE", "Create resource"),
    ("RESOURCE.UPDATE", "Edit resource"),
    ("RESOURCE.DESTROY", "Delete resource"),
    ("RESOURCE_TYPE.LIST", "List resource types"),
    ("RESOURCE_TYPE.CREATE", "Create resource type"),
    ("RESOURCE_TYPE.UPDATE", "Edit resource type"),
    ("RESOURCE_TYPE.DESTROY", "Delete resource type"),
]

# what each system role could do before; ADMIN passes every check without permissions
ROLE_PERMISSIONS = {
    "STAFF": [code for code, _ in PERMISSIONS],
    "CUSTOMER": ["RESOURCE.LIST", "RESOURCE_TYPE.LIST"],
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
        ("core", "0004_resource_status_optional"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
