from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from core.filters import ResourceFilter, ResourceTypeFilter
from core.models import Resource, ResourceType
from core.paginators import CustomPaginator
from core.serializers.resource_serializers import (
    EditResourceSerializer,
    EditResourceTypeSerializer,
    ResourceSerializer,
    ResourceTypeSerializer,
)
from core.utils import WebApiMixin, get_instance, response_success

from .documents import (
    create_resource_description,
    create_resource_type_description,
    delete_resource_description,
    delete_resource_type_description,
    list_resource_description,
    list_resource_type_description,
    retrieve_resource_description,
    retrieve_resource_type_description,
    update_resource_description,
    update_resource_type_description,
)


class ResourceViewSet(WebApiMixin, viewsets.ViewSet):

    @extend_schema(**list_resource_description)
    def list(self, request):
        resource_filter = ResourceFilter(
            request.query_params,
            queryset=Resource.objects.select_related(
                "resource_type", "status"
            ).order_by("name"),
        )
        if not resource_filter.is_valid():
            raise ValidationError(resource_filter.errors)
        paginator = CustomPaginator()
        page = paginator.paginate_queryset(resource_filter.qs, request)
        serializer = ResourceSerializer(page, many=True)
        return paginator.get_paginated_response(
            serializer.data, "Resources retrieved successfully!"
        )

    @extend_schema(**create_resource_description)
    def create(self, request):
        serializer = EditResourceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resource = serializer.save()
        return response_success(
            ResourceSerializer(resource).data,
            "Resource created successfully!",
            status.HTTP_201_CREATED,
        )

    @extend_schema(**retrieve_resource_description)
    def retrieve(self, request, pk=None):
        resource = get_instance(Resource, pk)
        return response_success(
            ResourceSerializer(resource).data, "Resource retrieved successfully!"
        )

    @extend_schema(**update_resource_description)
    def update(self, request, pk=None):
        resource = get_instance(Resource, pk)
        serializer = EditResourceSerializer(resource, data=request.data)
        serializer.is_valid(raise_exception=True)
        resource = serializer.save()
        return response_success(
            ResourceSerializer(resource).data, "Resource updated successfully!"
        )

    @extend_schema(**delete_resource_description)
    def destroy(self, request, pk=None):
        resource = get_instance(Resource, pk)
        resource.delete()
        return response_success(message="Resource deleted successfully!")


class ResourceTypeViewSet(WebApiMixin, viewsets.ViewSet):

    @extend_schema(**list_resource_type_description)
    def list(self, request):
        resource_types = ResourceTypeFilter(
            request.query_params,
            queryset=ResourceType.objects.order_by("name"),
        ).qs
        paginator = CustomPaginator()
        page = paginator.paginate_queryset(resource_types, request)
        serializer = ResourceTypeSerializer(page, many=True)
        return paginator.get_paginated_response(
            serializer.data, "Resource types retrieved successfully!"
        )

    @extend_schema(**create_resource_type_description)
    def create(self, request):
        serializer = EditResourceTypeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response_success(
            ResourceTypeSerializer(serializer.instance).data,
            "Resource type created successfully!",
            status.HTTP_201_CREATED,
        )

    @extend_schema(**retrieve_resource_type_description)
    def retrieve(self, request, pk=None):
        return response_success(
            ResourceTypeSerializer(get_instance(ResourceType, pk)).data,
            "Resource type retrieved successfully!",
        )

    @extend_schema(**update_resource_type_description)
    @transaction.atomic
    def partial_update(self, request, pk=None):
        get_instance(ResourceType, pk)  # 404 for an unknown or invalid id
        # lock the row: two updates based on the same version cannot both pass
        resource_type = ResourceType.objects.select_for_update().get(pk=pk)
        serializer = EditResourceTypeSerializer(
            resource_type, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response_success(
            ResourceTypeSerializer(serializer.instance).data,
            "Resource type updated successfully!",
        )

    @extend_schema(**delete_resource_type_description)
    def destroy(self, request, pk=None):
        resource_type = get_instance(ResourceType, pk)
        resource_type.delete()
        return response_success(message="Resource type deleted successfully!")
