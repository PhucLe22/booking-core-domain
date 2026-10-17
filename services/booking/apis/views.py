from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.constant import STAFF_ROLE_CODES
from core.filters import BookingCalendarFilter, BookingFilter
from core.middlewares.login_required import LOGIN_REQUIRED
from core.middlewares.staff import StaffMiddleware
from core.models import Booking, Resource
from core.paginators import CustomPaginator
from core.serializers.booking_serializers import (
    BookingSerializer,
    EditBookingSerializer,
    GuestBookingSerializer,
    ResourceCalendarSerializer,
    StaffBookingSerializer,
)
from core.utils import response_errors, response_success

from .documents import (
    create_booking_description,
    create_guest_booking_description,
    create_staff_booking_description,
    delete_booking_description,
    get_booking_calendar_description,
    list_booking_description,
    list_my_booking_description,
    retrieve_booking_description,
    update_booking_description,
)


class BookingViewSet(viewsets.ViewSet):
    # every action requires login except "guest"
    authentication_classes = [JWTAuthentication]
    permission_classes = LOGIN_REQUIRED

    def get_own_booking(self, request, pk):
        # staff and admin can open any booking (confirm, cancel, edit for customers);
        # other users only their own, the rest are reported as not found
        bookings = Booking.objects.all()
        if not request.user.has_role(*STAFF_ROLE_CODES):
            bookings = bookings.filter(user=request.user)
        try:
            return bookings.get(pk=pk)
        except (Booking.DoesNotExist, DjangoValidationError):
            raise NotFound("No Booking matches the given query!")

    def paginated_list(self, request, queryset):
        booking_filter = BookingFilter(
            request.query_params,
            queryset=queryset.select_related(
                "resource", "resource__resource_type", "status"
            ).order_by("start_at"),
        )
        if not booking_filter.is_valid():
            return response_errors(booking_filter.errors)
        paginator = CustomPaginator()
        page = paginator.paginate_queryset(booking_filter.qs, request)
        serializer = BookingSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(**list_booking_description)
    def list(self, request):
        return self.paginated_list(request, Booking.objects.all())

    @extend_schema(**list_my_booking_description)
    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        return self.paginated_list(request, Booking.objects.filter(user=request.user))

    @extend_schema(**retrieve_booking_description)
    def retrieve(self, request, pk=None):
        booking = self.get_own_booking(request, pk)
        return response_success(BookingSerializer(booking).data)

    @extend_schema(**create_booking_description)
    @transaction.atomic
    def create(self, request):
        serializer = EditBookingSerializer(data=request.data)
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        serializer.save(user=request.user)
        return response_success(
            BookingSerializer(serializer.instance).data,
            "Booking created successfully!",
            status.HTTP_201_CREATED,
        )

    @extend_schema(**create_guest_booking_description)
    @action(
        detail=False,
        methods=["post"],
        url_path="guest",
        authentication_classes=[],
        permission_classes=[AllowAny],
    )
    @transaction.atomic
    def guest(self, request):
        serializer = GuestBookingSerializer(data=request.data)
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        serializer.save(user=None)
        return response_success(
            BookingSerializer(serializer.instance).data,
            "Booking created successfully!",
            status.HTTP_201_CREATED,
        )

    @extend_schema(**create_staff_booking_description)
    @action(
        detail=False,
        methods=["post"],
        url_path="staff",
        permission_classes=[*LOGIN_REQUIRED, StaffMiddleware],
    )
    @transaction.atomic
    def staff(self, request):
        serializer = StaffBookingSerializer(data=request.data)
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        serializer.save()
        return response_success(
            BookingSerializer(serializer.instance).data,
            "Booking created successfully!",
            status.HTTP_201_CREATED,
        )

    @extend_schema(**update_booking_description)
    @transaction.atomic
    def update(self, request, pk=None):
        booking = self.get_own_booking(request, pk)
        serializer = EditBookingSerializer(booking, data=request.data)
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        serializer.save()
        return response_success(
            BookingSerializer(serializer.instance).data,
            "Booking updated successfully!",
        )

    @extend_schema(**delete_booking_description)
    def destroy(self, request, pk=None):
        booking = self.get_own_booking(request, pk)
        booking.delete()
        return response_success(message="Booking deleted successfully!")


class CalendarViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = LOGIN_REQUIRED

    @extend_schema(**get_booking_calendar_description)
    def list(self, request):
        filter_params = request.query_params.copy()
        calendar_filter = BookingCalendarFilter(
            filter_params,
            queryset=(
                Booking.objects.displayable()
                .select_related("resource", "user", "status")
                .order_by("resource_id", "start_at")
            ),
        )
        if not calendar_filter.is_valid():
            return response_errors(calendar_filter.errors)

        start_date, end_date = calendar_filter.get_calendar_range()
        bookings = calendar_filter.qs

        if start_date is None or end_date is None:
            return response_errors({"start_date": ["Invalid calendar filter."]})

        days = (end_date - start_date).days + 1
        resources = Resource.objects.select_related("resource_type").order_by("name")

        cleaned_data = calendar_filter.form.cleaned_data
        if cleaned_data.get("resource"):
            resources = resources.filter(pk=cleaned_data["resource"])
        if cleaned_data.get("resource_type"):
            resources = resources.filter(resource_type=cleaned_data["resource_type"])
        if cleaned_data.get("resource_type_code"):
            resources = resources.filter(
                resource_type__code=cleaned_data["resource_type_code"]
            )

        # a booking is listed on every day it covers inside the range
        bookings_by_resource_date = {}
        for booking in bookings:
            first_day = max(booking.start_at.date(), start_date)
            # a booking ending exactly at midnight does not cover the next day
            last_day = min((booking.end_at - timedelta(microseconds=1)).date(), end_date)
            for offset in range((last_day - first_day).days + 1):
                bookings_by_resource_date.setdefault(
                    (booking.resource_id, first_day + timedelta(days=offset)),
                    [],
                ).append(booking)

        resources_with_calendar = []
        for resource in resources:
            calendar = [
                {
                    "date": start_date + timedelta(days=offset),
                    "bookings": bookings_by_resource_date.get(
                        (resource.id, start_date + timedelta(days=offset)),
                        [],
                    ),
                }
                for offset in range(days)
            ]
            resource.calendar = calendar
            resources_with_calendar.append(resource)

        serializer = ResourceCalendarSerializer(
            resources_with_calendar,
            many=True,
            context={"request": request},
        )

        return response_success(
            serializer.data, "Booking calendars retrieved successfully!"
        )
