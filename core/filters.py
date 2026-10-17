from datetime import datetime, time, timedelta

from django.db.models import Q
from django_filters import rest_framework as filters
from core.models import (
    Booking,
    EnumDefinition,
    FileAttachment,
    Folder,
    Notification,
    Resource,
    ResourceType,
    StoredFile,
    User,
)

class ResourceFilter(filters.FilterSet):
    resource_type = filters.UUIDFilter(
        field_name="resource_type",
        error_messages={"invalid": "Resource type ID is not a valid UUID!"},
    )
    resource_type_code = filters.CharFilter(field_name="resource_type__code")
    status = filters.CharFilter(field_name="status__code", lookup_expr="iexact")

    class Meta:
        model = Resource
        fields = {
            "code": ["exact", "icontains"],
            "name": ["exact", "icontains"],
        }


class ResourceTypeFilter(filters.FilterSet):
    class Meta:
        model = ResourceType
        fields = {
            "code": ["exact", "icontains"],
            "name": ["exact", "icontains"],
        }


class BookingFilter(filters.FilterSet):
    resource = filters.UUIDFilter(
        field_name="resource",
        error_messages={"invalid": "Resource ID is not a valid UUID!"},
    )
    resource_type = filters.UUIDFilter(
        field_name="resource__resource_type",
        error_messages={"invalid": "Resource type ID is not a valid UUID!"},
    )
    resource_type_code = filters.CharFilter(field_name="resource__resource_type__code")
    user = filters.NumberFilter(
        field_name="user",
        error_messages={"invalid": "User ID must be a number!"},
    )
    # bookings that overlap the [from_time, to_time] range
    from_time = filters.DateTimeFilter(
        field_name="end_at",
        lookup_expr="gt",
        error_messages={"invalid": "From time is not a valid datetime!"},
    )
    to_time = filters.DateTimeFilter(
        field_name="start_at",
        lookup_expr="lt",
        error_messages={"invalid": "To time is not a valid datetime!"},
    )

    status = filters.CharFilter(field_name="status__code", lookup_expr="iexact")

    class Meta:
        model = Booking
        fields = {
            "title": ["icontains"],
        }


class BookingCalendarFilter(filters.FilterSet):
    """
    Filters the bookings shown on the calendar and holds the calendar date
    range (start_date..end_date, both inclusive).
    """

    MAX_DAYS = 31

    start_date = filters.DateFilter(
        method="filter_start_date",
        required=True,
        error_messages={
            "required": "Please enter start date!",
            "invalid": "Start date is not a valid date!",
        },
    )
    end_date = filters.DateFilter(
        method="filter_end_date",
        required=True,
        error_messages={
            "required": "Please enter end date!",
            "invalid": "End date is not a valid date!",
        },
    )
    resource = filters.UUIDFilter(
        field_name="resource",
        error_messages={"invalid": "Resource ID is not a valid UUID!"},
    )
    resource_type = filters.UUIDFilter(
        field_name="resource__resource_type",
        error_messages={"invalid": "Resource type ID is not a valid UUID!"},
    )
    resource_type_code = filters.CharFilter(field_name="resource__resource_type__code")

    class Meta:
        model = Booking
        fields = []

    def filter_start_date(self, queryset, name, value):
        # bookings that end after the first day starts
        return queryset.filter(end_at__gt=datetime.combine(value, time.min))

    def filter_end_date(self, queryset, name, value):
        # bookings that start before the day after the last day
        return queryset.filter(
            start_at__lt=datetime.combine(value + timedelta(days=1), time.min)
        )

    def is_valid(self):
        if not super().is_valid():
            return False
        start_date, end_date = self.get_calendar_range()
        if end_date < start_date:
            self.form.add_error("end_date", "End date must be on or after start date!")
        elif (end_date - start_date).days + 1 > self.MAX_DAYS:
            self.form.add_error(
                "end_date", f"Calendar range cannot exceed {self.MAX_DAYS} days!"
            )
        return not self.form.errors

    def get_calendar_range(self):
        if not self.is_bound or not hasattr(self.form, "cleaned_data"):
            return None, None
        return (
            self.form.cleaned_data.get("start_date"),
            self.form.cleaned_data.get("end_date"),
        )


class NotificationFilter(filters.FilterSet):
    class Meta:
        model = Notification
        # define field search ex: name=xxx, id=yyy
        fields = {
            "is_read": ["exact"],
        }


class UserFilter(filters.FilterSet):
    username = filters.CharFilter(field_name="username", lookup_expr="icontains")
    # matches first name or last name
    name = filters.CharFilter(method="filter_name")
    role = filters.CharFilter(field_name="roles__code", distinct=True)
    status = filters.BooleanFilter(field_name="status")

    class Meta:
        model = User
        fields = []

    def filter_name(self, queryset, name, value):
        return queryset.filter(
            Q(first_name__icontains=value) | Q(last_name__icontains=value)
        )


class FolderFilter(filters.FilterSet):
    parent = filters.UUIDFilter(
        field_name="parent",
        error_messages={"invalid": "Parent folder ID is not a valid UUID!"},
    )
    # true: only top level folders
    is_root = filters.BooleanFilter(field_name="parent", lookup_expr="isnull")
    name = filters.CharFilter(field_name="name", lookup_expr="icontains")

    class Meta:
        model = Folder
        fields = []


class StoredFileFilter(filters.FilterSet):
    folder = filters.UUIDFilter(
        field_name="folder",
        error_messages={"invalid": "Folder ID is not a valid UUID!"},
    )
    # true: only files that are not in a folder
    is_root = filters.BooleanFilter(field_name="folder", lookup_expr="isnull")
    name = filters.CharFilter(field_name="original_name", lookup_expr="icontains")
    extension = filters.CharFilter(field_name="extension", lookup_expr="iexact")

    class Meta:
        model = StoredFile
        fields = []


class FileAttachmentFilter(filters.FilterSet):
    object_type = filters.CharFilter(method="filter_object_type")
    object_id = filters.CharFilter(field_name="object_id")
    file = filters.UUIDFilter(
        field_name="file",
        error_messages={"invalid": "File ID is not a valid UUID!"},
    )
    purpose = filters.CharFilter(field_name="purpose")

    class Meta:
        model = FileAttachment
        fields = []

    def filter_object_type(self, queryset, name, value):
        # object_type uses the API names, eg: resource_type -> resourcetype
        return queryset.filter(content_type__model=value.replace("_", ""))


class EnumDefinitionFilter(filters.FilterSet):
    enum_type = filters.CharFilter(field_name="enum_type__code", lookup_expr="iexact")
    code = filters.CharFilter(field_name="code", lookup_expr="iexact")
    is_active = filters.BooleanFilter(field_name="is_active")

    class Meta:
        model = EnumDefinition
        fields = []

