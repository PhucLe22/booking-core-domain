from django.db.models import ProtectedError
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.constant import SYSTEM_ENUM_TYPES
from core.filters import EnumDefinitionFilter
from core.middlewares.login_required import LOGIN_REQUIRED
from core.middlewares.staff import AdminMiddleware
from core.models import EnumDefinition, EnumType
from core.paginators import CustomPaginator
from core.serializers.master_data_serializers import (
    EnumDefinitionSerializer,
    EnumGroupSerializer,
    EnumTypeSerializer,
)
from core.utils import get_instance, response_errors, response_success

from .documents import (
    create_enum_definition_document,
    create_enum_type_document,
    delete_enum_definition_document,
    delete_enum_type_document,
    list_enum_definitions_document,
    list_enum_types_document,
    retrieve_enum_definition_document,
    retrieve_enum_type_document,
    update_enum_definition_document,
    update_enum_type_document,
)


class MasterDataViewSet(viewsets.ViewSet):
    """Every logged in user can read master data; only admin can change it."""

    authentication_classes = [JWTAuthentication]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [cls() for cls in LOGIN_REQUIRED]
        return [cls() for cls in [*LOGIN_REQUIRED, AdminMiddleware]]

    def paginated(self, filterset, serializer_class, message):
        if not filterset.is_valid():
            return response_errors(filterset.errors)
        paginator = CustomPaginator()
        page = paginator.paginate_queryset(filterset.qs, self.request)
        return paginator.get_paginated_response(
            serializer_class(page, many=True).data, message
        )

    def save(self, serializer, message, status_code=status.HTTP_200_OK):
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        serializer.save()
        return response_success(serializer.data, message, status_code)


# =========================================================
# ENUM TYPE
# =========================================================


class EnumTypeViewSet(MasterDataViewSet):
    @extend_schema(**list_enum_types_document)
    def list(self, request):
        enum_types = EnumType.objects.prefetch_related("definitions").order_by("code")
        return response_success(
            EnumTypeSerializer(enum_types, many=True).data,
            "Enum types retrieved successfully!",
        )

    @extend_schema(**retrieve_enum_type_document)
    def retrieve(self, request, pk=None):
        return response_success(
            EnumTypeSerializer(get_instance(EnumType, pk)).data,
            "Enum type retrieved successfully!",
        )

    @extend_schema(**create_enum_type_document)
    def create(self, request):
        return self.save(
            EnumTypeSerializer(data=request.data),
            "Enum type created successfully!",
            status.HTTP_201_CREATED,
        )

    @extend_schema(**update_enum_type_document)
    def update(self, request, pk=None):
        return self.save(
            EnumTypeSerializer(get_instance(EnumType, pk), data=request.data),
            "Enum type updated successfully!",
        )

    @extend_schema(**delete_enum_type_document)
    def destroy(self, request, pk=None):
        enum_type = get_instance(EnumType, pk)
        if enum_type.code in SYSTEM_ENUM_TYPES:
            return response_errors({"id": ["System enum type cannot be deleted!"]})
        if enum_type.definitions.exists():
            return response_errors(
                {"id": ["Enum type still has values; delete them first!"]}
            )
        enum_type.delete()
        return response_success(message="Enum type deleted successfully!")


# =========================================================
# ENUM DEFINITION
# =========================================================


class EnumDefinitionViewSet(MasterDataViewSet):
    @extend_schema(**list_enum_definitions_document)
    def list(self, request):
        definitions = EnumDefinitionFilter(
            request.query_params,
            queryset=EnumDefinition.objects.select_related("enum_type").order_by(
                "enum_type__code", "position", "code"
            ),
        )
        if not definitions.is_valid():
            return response_errors(definitions.errors)

        # group the values under their enum type, eg:
        # RESOURCE_STATUS -> [ACTIVE, INACTIVE, MAINTENANCE]
        groups = {}
        for definition in definitions.qs:
            enum_type = definition.enum_type
            group = groups.setdefault(
                enum_type.pk,
                {
                    "code": enum_type.code,
                    "name": enum_type.name,
                    "description": enum_type.description,
                    "definitions": [],
                },
            )
            group["definitions"].append(definition)
        return response_success(
            EnumGroupSerializer(groups.values(), many=True).data,
            "Enum values retrieved successfully!",
        )

    @extend_schema(**retrieve_enum_definition_document)
    def retrieve(self, request, pk=None):
        return response_success(
            EnumDefinitionSerializer(get_instance(EnumDefinition, pk)).data,
            "Enum value retrieved successfully!",
        )

    @extend_schema(**create_enum_definition_document)
    def create(self, request):
        return self.save(
            EnumDefinitionSerializer(data=request.data),
            "Enum value created successfully!",
            status.HTTP_201_CREATED,
        )

    @extend_schema(**update_enum_definition_document)
    def update(self, request, pk=None):
        return self.save(
            EnumDefinitionSerializer(
                get_instance(EnumDefinition, pk), data=request.data
            ),
            "Enum value updated successfully!",
        )

    @extend_schema(**delete_enum_definition_document)
    def destroy(self, request, pk=None):
        definition = get_instance(EnumDefinition, pk)
        if definition.is_system:
            return response_errors({"id": ["System value cannot be deleted!"]})
        try:
            definition.delete()
        except ProtectedError:
            return response_errors(
                {"id": ["Value is still in use; set is_active=false instead!"]}
            )
        return response_success(message="Enum value deleted successfully!")

