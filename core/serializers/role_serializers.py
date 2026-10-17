from django.db import transaction
from rest_framework import serializers

from core.models import Permission, Role


class PermissionSerializer(serializers.ModelSerializer):
    code = serializers.CharField(
        max_length=100,
        error_messages={
            "required": "Please enter permission code!",
            "blank": "Permission code cannot be empty!",
            "max_length": "Permission code cannot exceed 100 characters!",
        },
    )
    name = serializers.CharField(
        max_length=150,
        error_messages={
            "required": "Please enter permission name!",
            "blank": "Permission name cannot be empty!",
            "max_length": "Permission name cannot exceed 150 characters!",
        },
    )
    configuration = serializers.JSONField(required=False)

    class Meta:
        model = Permission
        fields = ["id", "code", "name", "description", "configuration"]
        read_only_fields = ["id"]

    def validate_code(self, value):
        value = value.strip().upper()
        duplicates = Permission.objects.filter(code=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                f"Permission code '{value}' already exists!"
            )
        return value


class RoleSerializer(serializers.ModelSerializer):
    code = serializers.CharField(
        max_length=50,
        error_messages={
            "required": "Please enter role code!",
            "blank": "Role code cannot be empty!",
            "max_length": "Role code cannot exceed 50 characters!",
        },
    )
    name = serializers.CharField(
        max_length=100,
        error_messages={
            "required": "Please enter role name!",
            "blank": "Role name cannot be empty!",
            "max_length": "Role name cannot exceed 100 characters!",
        },
    )
    permissions = serializers.SlugRelatedField(
        many=True,
        slug_field="code",
        queryset=Permission.objects.all(),
        required=False,
        error_messages={
            "does_not_exist": "Permission '{value}' does not exist!",
            "not_a_list": "Permissions must be a list of permission codes!",
        },
    )
    configuration = serializers.JSONField(required=False)

    class Meta:
        model = Role
        fields = [
            "id",
            "code",
            "name",
            "description",
            "configuration",
            "is_system",
            "is_active",
            "permissions",
        ]
        read_only_fields = ["id", "is_system"]

    def validate_code(self, value):
        value = value.strip().upper()
        if self.instance is not None and self.instance.is_system:
            if value != self.instance.code:
                raise serializers.ValidationError("System role code cannot be changed!")
        duplicates = Role.objects.filter(code=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(f"Role code '{value}' already exists!")
        return value

    def validate_is_active(self, value):
        if self.instance is not None and self.instance.is_system and not value:
            raise serializers.ValidationError("System role cannot be deactivated!")
        return value

    @transaction.atomic
    def create(self, validated_data):
        permissions = validated_data.pop("permissions", [])
        role = Role.objects.create(**validated_data)
        role.permissions.set(permissions)
        return role

    @transaction.atomic
    def update(self, instance, validated_data):
        permissions = validated_data.pop("permissions", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if permissions is not None:
            instance.permissions.set(permissions)
        return instance
