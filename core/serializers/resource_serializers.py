from django.db import transaction
from rest_framework import serializers

from core.configuration_rules import check_configuration, check_field_definition
from core.constant import DEFAULT_RESOURCE_STATUS_TYPE, ResourceStatus
from core.models import EnumType, Resource, ResourceType

from .fields import enum_values

class ResourceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceType
        fields = "__all__"


class ResourceSerializer(serializers.ModelSerializer):
    resource_type_code = serializers.CharField(
        source="resource_type.code", read_only=True
    )
    # null when the resource has no status
    status = serializers.CharField(source="status.code", read_only=True, default=None)
    # status_name = serializers.CharField(source="status.name", read_only=True)

    class Meta:
        model = Resource
        fields = [
            "id",
            "resource_type",
            "resource_type_code",
            "code",
            "name",
            "status",
            # "status_name",
            "configuration",
            "created_at",
            "updated_at",
        ]


class EditResourceSerializer(serializers.ModelSerializer):
    resource_type = serializers.PrimaryKeyRelatedField(
        queryset=ResourceType.objects.all(),
        pk_field=serializers.UUIDField(
            error_messages={"invalid": "Resource type ID is not a valid UUID!"}
        ),
        error_messages={
            "required": "Please select a resource type!",
            "null": "Resource type cannot be empty!",
            "does_not_exist": "Resource type does not exist!",
        },
    )
    code = serializers.CharField(
        max_length=50,
        error_messages={
            "required": "Please enter resource code!",
            "blank": "Resource code cannot be empty!",
            "max_length": "Resource code cannot exceed 50 characters!",
        },
    )
    name = serializers.CharField(
        max_length=150,
        error_messages={
            "required": "Please enter resource name!",
            "blank": "Resource name cannot be empty!",
            "max_length": "Resource name cannot exceed 150 characters!",
        },
    )
    # a code from the status list of the resource type, checked in validate(); blank = no status
    status = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    configuration = serializers.JSONField(
        required=False,
        error_messages={
            "invalid": "Configuration must be valid JSON!",
        },
    )

    class Meta:
        model = Resource
        fields = [
            "id",
            "resource_type",
            "code",
            "name",
            "status",
            "configuration",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        # uniqueness is checked in validate() to return a custom message
        validators = []

    def validate_configuration(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Configuration must be an object!")
        return value

    def validate(self, data):
        resource_type = data.get(
            "resource_type", getattr(self.instance, "resource_type", None)
        )
        data["status"] = self.resolve_status(resource_type, data.get("status", ...))

        code = data.get("code", getattr(self.instance, "code", None))
        duplicates = Resource.objects.filter(resource_type=resource_type, code=code)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                {"code": "Resource code already exists for this resource type!"}
            )

        configuration = data.get(
            "configuration", getattr(self.instance, "configuration", {})
        )
        # missing fields get the default set in the resource type
        configuration, configuration_errors = check_configuration(
            configuration, resource_type.configuration
        )
        if configuration_errors:
            raise serializers.ValidationError({"configuration": configuration_errors})
        data["configuration"] = configuration
        return data

    def resolve_status(self, resource_type, code):
        """
        The status comes from the master data list of the resource type
        (configuration.status_enum_type, default RESOURCE_STATUS).
        A blank status ("" or null) means the resource has no status.
        When status is not sent at all, the current status is kept if it fits the list,
        else it becomes blank (new resources get ACTIVE when the list has it).
        """
        status_type = resource_type.status_enum_type
        statuses = enum_values(status_type)
        if code is None or (isinstance(code, str) and not code.strip()):
            return None
        if code is not ...:
            status = statuses.filter(code__iexact=code.strip()).first()
            if status is None:
                raise serializers.ValidationError(
                    {"status": [f"Resource status '{code}' does not exist in {status_type}!"]}
                )
            return status
        if self.instance is None:
            return statuses.filter(code=ResourceStatus.ACTIVE).first()
        current = self.instance.status
        if current is not None and current.enum_type.code == status_type:
            return current
        return None



class EditResourceTypeSerializer(serializers.ModelSerializer):
    code = serializers.CharField(
        max_length=50,
        error_messages={
            "required": "Please enter resource type code!",
            "blank": "Resource type code cannot be empty!",
            "max_length": "Resource type code cannot exceed 50 characters!",
        },
    )
    name = serializers.CharField(
        max_length=100,
        error_messages={
            "required": "Please enter resource type name!",
            "blank": "Resource type name cannot be empty!",
            "max_length": "Resource type name cannot exceed 100 characters!",
        },
    )
    configuration = serializers.JSONField(
        required=False,
        error_messages={
            "invalid": "Configuration must be valid JSON!",
        },
    )
    # when the status list changes: {old status code: new status code}
    status_mapping = serializers.JSONField(required=False, write_only=True)

    class Meta:
        model = ResourceType
        fields = ["id", "code", "name", "configuration", "status_mapping"]
        read_only_fields = ["id"]

    def validate_code(self, value):
        duplicates = ResourceType.objects.filter(code=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                f"Resource type code '{value}' already exists!"
            )
        return value

    def validate_configuration(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Configuration must be an object!")

        fields = value.get("fields", {})
        if not isinstance(fields, dict):
            raise serializers.ValidationError(
                {"fields": ["'fields' must be an object!"]}
            )

        # which master data list the statuses of this type's resources come from
        if "status_enum_type" in value:
            status_type = value["status_enum_type"]
            if not isinstance(status_type, str) or not EnumType.objects.filter(code=status_type).exists():
                raise serializers.ValidationError(
                    {"status_enum_type": [f"Master data list '{status_type}' does not exist!"]}
                )

        # type, required and every rule of each field (see core/configuration_rules.py)
        errors = {}
        for name, field in fields.items():
            field_errors = check_field_definition(name, field)
            if field_errors:
                errors[name] = field_errors
        if errors:
            raise serializers.ValidationError({"fields": errors})
        return value

    def validate(self, data):
        mapping = data.pop("status_mapping", None) or {}
        self.status_moves = []
        if self.instance is not None:
            configuration = data.get("configuration", self.instance.configuration) or {}
            status_type = configuration.get("status_enum_type") or DEFAULT_RESOURCE_STATUS_TYPE
            self.status_moves = self.plan_status_moves(status_type, mapping)
        return data

    def plan_status_moves(self, status_type, mapping):
        """
        When the status list changes, every resource of this type moves to a status
        of the new list: the one picked in status_mapping {old code: new code, or ""
        for no status}, else the value with the same code. Return [(old status id, new status)].
        """
        if not isinstance(mapping, dict):
            raise serializers.ValidationError({"status_mapping": ["Status mapping must be an object!"]})
        new_statuses = {status.code.upper(): status for status in enum_values(status_type)}
        # an empty new code means "no status"
        mapping = {str(old).upper(): str(new or "").upper() for old, new in mapping.items()}

        moves, errors = [], []
        used = (
            self.instance.resources.filter(status__isnull=False)
            .exclude(status__enum_type__code=status_type)
            .values_list("status_id", "status__code", "status__name")
            .distinct()
        )
        for status_id, code, name in used:
            code = code.upper()
            if mapping.get(code) == "":
                moves.append((status_id, None))
                continue
            target = new_statuses.get(mapping.get(code, code))
            if target is None:
                errors.append(
                    f"Status '{mapping[code]}' does not exist in {status_type}!"
                    if code in mapping
                    else f"Pick a status of {status_type} for resources that are '{name}' now!"
                )
            else:
                moves.append((status_id, target))
        if errors:
            raise serializers.ValidationError({"status_mapping": errors})
        return moves

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        for status_id, status in self.status_moves:
            instance.resources.filter(status_id=status_id).update(status=status)
        return instance
