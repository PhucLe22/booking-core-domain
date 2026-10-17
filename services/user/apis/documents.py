from drf_spectacular.utils import OpenApiParameter

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


def id_parameter(description, type=str):
    return OpenApiParameter(
        "id", type=type, location=OpenApiParameter.PATH, description=description
    )


# ---------- auth ----------

register_user_document = {
    "summary": "Register",
    "description": "Create a new customer account.",
    "request": RegisterUserSerializer,
    "responses": {201: UserSerializer},
    "auth": [],
}

login_user_document = {
    "summary": "Login",
    "description": "Login with username and password. Returns the user with access and refresh tokens.",
    "request": UserLoginSerializer,
    "responses": {200: UserSerializerWithToken},
    "auth": [],
}

refresh_token_document = {
    "summary": "Refresh token",
    "description": "Get new tokens when the access token is expired.",
    "request": RefreshTokenSerializer,
    "responses": {200: UserSerializerWithToken},
    "auth": [],
}

logout_user_document = {
    "summary": "Logout",
    "description": "Blacklist the refresh token and sign out every session of the user.",
    "request": RefreshTokenSerializer,
    "responses": {200: None},
}

get_me_document = {
    "summary": "Get my profile",
    "description": "Get the logged in user.",
    "responses": {200: UserSerializer},
}

update_me_document = {
    "summary": "Update my profile",
    "description": "Update the first and last name of the logged in user.",
    "request": ProfileSerializer,
    "responses": {200: UserSerializer},
}

change_password_document = {
    "summary": "Change password",
    "description": "Change the password of the logged in user. Every other session is signed out; new tokens are returned.",
    "request": ChangePasswordSerializer,
    "responses": {200: UserSerializerWithToken},
}

# ---------- users ----------

list_users_document = {
    "summary": "Get list of users",
    "description": "Admin or staff. eg: http://localhost:9001/api/v1/users/?role=CUSTOMER&name=an&page=1",
    "parameters": [
        OpenApiParameter(
            "page", int, required=False, default=1, description="Page number"
        ),
        OpenApiParameter(
            "page_size",
            int,
            required=False,
            default=5,
            description="Number of users per page.",
        ),
        OpenApiParameter("username", str, required=False, description="Username contains"),
        OpenApiParameter(
            "name", str, required=False, description="First or last name contains"
        ),
        OpenApiParameter(
            "role", str, required=False, description="Role code, eg: CUSTOMER"
        ),
        OpenApiParameter("status", bool, required=False, description="Account status"),
    ],
    "responses": {200: UserSerializer(many=True)},
}

retrieve_user_document = {
    "parameters": [id_parameter("ID of the user", int)],
    "summary": "Get user detail",
    "description": "Admin or staff.",
    "responses": {200: UserSerializer},
}

create_user_document = {
    "summary": "Create user",
    "description": "Admin creates a user with roles, eg: staff accounts.",
    "request": ManageUserSerializer,
    "responses": {201: UserSerializer},
}

update_user_document = {
    "parameters": [id_parameter("ID of the user", int)],
    "summary": "Update user",
    "description": "Admin updates name, status and roles. Username and password cannot be changed here.",
    "request": ManageUserSerializer,
    "responses": {200: UserSerializer},
}

delete_user_document = {
    "parameters": [id_parameter("ID of the user", int)],
    "summary": "Delete user",
    "description": "Admin soft deletes a user and signs them out.",
    "responses": {200: None},
}

# ---------- roles ----------

list_roles_document = {
    "summary": "Get list of roles",
    "description": "Admin only.",
    "responses": {200: RoleSerializer(many=True)},
}

retrieve_role_document = {
    "parameters": [id_parameter("UUID of the role")],
    "summary": "Get role detail",
    "description": "Admin only.",
    "responses": {200: RoleSerializer},
}

create_role_document = {
    "summary": "Create role",
    "description": "Admin only. permissions is a list of permission codes.",
    "request": RoleSerializer,
    "responses": {201: RoleSerializer},
}

update_role_document = {
    "parameters": [id_parameter("UUID of the role")],
    "summary": "Update role",
    "description": "Admin only. System roles cannot change code or be deactivated.",
    "request": RoleSerializer,
    "responses": {200: RoleSerializer},
}

delete_role_document = {
    "parameters": [id_parameter("UUID of the role")],
    "summary": "Delete role",
    "description": "Admin only. System roles and roles assigned to users cannot be deleted.",
    "responses": {200: None},
}

# ---------- permissions ----------

list_permissions_document = {
    "summary": "Get list of permissions",
    "description": "Admin only.",
    "responses": {200: PermissionSerializer(many=True)},
}

create_permission_document = {
    "summary": "Create permission",
    "description": "Admin only.",
    "request": PermissionSerializer,
    "responses": {201: PermissionSerializer},
}

update_permission_document = {
    "parameters": [id_parameter("UUID of the permission")],
    "summary": "Update permission",
    "description": "Admin only.",
    "request": PermissionSerializer,
    "responses": {200: PermissionSerializer},
}

delete_permission_document = {
    "parameters": [id_parameter("UUID of the permission")],
    "summary": "Delete permission",
    "description": "Admin only.",
    "responses": {200: None},
}
