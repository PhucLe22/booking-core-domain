import re

from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.configuration_rules import check_configuration, check_field_definition
from core.constant import (
    DEFAULT_RESOURCE_STATUS_TYPE,
    FIELD_LIST_HELP,
    FIELD_ORDER,
    KEY_PATTERN,
    KEY_PATTERN_MESSAGE,
    NOT_RESOURCE_STATUS_TYPES,
    ResourceStatus,
)
from core.models import EnumType, Resource, ResourceType

from .fields import enum_values


def field_list(configuration):
    """configuration["fields"] as the list of the spec: [{"key": ..., "type": ...}]."""
    configuration = configuration or {}
    fields = configuration.get("fields") or {}
    order = [key for key in configuration.get(FIELD_ORDER) or [] if key in fields]
    order += [key for key in fields if key not in order]
    return [{"key": key, **fields[key]} for key in order]


class ResourceTypeSerializer(serializers.ModelSerializer):
    """A resource type as the web reads it (key, label, list of fields)."""

    key = serializers.CharField(source="code")
    label = serializers.CharField(source="name")
    status_enum_type = serializers.CharField(read_only=True)

    class Meta:
        model = ResourceType
        fields = [
            "id",
            "key",
            "label",
            "description",
            "version",
            "status_enum_type",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_fields(self):
        declared = super().get_fields()
        declared["fields"] = serializers.SerializerMethodField(
            method_name="get_field_definitions"
        )
        return declared

    @extend_schema_field(
        serializers.ListField(child=serializers.DictField(), help_text=FIELD_LIST_HELP)
    )
    def get_field_definitions(self, obj):
        return field_list(obj.configuration)


class ResourceSerializer(serializers.ModelSerializer):
    """A resource as the web reads it (docs/web_api_spec.md, snake_case)."""

    resource_type_id = serializers.UUIDField(read_only=True)
    resource_type_key = serializers.CharField(
        source="resource_type.code", read_only=True
    )
    label = serializers.CharField(source="name", read_only=True)
    # null when the resource has no status
    status = serializers.CharField(source="status.code", read_only=True, default=None)
    custom_field_values = serializers.JSONField(source="configuration", read_only=True)

    class Meta:
        model = Resource
        fields = [
            "id",
            "resource_type_id",
            "resource_type_key",
            "code",
            "label",
            "status",
            "custom_field_values",
            "created_at",
            "updated_at",
        ]


class EditResourceSerializer(serializers.ModelSerializer):
    """
    Create / update a resource: resource_type_id, label, custom_field_values
    (stored in name and configuration); code is made from the label when it is not sent.
    """

    resource_type_id = serializers.PrimaryKeyRelatedField(
        source="resource_type",
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
    # not sent: made from the label on create, kept on update
    code = serializers.CharField(
        max_length=50,
        required=False,
        error_messages={
            "blank": "Resource code cannot be empty!",
            "max_length": "Resource code cannot exceed 50 characters!",
        },
    )
    label = serializers.CharField(
        source="name",
        max_length=150,
        error_messages={
            "required": "Please enter resource label!",
            "blank": "Resource label cannot be empty!",
            "max_length": "Resource label cannot exceed 150 characters!",
        },
    )
    # a code from the status list of the resource type, checked in validate(); blank = no status
    status = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    # values of the custom fields of the resource type (fields with scope "resource")
    custom_field_values = serializers.JSONField(
        source="configuration",
        required=False,
        error_messages={
            "invalid": "Custom field values must be valid JSON!",
        },
    )

    class Meta:
        model = Resource
        fields = [
            "id",
            "resource_type_id",
            "code",
            "label",
            "status",
            "custom_field_values",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        # uniqueness is checked in validate() to return a custom message
        validators = []

    def validate_custom_field_values(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Custom field values must be an object!")
        return value

    def validate(self, data):
        resource_type = data.get(
            "resource_type", getattr(self.instance, "resource_type", None)
        )
        data["status"] = self.resolve_status(resource_type, data.get("status", ...))

        code = data.get("code", getattr(self.instance, "code", None))
        if code is None:
            code = data["code"] = self.code_from_label(resource_type, data["name"])
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
            raise serializers.ValidationError(
                {"custom_field_values": configuration_errors}
            )
        data["configuration"] = configuration
        return data

    @staticmethod
    def code_from_label(resource_type, label):
        """
        A code unique in the resource type,
        eg "Phone Booth 1" -> PHONE_BOOTH_1 (_2, _3... when taken).
        """
        base = re.sub(r"[^A-Z0-9]+", "_", label.upper()).strip("_")[:44] or "RESOURCE"
        codes = set(
            Resource.objects.filter(
                resource_type=resource_type, code__startswith=base
            ).values_list("code", flat=True)
        )
        code, number = base, 1
        while code in codes:
            number += 1
            code = f"{base}_{number}"
        return code

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
    """
    Create / update a resource type with key, label and a list of fields
    (stored in configuration["fields"] + configuration["field_order"]).
    """

    key = serializers.CharField(
        source="code",
        max_length=50,
        error_messages={
            "required": "Please enter resource type key!",
            "blank": "Resource type key cannot be empty!",
            "max_length": "Resource type key cannot exceed 50 characters!",
        },
    )
    label = serializers.CharField(
        source="name",
        max_length=100,
        error_messages={
            "required": "Please enter resource type label!",
            "blank": "Resource type label cannot be empty!",
            "max_length": "Resource type label cannot exceed 100 characters!",
        },
    )
    # master data list of the resource statuses,
    # kept in configuration["status_enum_type"]
    status_enum_type = serializers.CharField(required=False, write_only=True)
    # when the status list changes: {old status code: new status code}
    status_mapping = serializers.JSONField(required=False, write_only=True)
    # optimistic locking: the version the client read, required on update
    base_version = serializers.IntegerField(
        required=False,
        write_only=True,
        min_value=1,
        error_messages={"invalid": "Base version must be a number!"},
    )

    class Meta:
        model = ResourceType
        fields = [
            "id",
            "key",
            "label",
            "status_enum_type",
            "status_mapping",
            "base_version",
        ]
        read_only_fields = ["id"]

    def get_fields(self):
        # "fields" cannot be a class attribute: Serializer.fields is taken by DRF
        declared = super().get_fields()
        declared["fields"] = serializers.ListField(
            child=serializers.DictField(),
            required=False,
            write_only=True,
            help_text=FIELD_LIST_HELP,
            error_messages={"not_a_list": "Fields must be a list!"},
        )
        return declared

    def validate_key(self, value):
        # keys created before the spec (eg MEETING_ROOM) can be sent back unchanged
        unchanged = self.instance is not None and value == self.instance.code
        if not unchanged and not KEY_PATTERN.match(value):
            raise serializers.ValidationError(KEY_PATTERN_MESSAGE)
        duplicates = ResourceType.objects.filter(code=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                f"Resource type key '{value}' already exists!"
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
            if status_type in NOT_RESOURCE_STATUS_TYPES:
                raise serializers.ValidationError(
                    {
                        "status_enum_type": [
                            f"{status_type} is not a list of resource statuses!"
                        ]
                    }
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
        self.check_base_version(data.pop("base_version", None))
        configuration = dict(getattr(self.instance, "configuration", None) or {})
        if "fields" in data:
            configuration["fields"], configuration[FIELD_ORDER] = self.fields_to_object(
                data.pop("fields")
            )
        if "status_enum_type" in data:
            configuration["status_enum_type"] = data.pop("status_enum_type")
        data["configuration"] = self.validate_configuration(configuration)

        mapping = data.pop("status_mapping", None) or {}
        self.status_moves = []
        if self.instance is not None:
            status_type = configuration.get("status_enum_type") or DEFAULT_RESOURCE_STATUS_TYPE
            self.status_moves = self.plan_status_moves(status_type, mapping)
        return data

    def check_base_version(self, base_version):
        """
        An update must be based on the current version
        (someone else may have saved first).
        """
        if self.instance is None:
            return
        if base_version is None:
            raise serializers.ValidationError(
                {"base_version": ["Please send the version you read (base_version)!"]}
            )
        if base_version != self.instance.version:
            raise serializers.ValidationError(
                {
                    "base_version": [
                        f"Resource type was changed by someone else (now version "
                        f"{self.instance.version}), reload it!"
                    ]
                },
                code="stale_version",
            )

    def fields_to_object(self, items):
        """[{"key": "capacity", ...}] -> ({"capacity": {...}}, ["capacity"])."""
        fields, errors = {}, []
        for position, item in enumerate(items):
            definition = dict(item)
            key = definition.pop("key", None)
            if not isinstance(key, str) or not KEY_PATTERN.match(key):
                errors.append(
                    f"Field {position + 1}: key {KEY_PATTERN_MESSAGE.lower()}!"
                )
            elif key in fields:
                errors.append(f"Field {position + 1}: key '{key}' is used twice!")
            else:
                fields[key] = definition
        if errors:
            raise serializers.ValidationError({"fields": errors})
        return fields, list(fields)

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
        validated_data["version"] = instance.version + 1
        instance = super().update(instance, validated_data)
        for status_id, status in self.status_moves:
            instance.resources.filter(status_id=status_id).update(status=status)
        return instance
