from core.serializers.resource_serializers import (
    EditResourceSerializer,
    EditResourceTypeSerializer,
    ResourceSerializer,
    ResourceTypeSerializer,
)
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse
from rest_framework.exceptions import NotFound

from core.serializers.notification_serializers import NotificationSerializer

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
            "resource_type",
            str,
            required=False,
            description="Filter by resource type ID (UUID)",
        ),
        OpenApiParameter(
            "resource_type_code",
            str,
            required=False,
            description="Filter by resource type code",
        ),
        OpenApiParameter(
            "status",
            str,
            required=False,
            description="Filter by status code",
        ),
    ],
    "responses": {200: ResourceSerializer(many=True)},
}

resource_id_parameter = OpenApiParameter(
    "id",
    type=str,
    location=OpenApiParameter.PATH,
    description="UUID of the resource",
)

create_resource_description = {
    "summary": "Create resource",
    "description": "Create a new resource",
    "request": EditResourceSerializer,
    "responses": {201: ResourceSerializer},
}

update_resource_description = {
    "parameters": [resource_id_parameter],
    "summary": "Update resource",
    "description": "Update an existing resource",
    "request": EditResourceSerializer,
    "responses": {200: ResourceSerializer},
}

delete_resource_description = {
    "parameters": [resource_id_parameter],
    "summary": "Delete resource",
    "description": "Delete a resource",
    "responses": {200: None},
}

create_resource_type_description = {
    "summary": "Create resource type",
    "description": "Create a new resource type",
    "request": EditResourceTypeSerializer,
    "responses": {201: ResourceTypeSerializer},
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
    "responses": {200: ResourceTypeSerializer(many=True)},
}

resource_type_id_parameter = OpenApiParameter(
    "id",
    type=str,
    location=OpenApiParameter.PATH,
    description="UUID of the resource type",
)

update_resource_type_description = {
    "parameters": [resource_type_id_parameter],
    "summary": "Update resource type",
    "description": "Update an existing resource type",
    "request": EditResourceTypeSerializer,
    "responses": {200: EditResourceTypeSerializer},
}

delete_resource_type_description = {
    "parameters": [resource_type_id_parameter],
    "summary": "Delete resource type",
    "description": "Delete a resource type",
    "responses": {200: None},
}
