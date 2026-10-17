from rest_framework import serializers

from core.constant import BOOKING_TRANSITIONS, BookingStatus
from core.models import Booking, Resource, User

from .fields import CodeRelatedField, enum_values

# bookings in these statuses hold their time slot
ACTIVE_BOOKING_STATUSES = [BookingStatus.PENDING, BookingStatus.CONFIRMED]
# a new booking can only start in one of these statuses
INITIAL_BOOKING_STATUSES = [BookingStatus.PENDING, BookingStatus.CONFIRMED]
DEFAULT_BOOKING_STATUS = BookingStatus.CONFIRMED


class BookingSerializer(serializers.ModelSerializer):
    status = serializers.CharField(source="status.code", read_only=True)
    status_name = serializers.CharField(source="status.name", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id",
            "resource",
            "user",
            "guest_name",
            "guest_email",
            "guest_phone",
            "start_at",
            "end_at",
            "status",
            "status_name",
            "title",
            "description",
            "configuration",
            "created_at",
        ]


class EditBookingSerializer(serializers.ModelSerializer):
    resource = serializers.PrimaryKeyRelatedField(
        queryset=Resource.objects.all(),
        pk_field=serializers.UUIDField(
            error_messages={"invalid": "Resource ID is not a valid UUID!"}
        ),
        error_messages={
            "required": "Please select a resource!",
            "null": "Resource cannot be empty!",
            "does_not_exist": "Resource does not exist!",
        },
    )
    start_at = serializers.DateTimeField(
        error_messages={
            "required": "Please enter start time!",
            "null": "Start time cannot be empty!",
            "invalid": "Start time is not a valid datetime!",
        },
    )
    end_at = serializers.DateTimeField(
        error_messages={
            "required": "Please enter end time!",
            "null": "End time cannot be empty!",
            "invalid": "End time is not a valid datetime!",
        },
    )
    status = CodeRelatedField(
        queryset=enum_values("BOOKING_STATUS"),
        required=False,
        error_messages={
            "null": "Booking status cannot be empty!",
            "does_not_exist": "Booking status '{value}' does not exist!",
        },
    )
    title = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True,
        error_messages={
            "max_length": "Title cannot exceed 255 characters!",
        },
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    class Meta:
        model = Booking
        fields = [
            "id",
            "resource",
            "user",
            "start_at",
            "end_at",
            "status",
            "title",
            "description",
            "configuration",
            "created_at",
        ]
        # user comes from the access token, never from the request body
        read_only_fields = ["id", "user", "created_at"]

    def validate(self, data):
        instance = self.instance
        status = self.validate_status_change(instance, data.get("status"))
        data["status"] = status

        resource = data.get("resource", getattr(instance, "resource", None))
        start_at = data.get("start_at", getattr(instance, "start_at", None))
        end_at = data.get("end_at", getattr(instance, "end_at", None))

        if end_at <= start_at:
            raise serializers.ValidationError(
                {"end_at": "End time must be after start time!"}
            )

        if not resource.is_bookable:
            raise serializers.ValidationError(
                {"resource": "Resource is not available for booking!"}
            )

        if status.code in ACTIVE_BOOKING_STATUSES:
            # lock the resource row so two requests cannot book the same slot
            # at the same time (the view runs inside transaction.atomic)
            Resource.objects.select_for_update().filter(pk=resource.pk).first()
            overlapping = Booking.objects.filter(
                resource=resource,
                status__code__in=ACTIVE_BOOKING_STATUSES,
                start_at__lt=end_at,
                end_at__gt=start_at,
            )
            if instance is not None:
                overlapping = overlapping.exclude(pk=instance.pk)
            if overlapping.exists():
                raise serializers.ValidationError(
                    {"start_at": "Resource is already booked for this time!"}
                )

        return data

    def validate_status_change(self, instance, new_status):
        """Return the booking status after this request, or raise."""
        if instance is None:
            if new_status is None:
                new_status = (
                    enum_values("BOOKING_STATUS")
                    .filter(code=DEFAULT_BOOKING_STATUS)
                    .first()
                )
                if new_status is None:
                    raise serializers.ValidationError(
                        {
                            "status": [
                                f"Booking status {DEFAULT_BOOKING_STATUS} "
                                "is not configured!"
                            ]
                        }
                    )
            elif new_status.code not in INITIAL_BOOKING_STATUSES:
                raise serializers.ValidationError(
                    {"status": ["A new booking can only be Pending or Confirmed!"]}
                )
            return new_status

        current = instance.status
        allowed = BOOKING_TRANSITIONS.get(current.code, [])
        if not allowed:
            raise serializers.ValidationError(
                {
                    "status": [
                        f"Booking is {current.name.lower()} "
                        "and can no longer be changed!"
                    ]
                }
            )
        if new_status is None or new_status == current:
            return current
        if new_status.code not in allowed:
            raise serializers.ValidationError(
                {
                    "status": [
                        f"Booking cannot change from {current.name} "
                        f"to {new_status.name}!"
                    ]
                }
            )
        return new_status


class GuestBookingSerializer(EditBookingSerializer):
    guest_name = serializers.CharField(
        max_length=255,
        error_messages={
            "required": "Please enter your name!",
            "blank": "Name cannot be empty!",
            "max_length": "Name cannot exceed 255 characters!",
        },
    )
    guest_email = serializers.EmailField(
        max_length=255,
        error_messages={
            "required": "Please enter your email!",
            "blank": "Email cannot be empty!",
            "invalid": "Enter a valid email address!",
            "max_length": "Email cannot exceed 255 characters!",
        },
    )
    guest_phone = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True,
        error_messages={
            "max_length": "Phone number cannot exceed 20 characters!",
        },
    )

    class Meta(EditBookingSerializer.Meta):
        fields = EditBookingSerializer.Meta.fields + [
            "guest_name",
            "guest_email",
            "guest_phone",
        ]


class StaffBookingSerializer(EditBookingSerializer):
    """Booking created by staff for a registered customer or for a guest."""

    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
        error_messages={
            "does_not_exist": "User does not exist!",
            "incorrect_type": "User ID must be a number!",
        },
    )
    guest_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True,
        error_messages={
            "max_length": "Name cannot exceed 255 characters!",
        },
    )
    guest_email = serializers.EmailField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True,
        error_messages={
            "invalid": "Enter a valid email address!",
            "max_length": "Email cannot exceed 255 characters!",
        },
    )
    guest_phone = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True,
        error_messages={
            "max_length": "Phone number cannot exceed 20 characters!",
        },
    )

    class Meta(EditBookingSerializer.Meta):
        fields = EditBookingSerializer.Meta.fields + [
            "guest_name",
            "guest_email",
            "guest_phone",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, data):
        user = data.get("user")
        guest_name = data.get("guest_name")
        guest_email = data.get("guest_email")

        if user and (guest_name or guest_email):
            raise serializers.ValidationError(
                {"user": "Select a customer or enter guest details, not both!"}
            )
        if not user:
            errors = {}
            if not guest_name:
                errors["guest_name"] = "Please select a customer or enter guest name!"
            if not guest_email:
                errors["guest_email"] = (
                    "Please select a customer or enter guest email!"
                )
            if errors:
                raise serializers.ValidationError(errors)

        return super().validate(data)


class CalendarBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        # no guest contact details: the calendar is visible to every user
        fields = ["id", "user", "title", "start_at", "end_at", "status", "status_name"]

    status = serializers.CharField(source="status.code", read_only=True)
    status_name = serializers.CharField(source="status.name", read_only=True)


class CalendarDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    bookings = CalendarBookingSerializer(many=True)


class ResourceCalendarSerializer(serializers.ModelSerializer):
    resource_type_code = serializers.CharField(source="resource_type.code")
    calendar = CalendarDaySerializer(many=True)

    class Meta:
        model = Resource
        fields = [
            "id",
            "code",
            "name",
            "status",
            "resource_type",
            "resource_type_code",
            "calendar",
        ]
