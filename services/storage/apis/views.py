from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import FileResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.constant import STAFF_ROLE_CODES
from core.filters import FileAttachmentFilter, FolderFilter, StoredFileFilter
from core.middlewares.login_required import LOGIN_REQUIRED
from core.middlewares.staff import AdminMiddleware
from core.models import FileAttachment, Folder, StorageConfig, StoredFile
from core.paginators import CustomPaginator
from core.serializers.storage_serializers import (
    FileAttachmentSerializer,
    FolderSerializer,
    StorageConfigSerializer,
    StoredFileSerializer,
    UpdateFileSerializer,
    UploadFileSerializer,
)
from core.storage import get_storage
from core.utils import get_instance, response_errors, response_success

from .documents import (
    create_attachment_document,
    create_folder_document,
    create_storage_config_document,
    delete_attachment_document,
    delete_file_document,
    delete_folder_document,
    delete_storage_config_document,
    download_file_document,
    list_attachments_document,
    list_files_document,
    list_folders_document,
    list_storage_configs_document,
    retrieve_file_document,
    retrieve_folder_document,
    update_file_document,
    update_folder_document,
    update_storage_config_document,
    upload_file_document,
)


class OwnedObjectsMixin:
    """
    Admin and staff see every object; other users only see their own.
    owner_field is the field that holds the owner of the object.
    """

    owner_field = None

    def is_manager(self, user):
        return user.has_role(*STAFF_ROLE_CODES)

    def visible(self, queryset):
        user = self.request.user
        if self.is_manager(user):
            return queryset
        return queryset.filter(**{self.owner_field: user})

    def can_access(self, obj, owner_field=None):
        user = self.request.user
        owner_id = getattr(obj, f"{owner_field or self.owner_field}_id")
        return self.is_manager(user) or owner_id == user.pk

    def get_visible(self, model, pk):
        try:
            return self.visible(model.objects.all()).get(pk=pk)
        except (model.DoesNotExist, DjangoValidationError, ValueError):
            raise NotFound(f"No {model.__name__} matches the given query!")

    def serializer_context(self):
        return {
            "user": self.request.user,
            "can_access": lambda obj: self.can_access(
                obj,
                "created_by" if isinstance(obj, Folder) else "uploaded_by",
            ),
        }

    def paginated(self, filterset, serializer_class, message):
        if not filterset.is_valid():
            return response_errors(filterset.errors)
        paginator = CustomPaginator()
        page = paginator.paginate_queryset(filterset.qs, self.request)
        return paginator.get_paginated_response(
            serializer_class(page, many=True).data, message
        )


# =========================================================
# STORAGE CONFIG (admin)
# =========================================================


class StorageConfigViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [*LOGIN_REQUIRED, AdminMiddleware]

    @extend_schema(**list_storage_configs_document)
    def list(self, request):
        configs = StorageConfig.objects.order_by("code")
        return response_success(
            StorageConfigSerializer(configs, many=True).data,
            "Storage configs retrieved successfully!",
        )

    @extend_schema(**create_storage_config_document)
    def create(self, request):
        serializer = StorageConfigSerializer(data=request.data)
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        serializer.save()
        return response_success(
            serializer.data,
            "Storage config created successfully!",
            status.HTTP_201_CREATED,
        )

    @extend_schema(**update_storage_config_document)
    def update(self, request, pk=None):
        serializer = StorageConfigSerializer(
            get_instance(StorageConfig, pk), data=request.data
        )
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        serializer.save()
        return response_success(serializer.data, "Storage config updated successfully!")

    @extend_schema(**delete_storage_config_document)
    def destroy(self, request, pk=None):
        config = get_instance(StorageConfig, pk)
        if config.files.exists():
            return response_errors({"id": ["Storage config still has files!"]})
        config.delete()
        return response_success(message="Storage config deleted successfully!")


# =========================================================
# FOLDER
# =========================================================


class FolderViewSet(OwnedObjectsMixin, viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = LOGIN_REQUIRED
    owner_field = "created_by"

    @extend_schema(**list_folders_document)
    def list(self, request):
        folders = FolderFilter(
            request.query_params,
            queryset=self.visible(Folder.objects.all()).order_by("name"),
        )
        return self.paginated(
            folders, FolderSerializer, "Folders retrieved successfully!"
        )

    @extend_schema(**retrieve_folder_document)
    def retrieve(self, request, pk=None):
        folder = self.get_visible(Folder, pk)
        return response_success(
            FolderSerializer(folder).data, "Folder retrieved successfully!"
        )

    @extend_schema(**create_folder_document)
    def create(self, request):
        serializer = FolderSerializer(
            data=request.data, context=self.serializer_context()
        )
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        serializer.save(created_by=request.user)
        return response_success(
            serializer.data, "Folder created successfully!", status.HTTP_201_CREATED
        )

    @extend_schema(**update_folder_document)
    def update(self, request, pk=None):
        serializer = FolderSerializer(
            self.get_visible(Folder, pk),
            data=request.data,
            context=self.serializer_context(),
        )
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        serializer.save()
        return response_success(serializer.data, "Folder updated successfully!")

    @extend_schema(**delete_folder_document)
    def destroy(self, request, pk=None):
        # subfolders are deleted too; their files are kept and moved to the root
        self.get_visible(Folder, pk).delete()
        return response_success(message="Folder deleted successfully!")


# =========================================================
# FILE
# =========================================================


class StoredFileViewSet(OwnedObjectsMixin, viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = LOGIN_REQUIRED
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    owner_field = "uploaded_by"

    @extend_schema(**list_files_document)
    def list(self, request):
        files = StoredFileFilter(
            request.query_params,
            queryset=self.visible(
                StoredFile.objects.select_related("storage_config")
            ).order_by("-created_at"),
        )
        return self.paginated(
            files, StoredFileSerializer, "Files retrieved successfully!"
        )

    @extend_schema(**retrieve_file_document)
    def retrieve(self, request, pk=None):
        return response_success(
            StoredFileSerializer(self.get_visible(StoredFile, pk)).data,
            "File retrieved successfully!",
        )

    @extend_schema(**upload_file_document)
    def create(self, request):
        serializer = UploadFileSerializer(
            data=request.data, context=self.serializer_context()
        )
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        stored_file = serializer.save()
        data = StoredFileSerializer(stored_file).data
        if serializer.attachment is not None:
            data["attachment"] = {
                "id": serializer.attachment.pk,
                "object_type": serializer.validated_data["object_type"],
                "object_id": serializer.attachment.object_id,
                "purpose": serializer.attachment.purpose,
            }
            message = "File uploaded and attached successfully!"
        else:
            message = "File uploaded successfully!"
        return response_success(data, message, status.HTTP_201_CREATED)

    @extend_schema(**update_file_document)
    def update(self, request, pk=None):
        stored_file = self.get_visible(StoredFile, pk)
        serializer = UpdateFileSerializer(
            stored_file, data=request.data, context=self.serializer_context()
        )
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        serializer.save()
        return response_success(
            StoredFileSerializer(stored_file).data, "File updated successfully!"
        )

    @extend_schema(**delete_file_document)
    @transaction.atomic
    def destroy(self, request, pk=None):
        stored_file = self.get_visible(StoredFile, pk)
        storage = get_storage(stored_file.storage_config)
        storage_key = stored_file.storage_key
        stored_file.delete()  # its attachments are deleted too
        # remove the content only once the row is really gone
        transaction.on_commit(lambda: storage.delete(storage_key))
        return response_success(message="File deleted successfully!")

    @extend_schema(**download_file_document)
    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        stored_file = self.get_visible(StoredFile, pk)
        storage = get_storage(stored_file.storage_config)
        if not storage.exists(stored_file.storage_key):
            raise NotFound("File content is missing from storage!")
        return FileResponse(
            storage.open(stored_file.storage_key, "rb"),
            as_attachment=True,
            filename=stored_file.original_name,
            content_type=stored_file.mime_type or "application/octet-stream",
        )


# =========================================================
# FILE ATTACHMENT
# =========================================================


class FileAttachmentViewSet(OwnedObjectsMixin, viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = LOGIN_REQUIRED
    owner_field = "file__uploaded_by"

    def can_access_attachment(self, attachment):
        return self.can_access(attachment.file, "uploaded_by")

    @extend_schema(**list_attachments_document)
    def list(self, request):
        attachments = FileAttachmentFilter(
            request.query_params,
            queryset=self.visible(
                FileAttachment.objects.select_related(
                    "file", "file__storage_config", "content_type"
                )
            ).order_by("-created_at"),
        )
        return self.paginated(
            attachments, FileAttachmentSerializer, "Attachments retrieved successfully!"
        )

    @extend_schema(**create_attachment_document)
    def create(self, request):
        serializer = FileAttachmentSerializer(
            data=request.data, context=self.serializer_context()
        )
        if not serializer.is_valid():
            return response_errors(serializer.errors)
        serializer.save()
        return response_success(
            serializer.data, "File attached successfully!", status.HTTP_201_CREATED
        )

    @extend_schema(**delete_attachment_document)
    def destroy(self, request, pk=None):
        # only the link is removed, the file itself is kept
        self.get_visible(FileAttachment, pk).delete()
        return response_success(message="File detached successfully!")
