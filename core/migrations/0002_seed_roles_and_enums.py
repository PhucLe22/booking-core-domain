from django.db import migrations

ROLES = [
    ("ADMIN", "Admin", "Full access to the system"),
    ("STAFF", "Staff", "Manages bookings for customers and guests"),
    ("CUSTOMER", "Customer", "Books resources for themselves"),
]

# enum type code -> (name, [(code, name, value), ...])
ENUMS = {
    "RESOURCE_STATUS": (
        "Resource status",
        [
            ("ACTIVE", "Active", 1),
            ("INACTIVE", "Inactive", 2),
            ("MAINTENANCE", "Maintenance", 3),
        ],
    ),
    "BOOKING_STATUS": (
        "Booking status",
        [
            ("PENDING", "Pending", 2),
            ("CONFIRMED", "Confirmed", 1),
            ("CANCELLED", "Cancelled", 3),
            ("COMPLETED", "Completed", 4),
        ],
    ),
    "NOTIFICATION_TYPE": (
        "Notification type",
        [
            ("SYSTEM_NOTIFICATION", "System notification", 1),
        ],
    ),
}


def seed(apps, schema_editor):
    Role = apps.get_model("core", "Role")
    EnumType = apps.get_model("core", "EnumType")
    EnumDefinition = apps.get_model("core", "EnumDefinition")

    for code, name, description in ROLES:
        Role.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": description, "is_system": True},
        )

    for type_code, (type_name, definitions) in ENUMS.items():
        enum_type, _ = EnumType.objects.update_or_create(
            code=type_code, defaults={"name": type_name}
        )
        for position, (code, name, value) in enumerate(definitions):
            EnumDefinition.objects.update_or_create(
                enum_type=enum_type,
                code=code,
                defaults={
                    "name": name,
                    "value": value,
                    "position": position,
                    "is_system": True,
                },
            )


def unseed(apps, schema_editor):
    apps.get_model("core", "EnumDefinition").objects.filter(
        enum_type__code__in=ENUMS.keys(), is_system=True
    ).delete()
    apps.get_model("core", "EnumType").objects.filter(code__in=ENUMS.keys()).delete()
    apps.get_model("core", "Role").objects.filter(
        code__in=[code for code, _, _ in ROLES], is_system=True
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
