from drf_spectacular.utils import OpenApiParameter

from core.serializers.master_data_serializers import (
    EnumDefinitionSerializer,
    EnumGroupSerializer,
    EnumTypeSerializer,
)


def id_parameter(description):
    return OpenApiParameter(
        "id", type=str, location=OpenApiParameter.PATH, description=description
    )



# ---------- enum types ----------

list_enum_types_document = {
    "summary": "Get list of enum types",
    "description": "Any logged in user.",
    "responses": {200: EnumTypeSerializer(many=True)},
}

retrieve_enum_type_document = {
    "parameters": [id_parameter("UUID of the enum type")],
    "summary": "Get enum type detail",
    "description": "Any logged in user.",
    "responses": {200: EnumTypeSerializer},
}

create_enum_type_document = {
    "summary": "Create enum type",
    "description": "Admin only. eg: PAYMENT_METHOD",
    "request": EnumTypeSerializer,
    "responses": {201: EnumTypeSerializer},
}

update_enum_type_document = {
    "parameters": [id_parameter("UUID of the enum type")],
    "summary": "Update enum type",
    "description": "Admin only. System enum types cannot change code.",
    "request": EnumTypeSerializer,
    "responses": {200: EnumTypeSerializer},
}

delete_enum_type_document = {
    "parameters": [id_parameter("UUID of the enum type")],
    "summary": "Delete enum type",
    "description": "Admin only. System enum types and types that still have values cannot be deleted.",
    "responses": {200: None},
}

# ---------- enum definitions ----------

list_enum_definitions_document = {
    "summary": "Get enum values grouped by enum type",
    "description": "Any logged in user. Each enum type with its values, eg: RESOURCE_STATUS -> ACTIVE, INACTIVE, MAINTENANCE. Filter: ?enum_type=BOOKING_STATUS&is_active=true",
    "parameters": [
        OpenApiParameter("enum_type", str, required=False, description="eg: BOOKING_STATUS"),
        OpenApiParameter("code", str, required=False, description="eg: CONFIRMED"),
        OpenApiParameter("is_active", bool, required=False, description="Active values only"),
    ],
    "responses": {200: EnumGroupSerializer(many=True)},
}

retrieve_enum_definition_document = {
    "parameters": [id_parameter("UUID of the enum value")],
    "summary": "Get enum value detail",
    "description": "Any logged in user.",
    "responses": {200: EnumDefinitionSerializer},
}

create_enum_definition_document = {
    "summary": "Create enum value",
    "description": "Admin only. eg: BOOKING_STATUS -> NO_SHOW",
    "request": EnumDefinitionSerializer,
    "responses": {201: EnumDefinitionSerializer},
}

update_enum_definition_document = {
    "parameters": [id_parameter("UUID of the enum value")],
    "summary": "Update enum value",
    "description": "Admin only. System values keep their type and code and stay active.",
    "request": EnumDefinitionSerializer,
    "responses": {200: EnumDefinitionSerializer},
}

delete_enum_definition_document = {
    "parameters": [id_parameter("UUID of the enum value")],
    "summary": "Delete enum value",
    "description": "Admin only. System values and values in use cannot be deleted; deactivate them instead.",
    "responses": {200: None},
}
