from django.urls import include, path
from rest_framework import routers
from rest_framework.routers import DefaultRouter

from .views import ResourceTypeViewSet, ResourceViewSet

router = routers.DefaultRouter()
router = DefaultRouter()
router.register(r"v1/resources", ResourceViewSet, basename="resource")
router.register(
    r"v1/resource_types", ResourceTypeViewSet, basename="resource_type"
)

urlpatterns = [
    path("", include(router.urls)),
]
