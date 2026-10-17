from django.contrib.auth import authenticate
from django.db.models import ProtectedError
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from core.filters import UserFilter
from core.jwt import MyTokenObtainPairSerializer
from core.middlewares.login_required import LOGIN_REQUIRED
from core.middlewares.staff import AdminMiddleware, StaffMiddleware
from core.models import Permission, Role, User
from core.paginators import CustomPaginator
from core.serializers.role_serializers import PermissionSerializer, RoleSerializer
from core.serializers.user_serializers import (
    ChangePasswordSerializer,
    ManageUserSerializer,
    ProfileSerializer,
    RefreshTokenSerializer,
    RegisterUserSerializer,
    UserLoginSerializer,
    UserSerializer,
    UserSerializerWithToken,
)
from core.utils import get_instance, response_errors, response_success

from .documents import (
    change_password_document,
    create_permission_document,
    create_role_document,
    create_user_document,
    delete_permission_document,
    delete_role_document,
    delete_user_document,
    get_me_document,
    list_permissions_document,
    list_roles_document,
    list_users_document,
    login_user_document,
    logout_user_document,
    refresh_token_document,
    register_user_document,
    retrieve_role_document,
    retrieve_user_document,
    update_me_document,
    update_permission_document,
    update_role_document,
    update_user_document,
)


def user_with_tokens(user):
    refresh = MyTokenObtainPairSerializer.get_token(user)
    return UserSerializerWithToken(
        user,
        context={
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
        },
    ).data


class AuthenViewSet(viewsets.ViewSet):
    @extend_schema(**register_user_document)
    @action(detail=False, methods=["post"], url_path="register")
    def create_user(self, request):
        serializer = RegisterUserSerializer(data=request.data)
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        user = serializer.save()
        return response_success(
            UserSerializer(user).data,
            "User created successfully!",
            status.HTTP_201_CREATED,
        )

    @extend_schema(**login_user_document)
    @action(methods=["post"], detail=False, url_path="login")
    def login_user(self, request):
        serializer = UserLoginSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return response_errors(serializer.errors)

        user = authenticate(
            request,
            username=serializer.validated_data["username"].lower(),
            password=serializer.validated_data["password"],
        )
        if not user:
            return response_errors(
                {"username": ["Username or password is incorrect!"]},
                status.HTTP_401_UNAUTHORIZED,
            )
        return response_success(user_with_tokens(user), "Login successfully!")

    @extend_schema(**logout_user_document)
    @action(
        methods=["post"],
        detail=False,
        url_path="logout",
        authentication_classes=[JWTAuthentication],
        permission_classes=LOGIN_REQUIRED,
    )
    def logout_user(self, request):
        try:
            refresh_token = RefreshToken(request.data.get("refresh_token"))
            request.user.set_new_token_version()
            refresh_token.blacklist()
        except (TokenError, InvalidToken) as e:
            raise AuthenticationFailed(f"{str(e)}!")
        return response_success(message="Logout successfully!")

    @extend_schema(methods=["GET"], **get_me_document)
    @extend_schema(methods=["PUT"], **update_me_document)
    @action(
        methods=["get", "put"],
        detail=False,
        url_path="me",
        authentication_classes=[JWTAuthentication],
        permission_classes=LOGIN_REQUIRED,
    )
    def me(self, request):
        if request.method == "GET":
            return response_success(
                UserSerializer(request.user).data, "Profile retrieved successfully!"
            )

        serializer = ProfileSerializer(request.user, data=request.data)
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        serializer.save()
        return response_success(
            UserSerializer(request.user).data, "Profile updated successfully!"
        )

    @extend_schema(**change_password_document)
    @action(
        methods=["post"],
        detail=False,
        url_path="change_password",
        authentication_classes=[JWTAuthentication],
        permission_classes=LOGIN_REQUIRED,
    )
    def change_password(self, request):
        user = request.user
        serializer = ChangePasswordSerializer(
            data=request.data, context={"user": user}
        )
        if not serializer.is_valid():
            return response_errors(serializer.errors)

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        # sign out every other session; the caller gets fresh tokens
        user.set_new_token_version()
        return response_success(
            user_with_tokens(user), "Password changed successfully!"
        )


# refresh token view
class CustomTokenRefreshView(TokenRefreshView):
    @extend_schema(**refresh_token_document)
    def post(self, request, *args, **kwargs):
        serializer = RefreshTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return response_errors(serializer.errors)

        return response_success(
            UserSerializerWithToken(
                serializer.validated_data.get("user"),
                context={
                    "access_token": str(serializer.validated_data["access_token"]),
                    "refresh_token": str(
                        serializer.validated_data.get("refresh_token")
                    ),
                },
            ).data,
            "Refresh token successfully!",
        )


class UserViewSet(viewsets.ViewSet):
    """Admin manages users; staff can look users up (e.g. for staff bookings)."""

    authentication_classes = [JWTAuthentication]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [cls() for cls in [*LOGIN_REQUIRED, StaffMiddleware]]
        return [cls() for cls in [*LOGIN_REQUIRED, AdminMiddleware]]

    @extend_schema(**list_users_document)
    def list(self, request):
        user_filter = UserFilter(
            request.query_params,
            queryset=User.objects.prefetch_related("roles").order_by("id"),
        )
        if not user_filter.is_valid():
            return response_errors(user_filter.errors)
        paginator = CustomPaginator()
        page = paginator.paginate_queryset(user_filter.qs, request)
        return paginator.get_paginated_response(
            UserSerializer(page, many=True).data, "Users retrieved successfully!"
        )

    @extend_schema(**retrieve_user_document)
    def retrieve(self, request, pk=None):
        return response_success(
            UserSerializer(get_instance(User, pk)).data, "User retrieved successfully!"
        )

    @extend_schema(**create_user_document)
    def create(self, request):
        serializer = ManageUserSerializer(
            data=request.data, context={"user": request.user}
        )
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        user = serializer.save()
        return response_success(
            UserSerializer(user).data,
            "User created successfully!",
            status.HTTP_201_CREATED,
        )

    @extend_schema(**update_user_document)
    def update(self, request, pk=None):
        user = get_instance(User, pk)
        serializer = ManageUserSerializer(
            user, data=request.data, context={"user": request.user}
        )
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        user = serializer.save()
        # role or status changes take effect on the user's next login
        user.set_new_token_version()
        return response_success(
            UserSerializer(user).data, "User updated successfully!"
        )

    @extend_schema(**delete_user_document)
    def destroy(self, request, pk=None):
        user = get_instance(User, pk)
        if user == request.user:
            return response_errors({"id": ["You cannot delete your own account!"]})
        user.set_new_token_version()
        user.delete()  # soft delete
        return response_success(message="User deleted successfully!")


class RoleViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [*LOGIN_REQUIRED, AdminMiddleware]

    @extend_schema(**list_roles_document)
    def list(self, request):
        roles = Role.objects.prefetch_related("permissions").order_by("code")
        return response_success(
            RoleSerializer(roles, many=True).data, "Roles retrieved successfully!"
        )

    @extend_schema(**retrieve_role_document)
    def retrieve(self, request, pk=None):
        return response_success(
            RoleSerializer(get_instance(Role, pk)).data, "Role retrieved successfully!"
        )

    @extend_schema(**create_role_document)
    def create(self, request):
        serializer = RoleSerializer(data=request.data)
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        serializer.save()
        return response_success(
            serializer.data, "Role created successfully!", status.HTTP_201_CREATED
        )

    @extend_schema(**update_role_document)
    def update(self, request, pk=None):
        serializer = RoleSerializer(get_instance(Role, pk), data=request.data)
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        serializer.save()
        return response_success(serializer.data, "Role updated successfully!")

    @extend_schema(**delete_role_document)
    def destroy(self, request, pk=None):
        role = get_instance(Role, pk)
        if role.is_system:
            return response_errors({"id": ["System role cannot be deleted!"]})
        if role.user_assignments.exists():
            return response_errors({"id": ["Role is still assigned to users!"]})
        role.delete()
        return response_success(message="Role deleted successfully!")


class PermissionViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [*LOGIN_REQUIRED, AdminMiddleware]

    @extend_schema(**list_permissions_document)
    def list(self, request):
        permissions = Permission.objects.order_by("code")
        return response_success(
            PermissionSerializer(permissions, many=True).data,
            "Permissions retrieved successfully!",
        )

    @extend_schema(**create_permission_document)
    def create(self, request):
        serializer = PermissionSerializer(data=request.data)
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        serializer.save()
        return response_success(
            serializer.data,
            "Permission created successfully!",
            status.HTTP_201_CREATED,
        )

    @extend_schema(**update_permission_document)
    def update(self, request, pk=None):
        serializer = PermissionSerializer(
            get_instance(Permission, pk), data=request.data
        )
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        serializer.save()
        return response_success(serializer.data, "Permission updated successfully!")

    @extend_schema(**delete_permission_document)
    def destroy(self, request, pk=None):
        permission = get_instance(Permission, pk)
        try:
            permission.delete()
        except ProtectedError:
            return response_errors(
                {"id": ["Permission is still used by status transitions!"]}
            )
        return response_success(message="Permission deleted successfully!")
