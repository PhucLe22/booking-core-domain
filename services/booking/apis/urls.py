from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BookingViewSet, CalendarViewSet

router = DefaultRouter()
router.register(r"v1/bookings", BookingViewSet, basename="booking")
router.register(r"v1/calendars", CalendarViewSet, basename="calendar")

urlpatterns = [
    path("", include(router.urls)),
]
