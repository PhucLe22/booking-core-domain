from drf_spectacular.utils import OpenApiParameter

from core.serializers.booking_serializers import (
    BookingSerializer,
    EditBookingSerializer,
    GuestBookingSerializer,
    ResourceCalendarSerializer,
    StaffBookingSerializer,
)

booking_id_parameter = OpenApiParameter(
    "id",
    type=str,
    location=OpenApiParameter.PATH,
    description="UUID of the booking",
)

list_booking_description = {
    "summary": "Get list of all bookings",
    "description": "get list of all bookings and filter eg: http://localhost:9015/api/v1/bookings/?resource_type_code=MEETING_ROOM&from_time=2026-10-08T00:00:00&to_time=2026-10-09T00:00:00",
    "parameters": [
        OpenApiParameter(
            "page", int, required=False, default=1, description="Page number"
        ),
        OpenApiParameter(
            "page_size",
            int,
            required=False,
            default=5,
            description="Number of bookings per page.",
        ),
        OpenApiParameter(
            "resource", str, required=False, description="Filter by resource ID (UUID)"
        ),
        OpenApiParameter(
            "resource_type",
            str,
            required=False,
            description="Filter by resource type ID (UUID)",
        ),
        OpenApiParameter(
            "resource_type_code",
            str,
            required=False,
            description="Filter by resource type code",
        ),
        OpenApiParameter("user", int, required=False, description="Filter by user ID"),
        OpenApiParameter(
            "status",
            str,
            required=False,
            description="Status code: PENDING, CONFIRMED, CANCELLED, COMPLETED",
        ),
        OpenApiParameter(
            "title__icontains", str, required=False, description="Title contains"
        ),
        OpenApiParameter(
            "from_time",
            str,
            required=False,
            description="Bookings that end after this time, eg: 2026-10-08T00:00:00",
        ),
        OpenApiParameter(
            "to_time",
            str,
            required=False,
            description="Bookings that start before this time, eg: 2026-10-09T00:00:00",
        ),
    ],
    "responses": {200: BookingSerializer(many=True)},
}

list_my_booking_description = {
    "summary": "Get list of my bookings",
    "description": "get list of bookings of the logged in user and filter eg: http://localhost:9015/api/v1/bookings/me/?resource_type_code=MEETING_ROOM&from_time=2026-10-08T00:00:00&to_time=2026-10-09T00:00:00",
    "parameters": [
        OpenApiParameter(
            "page", int, required=False, default=1, description="Page number"
        ),
        OpenApiParameter(
            "page_size",
            int,
            required=False,
            default=5,
            description="Number of bookings per page.",
        ),
        OpenApiParameter(
            "resource", str, required=False, description="Filter by resource ID (UUID)"
        ),
        OpenApiParameter(
            "resource_type",
            str,
            required=False,
            description="Filter by resource type ID (UUID)",
        ),
        OpenApiParameter(
            "resource_type_code",
            str,
            required=False,
            description="Filter by resource type code, eg: MEETING_ROOM",
        ),
        OpenApiParameter(
            "status",
            str,
            required=False,
            description="Status code: PENDING, CONFIRMED, CANCELLED, COMPLETED",
        ),
        OpenApiParameter(
            "title__icontains", str, required=False, description="Title contains"
        ),
        OpenApiParameter(
            "from_time",
            str,
            required=False,
            description="Bookings that end after this time, eg: 2026-10-08T00:00:00",
        ),
        OpenApiParameter(
            "to_time",
            str,
            required=False,
            description="Bookings that start before this time, eg: 2026-10-09T00:00:00",
        ),
    ],
    "responses": {200: BookingSerializer(many=True)},
}

retrieve_booking_description = {
    "parameters": [booking_id_parameter],
    "summary": "Get booking detail",
    "description": "Get booking detail",
    "responses": {200: BookingSerializer},
}

create_booking_description = {
    "summary": "Create booking (logged in customer)",
    "description": "Create a new booking for the logged in user. The user is taken from the access token.",
    "request": EditBookingSerializer,
    "responses": {201: BookingSerializer},
}

update_booking_description = {
    "parameters": [booking_id_parameter],
    "summary": "Update booking",
    "description": "Update an existing booking",
    "request": EditBookingSerializer,
    "responses": {200: BookingSerializer},
}

delete_booking_description = {
    "parameters": [booking_id_parameter],
    "summary": "Delete booking",
    "description": "Delete a booking",
    "responses": {200: None},
}

create_guest_booking_description = {
    "summary": "Create booking (guest)",
    "description": "Create a new booking without logging in. Guest name and email are required.",
    "request": GuestBookingSerializer,
    "responses": {201: BookingSerializer},
    "auth": [],
}

create_staff_booking_description = {
    "summary": "Create booking (staff)",
    "description": "Staff creates a booking for a customer (send `user`) or a guest (send `guest_name` and `guest_email`). Requires an admin or staff account.",
    "request": StaffBookingSerializer,
    "responses": {201: BookingSerializer},
}

get_booking_calendar_description = {
    "summary": "Get booking calendar",
    "description": "Get bookings per resource per day (cancelled bookings are hidden), eg: http://localhost:9015/api/v1/calendars/?start_date=2026-10-20&end_date=2026-10-26&resource_type_code=MEETING_ROOM",
    "parameters": [
        OpenApiParameter(
            "start_date",
            str,
            required=True,
            description="First day of the calendar, eg: 2026-10-20",
        ),
        OpenApiParameter(
            "end_date",
            str,
            required=True,
            description="Last day of the calendar (max 31 days), eg: 2026-10-26",
        ),
        OpenApiParameter(
            "resource", str, required=False, description="Filter by resource ID (UUID)"
        ),
        OpenApiParameter(
            "resource_type",
            str,
            required=False,
            description="Filter by resource type ID (UUID)",
        ),
        OpenApiParameter(
            "resource_type_code",
            str,
            required=False,
            description="Filter by resource type code, eg: MEETING_ROOM",
        ),
    ],
    "responses": {200: ResourceCalendarSerializer(many=True)},
}
