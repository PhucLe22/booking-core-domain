import os
import re
import shutil
from datetime import datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from typing import List

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Model, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, inline_serializer
from PIL import Image
from rest_framework import exceptions, serializers, status
from rest_framework.exceptions import NotFound, ParseError
from rest_framework.response import Response

from core.constant import (
    DIR_TO_UPLOAD_MAPPER,
    PERMISSIONS_LIST,
    UI_PERMISSION_MAPPING,
    UNAUTHENTICATED_MESSAGE,
)


def response_success(data=None, message="", status_code=status.HTTP_200_OK):
    return Response(
        {
            "status": True,
            "data": data if data is not None else {},
            "message": message,
        },
        status=status_code,
    )


def response_errors(errors, status_code=status.HTTP_400_BAD_REQUEST):
    # data keeps the full per-field errors, message is the first one for display
    return Response(
        {
            "status": False,
            "data": errors,
            "message": extract_first_error_message(errors),
        },
        status=status_code,
    )


def convert_to_dict(error_list):
    if isinstance(error_list, list):
        error_dict = {}
        for error in error_list:
            if isinstance(error, dict):
                error_dict.update(error)
        return error_dict
    return error_list


def format_response(errors):
    error_message = next(iter(errors.values()))[0]
    return error_message


def end_of_today():
    return timezone.now().replace(hour=24, minute=59, second=59, microsecond=59)


def update_name_with_count(model, name, obj):
    """
    Updates the name of a model instance by appending a count of objects
    with the same name excluding the given object_id.
    """
    # Count the number of objects with the same name excluding the current object
    count_global = model.global_objects.filter(
        Q(name__regex=f"^{name}\\(\\d*\\)$") | Q(name=name)
    ).count()
    count = model.objects.filter(
        Q(name__regex=f"^{name}\\(\\d*\\)$") | Q(name=name)
    ).count()
    count_deleted = model.deleted_objects.filter(
        Q(name__regex=f"^{name}\\(\\d*\\)$") | Q(name=name)
    ).count()

    if count == 0 or count_global < 1:
        return

    if count_global > 1:
        obj.name = f"{obj.name}({str(count_global - count_deleted)})"
        obj.save()
    elif count_global == 0:
        return Response(
            {"status": False, "message": "Name is invalid value!"},
            status=status.HTTP_400_BAD_REQUEST,
        )


def convert_to_snake_case(text):
    if isinstance(text, str):
        text = text.strip()
        text = re.sub(r"[^a-zA-Z0-9._-]", "_", text)
        text = text.lower()
    return text


def upload_to_directory(instance, filename):
    # Build storage paths based on instance information
    identify_code = convert_to_snake_case(
        getattr(instance, DIR_TO_UPLOAD_MAPPER[instance.__class__.__name__.lower()])
    )
    # uploads/device/MC1/file_xxxx.jpg
    return f"uploads/{instance.__class__.__name__.lower()}/{identify_code}/{filename}"


def process_image(path):
    img = Image.open(path)
    return img.resize((800, 800))  # Resize image 800x800


def snake_to_lowercase(name):
    return name.replace("_", "")


def get_instance(model: Model, pk: int = None):
    try:
        instance = model.objects.get(pk=pk)
        return instance
    except model.DoesNotExist:
        raise NotFound(f"No {model.__name__} matches the given query!")
    except ValueError:
        raise ParseError(f"Invalid {model.__name__} ID!")


def get_deleted_instance(model: Model, pk: int = None):
    try:
        instance = model.deleted_objects.get(pk=pk)
        return instance
    except model.DoesNotExist:
        raise NotFound(f"No {model.__name__} matches the given query!")
    except ValueError:
        raise ParseError(f"Invalid {model.__name__} ID!")


def get_global_instance(model: Model, pk: int = None):
    try:
        instance = model.global_objects.get(pk=pk)
        return instance
    except model.DoesNotExist:
        raise NotFound(f"No {model.__name__} matches the given query!")
    except ValueError:
        raise ParseError(f"Invalid {model.__name__} ID!")


def calculate_average_percent(list):
    if list.count() == 0:
        return 0.00

    total_percent = sum(Decimal(item.completion_percent) for item in list)
    average_percent = total_percent / list.count()

    return round(float(average_percent), 2)


def path_is_excluded(current_route, list) -> bool:
    return any(current_route.startswith(path) for path in list)


def validate_max_length(value, max_length, field_name):
    if value and len(value) > max_length:
        raise serializers.ValidationError(
            f"{field_name} exceeds maximum length of {max_length} characters!"
        )
    return value


def format_date_filter(date_from: str, date_to: str) -> List[str]:
    try:
        target_date_from = datetime.strptime(date_from, "%Y-%m-%d").date()
        target_date_to = datetime.strptime(date_to, "%Y-%m-%d").date()
    except ValueError:
        raise ParseError("Date is not match format yyyy-mm-dd")

    start_of_day = datetime.combine(target_date_from, datetime.min.time())  # 00:00:00
    end_of_day = datetime.combine(
        target_date_to, datetime.max.time()
    )  # 23:59:59.999999

    # Ensure the format matches the expected format: "YYYY-MM-DD HH:MM:SS.ffffff+00:00"
    start_of_day_str = start_of_day.strftime("%Y-%m-%d %H:%M:%S.%f%z")
    end_of_day_str = end_of_day.strftime("%Y-%m-%d %H:%M:%S.%f%z")
    return [start_of_day_str, end_of_day_str]


def convert_bin_to_hex(bin_number):
    return hex(int(bin_number, 2))[2:].upper()


def convert_hex_to_bin(hex_number):
    return bin(int(hex_number, 16))[2:].zfill(len(PERMISSIONS_LIST))


def is_hex(value):
    pattern = r"^[0-9A-Fa-f]+$"
    return bool(re.match(pattern, value))


def check_permissions_by_hex(hex_num, id_permission) -> bool:
    bin_num = convert_hex_to_bin(hex_num)
    return bool(int(bin_num[-int(id_permission)]))


def get_current_shift_start(current_time):
    # Determine the start time of the current shift
    hour = current_time.hour

    # Day shift: 8:00 - 20:00, night shift: 20:00 - 8:00
    if 8 <= hour < 20:
        # Day shift
        return current_time.replace(hour=8, minute=0, second=0, microsecond=0)
    else:
        # Night shift
        if hour < 8:
            # If it's after midnight but before 8:00 AM
            return (current_time - timedelta(days=1)).replace(
                hour=20, minute=0, second=0, microsecond=0
            )
        else:
            # If it's after 8:00 PM
            return current_time.replace(hour=20, minute=0, second=0, microsecond=0)


def get_start_of_shift():
    return get_current_shift_start(datetime.now()).strftime("%Y-%m-%d %H:%M:%S")


def get_start_of_day():
    return (
        datetime.now()
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .strftime("%Y-%m-%d %H:%M:%S")
    )


def get_start_of_week():
    return (
        (datetime.now() - timedelta(days=datetime.now().weekday()))
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .strftime("%Y-%m-%d %H:%M:%S")
    )


def get_start_of_month():
    return (
        datetime.now()
        .replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        .strftime("%Y-%m-%d %H:%M:%S")
    )


def fix_vector(vector, dim=10000):
    vector = vector[:dim]
    return vector + [0.0] * (dim - len(vector))


def check_ui_permission(user, ui_permission_key):
    """
    Check whether the user has a specific UI permission
    (UI_PERMISSION_MAPPING maps a UI key to a Permission code).
    """
    if ui_permission_key not in UI_PERMISSION_MAPPING:
        return False

    permission_code = UI_PERMISSION_MAPPING[ui_permission_key]
    return user.roles.filter(
        is_active=True, permissions__code=permission_code
    ).exists()


def get_access_token_from_request(request):
    """
    Extracts the JWT token from the request header.
    Assumes the token is in the Authorization header.
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def extract_first_error_message(errors):
    """
    Extract the first error message from nested serializer errors structure
    """
    if isinstance(errors, dict):
        for key, value in errors.items():
            if isinstance(value, dict):
                result = extract_first_error_message(value)
                if result:
                    return result
            elif isinstance(value, list) and value:
                if isinstance(value[0], str):
                    return value[0]
                else:
                    result = extract_first_error_message(value[0])
                    if result:
                        return result
    elif isinstance(errors, list) and errors:
        if isinstance(errors[0], str):
            return errors[0]
        else:
            return extract_first_error_message(errors[0])
    return None


def global_response_errors(errors):
    error_message = extract_first_error_message(errors)
    return Response({
        "status": False,
        "message": error_message
        },status=status.HTTP_400_BAD_REQUEST)


# =========================================================
# WEB API ERRORS – same format as response_success / response_errors
# =========================================================
# Add WebApiMixin before viewsets.ViewSet to turn it on for a viewset; other views keep
# the old error handler (core/exceptions.py). Every error answers
#
#     {"status": false, "data": {<field>: [<message>]} or {}, "message": "<first error>"}
#
# with the HTTP status telling the kind of error: 401, 403, 404, 405..., 409 (business
# conflict) or 422 (invalid data). Business errors are raised from serializers with the
# DRF error code, eg serializers.ValidationError({"start_at": "..."}, code="slot_taken").
# success_response / error_responses describe these formats in documents.py.

# DRF error code given in a serializer -> HTTP status (other validation errors: 422)
ERROR_CODE_STATUS = {
    "slot_taken": status.HTTP_409_CONFLICT,
    "invalid_transition": status.HTTP_409_CONFLICT,
    "stale_version": status.HTTP_409_CONFLICT,
    "booking_denied": status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def error_codes(detail):
    """Every DRF error code inside a ValidationError detail."""
    if isinstance(detail, dict):
        return set().union(*(error_codes(value) for value in detail.values()))
    if isinstance(detail, list):
        return set().union(*(error_codes(item) for item in detail))
    return {getattr(detail, "code", None)}


def web_api_exception_handler(exc, context):
    # imported here: core.utils is loaded while rest_framework.views reads
    # DEFAULT_PERMISSION_CLASSES (core.permissions -> core.utils), a top-level import
    # of rest_framework.views would be circular
    from rest_framework.views import exception_handler

    # an invalid UUID in the URL raises a Django error: it cannot match any record
    if isinstance(exc, DjangoValidationError):
        exc = exceptions.NotFound("No record matches the given query!")

    response = exception_handler(exc, context)
    if response is None:  # unexpected error: 500 as before
        return None

    data, message = {}, str(getattr(exc, "detail", exc))
    if isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
        # one plain sentence: simplejwt puts a dict of token details in exc.detail
        response.status_code = status.HTTP_401_UNAUTHORIZED
        message = UNAUTHENTICATED_MESSAGE
    elif isinstance(exc, exceptions.ValidationError):
        codes = error_codes(exc.detail)
        response.status_code = next(
            (http for code, http in ERROR_CODE_STATUS.items() if code in codes),
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
        data, message = exc.detail, extract_first_error_message(exc.detail) or str(exc)
    elif isinstance(exc, exceptions.ParseError):  # eg malformed JSON
        response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY

    response.data = {"status": False, "data": data, "message": message}
    return response


class WebApiMixin:
    """Errors of this viewset as {status: false, data, message} (see above)."""

    def get_exception_handler(self):
        return web_api_exception_handler


# =========================================================
# SWAGGER (drf-spectacular) – used in documents.py
# =========================================================

# kind of error -> (HTTP status, field of the example error or None, example message)
ERROR_EXAMPLES = {
    "UNAUTHENTICATED": (401, None, UNAUTHENTICATED_MESSAGE),
    "FORBIDDEN": (403, None, "You do not have permission to perform this action!"),
    "NOT_FOUND": (404, None, "No record matches the given query!"),
    "SLOT_TAKEN": (409, "start_at", "Resource is already booked for this time!"),
    "INVALID_TRANSITION": (
        409,
        "status",
        "Booking cannot change from Cancelled to Confirmed!",
    ),
    "STALE_VERSION": (
        409,
        "base_version",
        "Resource type was changed by someone else (now version 2), reload it!",
    ),
    "VALIDATION_FAILED": (422, "start_at", "Please enter start time!"),
    "BOOKING_DENIED": (422, "non_field_errors", "Guests can book at most 2 hours"),
}


def error_example(kind):
    """Example body of one kind of error: {status: false, data, message}."""
    http_status, field, message = ERROR_EXAMPLES[kind]
    return OpenApiExample(
        kind.replace("_", " ").capitalize(),
        value={
            "status": False,
            "data": {field: [message]} if field else {},
            "message": message,
        },
        response_only=True,
        status_codes=[str(http_status)],
    )


# every API that needs a login can answer these
AUTH_ERRORS = ("UNAUTHENTICATED", "FORBIDDEN")

ERROR_SCHEMA = inline_serializer(
    name="ErrorResponse",
    fields={
        "status": serializers.BooleanField(help_text="always false"),
        "data": serializers.DictField(
            help_text="errors per field, {} when not about fields"
        ),
        "message": serializers.CharField(help_text="first error, to show to the user"),
    },
)

PAGINATION_SCHEMA = inline_serializer(
    name="Pagination",
    fields={
        "total_items": serializers.IntegerField(),
        "page_size": serializers.IntegerField(),
        "current_page": serializers.IntegerField(),
        "total_pages": serializers.IntegerField(),
        "next_page": serializers.URLField(allow_null=True),
        "previous_page": serializers.URLField(allow_null=True),
    },
)


def error_responses(*kinds):
    """
    Error responses for `responses` of extend_schema, grouped by HTTP status, eg
    {**error_responses(*AUTH_ERRORS, "NOT_FOUND", "VALIDATION_FAILED")}.
    """
    by_status = {}
    for kind in kinds:
        by_status.setdefault(ERROR_EXAMPLES[kind][0], []).append(kind)
    return {
        http_status: OpenApiResponse(
            response=ERROR_SCHEMA,
            description=" / ".join(status_kinds),
            examples=[error_example(kind) for kind in status_kinds],
        )
        for http_status, status_kinds in by_status.items()
    }


@lru_cache(maxsize=None)
def success_response(serializer_class=None, shape="object"):
    """
    Schema of response_success / CustomPaginator for `responses` of extend_schema:
    {status, data, message}, data being
      shape="object": one serializer_class (or {} when serializer_class is None)
      shape="list":   a list of serializer_class
      shape="page":   a list of serializer_class, plus "pagination"
    Cached: one schema component per (serializer, shape).
    """
    if serializer_class is None:
        name, data = "EmptyResponse", serializers.DictField(help_text="always {}")
    else:
        suffix = {
            "object": "Response",
            "list": "ListResponse",
            "page": "PageResponse",
        }[shape]
        name = serializer_class.__name__.removesuffix("Serializer") + suffix
        data = serializer_class(many=shape != "object")
    fields = {
        "status": serializers.BooleanField(),
        "data": data,
        "message": serializers.CharField(),
    }
    if shape == "page":
        fields["pagination"] = PAGINATION_SCHEMA
    return inline_serializer(name=name, fields=fields)
