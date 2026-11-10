from drf_spectacular.utils import OpenApiParameter

from core.serializers.resource_serializers import (
    EditResourceSerializer,
    EditResourceTypeSerializer,
    ResourceSerializer,
    ResourceTypeSerializer,
)
from core.utils import AUTH_ERRORS, error_responses, success_response

list_resource_description = {
    "summary": "Get list of resources",
    "description": "get list of resources",
    "parameters": [
        OpenApiParameter(
            "page", int, required=False, default=1, description="Page number"
        ),
        OpenApiParameter(
            "page_size",
            int,
            required=False,
            default=5,
            description="Number of resources per page.",
        ),
        OpenApiParameter(
            "resource_type_id",
            str,
            required=False,
            description="Filter by resource type ID (UUID)",
        ),
        OpenApiParameter(
            "resource_type_key",
            str,
            required=False,
            description="Filter by resource type key, eg: phone_booth",
        ),
        OpenApiParameter(
            "status",
            str,
            required=False,
            description="Filter by status code",
        ),
        OpenApiParameter("code", str, required=False, description="Exact resource code"),
        OpenApiParameter(
            "label__icontains", str, required=False, description="Label contains"
        ),
    ],
    "responses": {
        200: success_response(ResourceSerializer, "page"),
        **error_responses(*AUTH_ERRORS, "VALIDATION_FAILED"),
    },
}

resource_id_parameter = OpenApiParameter(
    "id",
    type=str,
    location=OpenApiParameter.PATH,
    description="UUID of the resource",
)

retrieve_resource_description = {
    "parameters": [resource_id_parameter],
    "summary": "Get resource detail",
    "description": "Get a resource with its custom field values",
    "responses": {
        200: success_response(ResourceSerializer),
        **error_responses(*AUTH_ERRORS, "NOT_FOUND"),
    },
}

create_resource_description = {
    "summary": "Create resource",
    "description": "Create a new resource",
    "request": EditResourceSerializer,
    "responses": {
        201: success_response(ResourceSerializer),
        **error_responses(*AUTH_ERRORS, "VALIDATION_FAILED"),
    },
}

update_resource_description = {
    "parameters": [resource_id_parameter],
    "summary": "Update resource",
    "description": "Update an existing resource",
    "request": EditResourceSerializer,
    "responses": {
        200: success_response(ResourceSerializer),
        **error_responses(*AUTH_ERRORS, "NOT_FOUND", "VALIDATION_FAILED"),
    },
}

delete_resource_description = {
    "parameters": [resource_id_parameter],
    "summary": "Delete resource",
    "description": "Delete a resource",
    "responses": {
        200: success_response(),
        **error_responses(*AUTH_ERRORS, "NOT_FOUND"),
    },
}

create_resource_type_description = {
    "summary": "Create resource type",
    "description": "Create a new resource type",
    "request": EditResourceTypeSerializer,
    "responses": {
        201: success_response(ResourceTypeSerializer),
        **error_responses(*AUTH_ERRORS, "VALIDATION_FAILED"),
    },
}

list_resource_type_description = {
    "summary": "Get list of resource types",
    "description": "get list of resource types",
    "parameters": [
        OpenApiParameter(
            "page", int, required=False, default=1, description="Page number"
        ),
        OpenApiParameter(
            "page_size",
            int,
            required=False,
            default=5,
            description="Number of resource types per page.",
        ),
        OpenApiParameter(
            "code", str, required=False, description="Exact resource type code"
        ),
        OpenApiParameter(
            "name", str, required=False, description="Exact resource type name"
        ),
    ],
    "responses": {
        200: success_response(ResourceTypeSerializer, "page"),
        **error_responses(*AUTH_ERRORS),
    },
}

resource_type_id_parameter = OpenApiParameter(
    "id",
    type=str,
    location=OpenApiParameter.PATH,
    description="UUID of the resource type",
)

retrieve_resource_type_description = {
    "parameters": [resource_type_id_parameter],
    "summary": "Get resource type detail",
    "description": "Get a resource type with its list of fields",
    "responses": {
        200: success_response(ResourceTypeSerializer),
        **error_responses(*AUTH_ERRORS, "NOT_FOUND"),
    },
}

update_resource_type_description = {
    "parameters": [resource_type_id_parameter],
    "summary": "Update resource type",
    "description": (
        "Update only the fields that are sent. `base_version` (the version that was read) is "
        "required: when someone else saved first the answer is 409 STALE_VERSION. "
        "The version goes up by one after each update."
    ),
    "request": EditResourceTypeSerializer,
    "responses": {
        200: success_response(ResourceTypeSerializer),
        **error_responses(*AUTH_ERRORS, "NOT_FOUND", "STALE_VERSION", "VALIDATION_FAILED"),
    },
}

delete_resource_type_description = {
    "parameters": [resource_type_id_parameter],
    "summary": "Delete resource type",
    "description": "Delete a resource type",
    "responses": {
        200: success_response(),
        **error_responses(*AUTH_ERRORS, "NOT_FOUND"),
    },
}
