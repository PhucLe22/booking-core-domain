from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import EnumDefinitionViewSet, EnumTypeViewSet

router = DefaultRouter()
router.register(r"v1/enum_types", EnumTypeViewSet, basename="enum_type")
router.register(
    r"v1/enum_definitions", EnumDefinitionViewSet, basename="enum_definition"
)

urlpatterns = [
    path("", include(router.urls)),
]
