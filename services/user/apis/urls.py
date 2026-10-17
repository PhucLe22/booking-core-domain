from django.urls import include, path
from rest_framework import routers

from .views import (
    AuthenViewSet,
    CustomTokenRefreshView,
    PermissionViewSet,
    RoleViewSet,
    UserViewSet,
)


router = routers.DefaultRouter()
router.register(r"v1/auth", AuthenViewSet, basename="auth")
router.register(r"v1/users", UserViewSet, basename="user")
router.register(r"v1/roles", RoleViewSet, basename="role")
router.register(r"v1/permissions", PermissionViewSet, basename="permission")

urlpatterns = [
    path(r"", include(router.urls)),
    path(r"v1/auth/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
]
