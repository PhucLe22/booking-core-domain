from rest_framework import serializers

from core.constant import SYSTEM_ENUM_TYPES
from core.models import (
    EnumDefinition,
    EnumType,
)


def normalize_code(value):
    return value.strip().upper()


# =========================================================
# ENUM TYPE
# =========================================================


class EnumTypeSerializer(serializers.ModelSerializer):
    code = serializers.CharField(
        max_length=50,
        error_messages={
            "required": "Please enter enum type code!",
            "blank": "Enum type code cannot be empty!",
            "max_length": "Enum type code cannot exceed 50 characters!",
        },
    )
    name = serializers.CharField(
        max_length=100,
        error_messages={
            "required": "Please enter enum type name!",
            "blank": "Enum type name cannot be empty!",
            "max_length": "Enum type name cannot exceed 100 characters!",
        },
    )
    description = serializers.CharField(required=False, allow_blank=True)
    is_system = serializers.SerializerMethodField()
    definitions_count = serializers.SerializerMethodField()

    class Meta:
        model = EnumType
        fields = ["id", "code", "name", "description", "is_system", "definitions_count"]
        read_only_fields = ["id"]

    def get_is_system(self, obj) -> bool:
        return obj.code in SYSTEM_ENUM_TYPES

    def get_definitions_count(self, obj) -> int:
        return obj.definitions.count()

    def validate_code(self, value):
        value = normalize_code(value)
        if self.instance is not None and self.instance.code in SYSTEM_ENUM_TYPES:
            if value != self.instance.code:
                raise serializers.ValidationError(
                    "System enum type code cannot be changed!"
                )
        duplicates = EnumType.objects.filter(code=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(f"Enum type '{value}' already exists!")
        return value


# =========================================================
# ENUM DEFINITION
# =========================================================


class EnumDefinitionSerializer(serializers.ModelSerializer):
    enum_type = serializers.SlugRelatedField(
        slug_field="code",
        queryset=EnumType.objects.all(),
        error_messages={
            "required": "Please select an enum type!",
            "does_not_exist": "Enum type '{value}' does not exist!",
        },
    )
    code = serializers.CharField(
        max_length=50,
        error_messages={
            "required": "Please enter code!",
            "blank": "Code cannot be empty!",
            "max_length": "Code cannot exceed 50 characters!",
        },
    )
    name = serializers.CharField(
        max_length=100,
        error_messages={
            "required": "Please enter name!",
            "blank": "Name cannot be empty!",
            "max_length": "Name cannot exceed 100 characters!",
        },
    )
    value = serializers.IntegerField(
        required=False,
        allow_null=True,
        error_messages={"invalid": "Value must be a number!"},
    )
    position = serializers.IntegerField(
        required=False,
        min_value=0,
        error_messages={
            "invalid": "Position must be a number!",
            "min_value": "Position cannot be negative!",
        },
    )
    configuration = serializers.JSONField(required=False)

    class Meta:
        model = EnumDefinition
        fields = [
            "id",
            "enum_type",
            "code",
            "name",
            "value",
            "position",
            "configuration",
            "is_system",
            "is_active",
        ]
        read_only_fields = ["id", "is_system"]
        # uniqueness is checked in validate() to return custom messages
        validators = []

    def validate_code(self, value):
        return normalize_code(value)

    def validate_configuration(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Configuration must be an object!")
        return value

    def validate(self, data):
        instance = self.instance
        enum_type = data.get("enum_type", getattr(instance, "enum_type", None))
        code = data.get("code", getattr(instance, "code", None))
        value = data.get("value", getattr(instance, "value", None))

        # the code relies on system values: they keep their type and code
        # and stay active; name, value, position and configuration can change
        if instance is not None and instance.is_system:
            errors = {}
            if enum_type != instance.enum_type:
                errors["enum_type"] = ["System value cannot move to another type!"]
            if code != instance.code:
                errors["code"] = ["System value code cannot be changed!"]
            if data.get("is_active") is False:
                errors["is_active"] = ["System value cannot be deactivated!"]
            if errors:
                raise serializers.ValidationError(errors)

        siblings = EnumDefinition.objects.filter(enum_type=enum_type)
        if instance is not None:
            siblings = siblings.exclude(pk=instance.pk)
        if siblings.filter(code=code).exists():
            raise serializers.ValidationError(
                {"code": [f"Code '{code}' already exists in {enum_type.code}!"]}
            )
        if value is not None and siblings.filter(value=value).exists():
            raise serializers.ValidationError(
                {"value": [f"Value {value} already exists in {enum_type.code}!"]}
            )
        return data



class EnumValueSerializer(serializers.ModelSerializer):
    """A value inside its enum type group (the type is not repeated)."""

    class Meta:
        model = EnumDefinition
        fields = [
            "id",
            "code",
            "name",
            "value",
            "position",
            "configuration",
            "is_system",
            "is_active",
        ]


class EnumGroupSerializer(serializers.Serializer):
    """An enum type with its values, eg: RESOURCE_STATUS -> ACTIVE, INACTIVE, ..."""

    enum_type = serializers.CharField(source="code")
    name = serializers.CharField()
    description = serializers.CharField()
    is_system = serializers.SerializerMethodField()
    definitions = EnumValueSerializer(many=True)

    def get_is_system(self, obj) -> bool:
        return obj["code"] in SYSTEM_ENUM_TYPES
