from django.db import migrations

# the 9 booking statuses of docs/web_api_spec.md, in the order of the spec:
# (code, name, value)
BOOKING_STATUSES = [
    ("AWAITING_PAYMENT", "Awaiting payment", 5),
    ("PENDING_APPROVAL", "Pending approval", 2),
    ("CONFIRMED", "Confirmed", 1),
    ("CHECKED_IN", "Checked in", 6),
    ("COMPLETED", "Completed", 4),
    ("EXPIRED", "Expired", 7),
    ("REJECTED", "Rejected", 8),
    ("CANCELLED", "Cancelled", 3),
    ("NO_SHOW", "No show", 9),
]
NEW_CODES = ["AWAITING_PAYMENT", "CHECKED_IN", "EXPIRED", "REJECTED", "NO_SHOW"]


def seed(apps, schema_editor):
    EnumType = apps.get_model("core", "EnumType")
    EnumDefinition = apps.get_model("core", "EnumDefinition")
    Booking = apps.get_model("core", "Booking")
    BookingHistory = apps.get_model("core", "BookingHistory")

    enum_type = EnumType.objects.get(code="BOOKING_STATUS")
    values = EnumDefinition.objects.filter(enum_type=enum_type)

    # PENDING becomes PENDING_APPROVAL: the row is renamed, so bookings and their
    # history keep pointing at it
    pending = values.filter(code="PENDING").first()
    approval = values.filter(code="PENDING_APPROVAL").first()
    if pending is not None and approval is not None:
        # both exist (PENDING_APPROVAL added by hand): move everything to it
        Booking.objects.filter(status=pending).update(status=approval)
        BookingHistory.objects.filter(from_status=pending).update(from_status=approval)
        BookingHistory.objects.filter(to_status=pending).update(to_status=approval)
        pending.delete()
    elif pending is not None:
        pending.code = "PENDING_APPROVAL"
        pending.save(update_fields=["code"])

    for position, (code, name, value) in enumerate(BOOKING_STATUSES):
        definition = values.filter(code=code).first()
        # a value number used by another value of the list is left empty
        if values.filter(value=value).exclude(code=code).exists():
            value = None
        if definition is None:
            EnumDefinition.objects.create(
                enum_type=enum_type,
                code=code,
                name=name,
                value=value,
                position=position,
                is_system=True,
                is_active=True,
            )
        else:
            definition.name = name
            definition.position = position
            definition.is_system = True
            definition.is_active = True
            if definition.value is None:
                definition.value = value
            definition.save(
                update_fields=["name", "position", "is_system", "is_active", "value"]
            )


def unseed(apps, schema_editor):
    EnumDefinition = apps.get_model("core", "EnumDefinition")
    values = EnumDefinition.objects.filter(enum_type__code="BOOKING_STATUS")

    # new values no booking uses are removed; used ones are kept (not system any more)
    for definition in values.filter(code__in=NEW_CODES):
        used = (
            definition.bookings.exists()
            or apps.get_model("core", "BookingHistory")
            .objects.filter(to_status=definition)
            .exists()
            or apps.get_model("core", "BookingHistory")
            .objects.filter(from_status=definition)
            .exists()
        )
        if used:
            definition.is_system = False
            definition.save(update_fields=["is_system"])
        else:
            definition.delete()

    values.filter(code="PENDING_APPROVAL").update(code="PENDING", name="Pending")
    for position, code in enumerate(["PENDING", "CONFIRMED", "CANCELLED", "COMPLETED"]):
        values.filter(code=code).update(position=position)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_booking_history_applied_config"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
