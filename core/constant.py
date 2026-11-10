import re
from enum import Enum

USER_DEFAULT_SYSTEM = 3
MAX_IMAGE_SIZE = 3 * 1024 * 1024
ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"]
EXCLUDE_AUTH_PATH = [
    "api/v1/auth/login",
    "api/v1/auth/register",
    "api/v1/auth/refresh",
]

EXCLUDE_ACTIVE_PATH = [
    *EXCLUDE_AUTH_PATH,
    "api/v1/auth/logout",
    "api/v1/users/request_active_account",
    "api/v1/notifications/",
    "api/v1/users/",
    "api/v1/auth/me/",
]

# message of every 401 answered by core.utils.WebApiMixin
# (missing, invalid or expired token)
UNAUTHENTICATED_MESSAGE = "You are not authenticated, please log in again!"


class NotificationTypeEnum(Enum):
    # system notification 1-20
    SYSTEM_NOTIFICATION = 1
    # define here


PERMISSIONS_LIST = []

permissions_enum_dict = {
    name.upper().replace(" ", "_"): idx + 1
    for idx, name in enumerate(PERMISSIONS_LIST)
    if "future use" not in name.lower()
}

PermissionsEnum = Enum("PermissionsEnum", permissions_enum_dict)


UI_PERMISSION_MAPPING = {}
DEFAULT_PERMISSION_CLASSES = 2

DIR_TO_UPLOAD_MAPPER = {"user": "pk"}


class LabelEnum(Enum):
    def __new__(cls, value, label):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.label = label
        return obj

    @classmethod
    def choices(cls):
        return [
            (item.value, item.label)
            for item in cls
        ]

    @classmethod
    def values(cls):
        return [
            item.value
            for item in cls
        ]

    @classmethod
    def labels(cls):
        return [
            item.label
            for item in cls
        ]

    @classmethod
    def get_label(cls, value):
        try:
            return cls(value).label
        except ValueError:
            return None


class ResourceStatusEnum(LabelEnum):
    ACTIVE = (1, "Active")
    INACTIVE = (2, "Inactive")
    MAINTENANCE = (3, "Maintenance")


class BookingStatusEnum(LabelEnum):
    CONFIRMED = (1, "Confirmed")
    PENDING = (2, "Pending")
    CANCELLED = (3, "Cancelled")
    COMPLETED = (4, "Completed")


class RoleCode:
    """Codes of the system roles seeded in the roles table."""

    ADMIN = "ADMIN"
    STAFF = "STAFF"
    CUSTOMER = "CUSTOMER"


# roles allowed to use staff APIs
STAFF_ROLE_CODES = [RoleCode.ADMIN, RoleCode.STAFF]


# enum types the code depends on: their code cannot change and they cannot be
# deleted (their seeded values are protected by EnumDefinition.is_system)
SYSTEM_ENUM_TYPES = ["RESOURCE_STATUS", "BOOKING_STATUS", "NOTIFICATION_TYPE"]


# codes of the seeded system enum values; names, numbers and order live in
# the enum_definitions table (master-data service)
# master data list a resource type takes its resource statuses from, unless
# ResourceType.configuration["status_enum_type"] names another list
DEFAULT_RESOURCE_STATUS_TYPE = "RESOURCE_STATUS"
# system lists that are not resource statuses: a resource type cannot use them
NOT_RESOURCE_STATUS_TYPES = ["BOOKING_STATUS", "NOTIFICATION_TYPE"]

# key of a resource type and of its custom fields (docs/web_api_spec.md),
# eg phone_booth, has_phone_charger
KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
KEY_PATTERN_MESSAGE = "Must match ^[a-z][a-z0-9_]*$"

# configuration["fields"] is an object {key: definition}; Postgres jsonb does not keep
# the order of its keys, so the order of the list is kept in configuration["field_order"]
FIELD_ORDER = "field_order"

FIELD_LIST_HELP = (
    'Custom fields, eg [{"key": "capacity", "label": "Capacity", "type": "integer", '
    '"required": true, "min": 1}]'
)


class ResourceStatus:
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    MAINTENANCE = "MAINTENANCE"


# codes of the BOOKING_STATUS values (docs/web_api_spec.md, seeded by migration 0010)
class BookingStatus:
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


# who changed the status of a booking (BookingHistory.actor_type, docs/web_api_spec.md)
class BookingActorType:
    USER = "user"
    SYSTEM = "system"

    CHOICES = [(USER, "User"), (SYSTEM, "System")]


# allowed booking status changes: current status -> statuses it can move to
# (the transitions of the new statuses come with the booking actions, task 2.10)
BOOKING_TRANSITIONS = {
    BookingStatus.PENDING_APPROVAL: [BookingStatus.CONFIRMED, BookingStatus.CANCELLED],
    BookingStatus.CONFIRMED: [BookingStatus.CANCELLED, BookingStatus.COMPLETED],
    BookingStatus.CANCELLED: [],
    BookingStatus.COMPLETED: [],
}
