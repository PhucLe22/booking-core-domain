import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from core.constant import RoleCode
from core.models import Role, User
from core.utils import validate_max_length


def validate_strong_password(value, user=None):
    try:
        validate_password(value, user)
    except ValidationError as exc:
        if len(exc.messages) > 1:
            raise serializers.ValidationError(
                "Your password must contain at least 8 characters, one uppercase "
                "letter, one digit, and one special character!"
            )
        raise serializers.ValidationError(exc.messages)
    return value


class UserSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(
        required=True,
        error_messages={
            "required": "Please enter your firstname!",
            "blank": "Firstname cannot be empty!",
        },
    )
    last_name = serializers.CharField(
        required=True,
        error_messages={
            "required": "Please enter your lastname!",
            "blank": "Lastname cannot be empty!",
        },
    )
    username = serializers.CharField(
        required=True,
        error_messages={
            "required": "Please enter your username address!",
            "invalid": "Enter a valid username address!",
            "blank": "Username cannot be empty!",
        },
    )
    password = serializers.CharField(
        required=True,
        write_only=True,
        error_messages={
            "required": "Please enter your password!",
            "blank": "Password cannot be empty!",
        },
    )
    roles = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="code"
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "password",
            "first_name",
            "last_name",
            "roles",
            "avatar",
            "full_name",
            "status",
        ]
        extra_kwargs = {"password": {"write_only": True}}

        def get_full_name(self, obj):
            return obj.full_name

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if representation.get("avatar"):
            representation["avatar"] = (
                f"{os.environ.get("BE_DOMAIN")}{representation['avatar']}"
            )
        return representation


class RegisterUserSerializer(serializers.Serializer):
    first_name = serializers.CharField(
        required=True,
        error_messages={
            "required": "Please enter your firstname!",
            "blank": "Firstname cannot be empty!",
        },
    )
    last_name = serializers.CharField(
        required=True,
        error_messages={
            "required": "Please enter your lastname!",
            "blank": "Lastname cannot be empty!",
        },
    )
    username = serializers.CharField(
        required=True,
        error_messages={
            "required": "Please enter your username address!",
            "invalid": "Enter a valid username address!",
            "blank": "Username cannot be empty!",
        },
    )
    password = serializers.CharField(
        required=True,
        write_only=True,
        error_messages={
            "required": "Please enter your password!",
            "blank": "Password cannot be empty!",
        },
    )
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "password",
            "first_name",
            "last_name",
            "avatar",
            "full_name",
            "status",
        ]
        extra_kwargs = {"password": {"write_only": True}}

        def get_full_name(self, obj):
            return obj.full_name

    def validate(self, data):
        char_fields = ["first_name", "last_name", "password"]
        for field in char_fields:
            if field in data:
                validate_max_length(
                    data[field],
                    self.Meta.model._meta.get_field(field).max_length,
                    field.capitalize(),
                )
        return data

    def validate_username(self, value):
        if User.objects.filter(username=value.lower()).exists():
            raise serializers.ValidationError("Username already exists!")
        return value

    def validate_password(self, value):
        return validate_strong_password(value)

    @transaction.atomic
    def create(self, validated_data):
        validated_data["username"] = validated_data["username"].lower()
        user = User(**validated_data)
        user.set_password(validated_data.get("password", "Defaultpassword@123"))
        user.save()
        # every sign-up is a customer, staff/admin roles are assigned by an admin
        user.assign_role(RoleCode.CUSTOMER)
        return user


class UserLoginSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        required=True,
        error_messages={
            "required": "Please enter username address!",
            "invalid": "Enter a valid username address!",
            "blank": "Username cannot be empty!",
        },
    )
    password = serializers.CharField(
        required=True,
        error_messages={
            "required": "Please enter your password!",
            "blank": "Password cannot be empty!",
        },
    )

    class Meta:
        model = User
        fields = ["username", "password"]
        extra_kwargs = {"password": {"write_only": True}}


class RefreshTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()
    token_class = RefreshToken

    def validate(self, attrs):
        try:
            refresh = self.token_class(attrs["refresh_token"])
        except TokenError as e:
            raise InvalidToken(f"{str(e)}!")
        except InvalidToken as e:
            raise InvalidToken(f"{str(e)}!")

        if not refresh:
            raise AuthenticationFailed("No refresh token provided!")

        # get the user from the token
        user_id = refresh.payload.get("user_id")
        user = User.objects.get(id=user_id)
        token_version = refresh.payload.get("token_version", None)
        if not user.is_token_version_valid(token_version):
            raise AuthenticationFailed("Token is invalid due to version mismatch!")

        data = {"access_token": str(refresh.access_token), "user": user}

        if api_settings.ROTATE_REFRESH_TOKENS:
            if api_settings.BLACKLIST_AFTER_ROTATION:
                try:
                    # Attempt to blacklist the given refresh token
                    refresh.blacklist()
                except AttributeError:
                    # If blacklist app not installed, `blacklist` method will
                    # not be present
                    pass

            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()

            data["refresh_token"] = str(refresh)

        return data


class UserSerializerWithToken(UserSerializer):
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["refresh_token"] = self.context.get("refresh_token")
        representation["access_token"] = self.context.get("access_token")
        return representation


class ProfileSerializer(serializers.ModelSerializer):
    """The logged in user updates their own profile."""

    first_name = serializers.CharField(
        max_length=255,
        error_messages={
            "required": "Please enter your firstname!",
            "blank": "Firstname cannot be empty!",
            "max_length": "Firstname cannot exceed 255 characters!",
        },
    )
    last_name = serializers.CharField(
        max_length=255,
        error_messages={
            "required": "Please enter your lastname!",
            "blank": "Lastname cannot be empty!",
            "max_length": "Lastname cannot exceed 255 characters!",
        },
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name"]


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        write_only=True,
        error_messages={
            "required": "Please enter your current password!",
            "blank": "Current password cannot be empty!",
        },
    )
    new_password = serializers.CharField(
        write_only=True,
        error_messages={
            "required": "Please enter your new password!",
            "blank": "New password cannot be empty!",
        },
    )

    def validate_old_password(self, value):
        if not self.context["user"].check_password(value):
            raise serializers.ValidationError("Current password is incorrect!")
        return value

    def validate_new_password(self, value):
        return validate_strong_password(value, self.context["user"])

    def validate(self, data):
        if data["old_password"] == data["new_password"]:
            raise serializers.ValidationError(
                {"new_password": "New password must be different from the current one!"}
            )
        return data


class ManageUserSerializer(serializers.ModelSerializer):
    """Admin creates or updates any user, including their roles."""

    username = serializers.CharField(
        max_length=255,
        error_messages={
            "required": "Please enter username!",
            "blank": "Username cannot be empty!",
            "max_length": "Username cannot exceed 255 characters!",
        },
    )
    password = serializers.CharField(
        write_only=True,
        required=False,
        error_messages={"blank": "Password cannot be empty!"},
    )
    first_name = serializers.CharField(
        max_length=255,
        error_messages={
            "required": "Please enter firstname!",
            "blank": "Firstname cannot be empty!",
            "max_length": "Firstname cannot exceed 255 characters!",
        },
    )
    last_name = serializers.CharField(
        max_length=255,
        error_messages={
            "required": "Please enter lastname!",
            "blank": "Lastname cannot be empty!",
            "max_length": "Lastname cannot exceed 255 characters!",
        },
    )
    status = serializers.BooleanField(required=False)
    roles = serializers.SlugRelatedField(
        many=True,
        slug_field="code",
        queryset=Role.objects.filter(is_active=True),
        error_messages={
            "required": "Please select at least one role!",
            "does_not_exist": "Role '{value}' does not exist!",
            "not_a_list": "Roles must be a list of role codes!",
        },
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "password",
            "first_name",
            "last_name",
            "full_name",
            "status",
            "roles",
        ]
        read_only_fields = ["id", "full_name"]

    def validate_username(self, value):
        value = value.lower()
        if self.instance is not None and value != self.instance.username:
            raise serializers.ValidationError("Username cannot be changed!")
        if self.instance is None and User.global_objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists!")
        return value

    def validate_password(self, value):
        return validate_strong_password(value)

    def validate_roles(self, value):
        if not value:
            raise serializers.ValidationError("Please select at least one role!")
        return value

    def validate(self, data):
        if self.instance is None and not data.get("password"):
            raise serializers.ValidationError({"password": "Please enter password!"})
        if self.instance is not None and "password" in data:
            raise serializers.ValidationError(
                {"password": "Password cannot be changed here!"}
            )

        # an admin cannot lock themselves out
        current_user = self.context.get("user")
        if self.instance is not None and self.instance == current_user:
            if RoleCode.ADMIN not in [role.code for role in data.get("roles", [])]:
                raise serializers.ValidationError(
                    {"roles": "You cannot remove your own admin role!"}
                )
            if data.get("status") is False:
                raise serializers.ValidationError(
                    {"status": "You cannot deactivate your own account!"}
                )
        return data

    @transaction.atomic
    def create(self, validated_data):
        roles = validated_data.pop("roles")
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        user.roles.set(roles)
        return user

    @transaction.atomic
    def update(self, instance, validated_data):
        roles = validated_data.pop("roles", None)
        validated_data.pop("username", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if roles is not None:
            instance.roles.set(roles)
        return instance
