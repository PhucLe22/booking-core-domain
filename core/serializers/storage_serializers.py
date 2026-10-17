import mimetypes
import os

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from rest_framework import serializers

from core.models import (
    Booking,
    Comment,
    FileAttachment,
    Folder,
    Resource,
    ResourceType,
    StorageConfig,
    StoredFile,
    User,
)
from core.storage import (
    KNOWN_PROVIDERS,
    STORAGE_PATH_PATTERN,
    build_storage_key,
    ensure_storage_directory,
    file_checksum,
    get_storage,
    storage_path,
)

# configuration must not hold credentials (keys are matched case-insensitively)
SECRET_KEY_HINTS = ["secret", "password", "access_key", "token", "credential"]

# object_type accepted by attachments -> model
ATTACHABLE_MODELS = {
    "booking": Booking,
    "resource": Resource,
    "resource_type": ResourceType,
    "comment": Comment,
    "user": User,
}


def find_secret_keys(value, path=""):
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            if any(hint in str(key).lower() for hint in SECRET_KEY_HINTS):
                found.append(key_path)
            found.extend(find_secret_keys(item, key_path))
    return found


# =========================================================
# STORAGE CONFIG
# =========================================================


class StorageConfigSerializer(serializers.ModelSerializer):
    code = serializers.CharField(
        max_length=50,
        error_messages={
            "required": "Please enter storage code!",
            "blank": "Storage code cannot be empty!",
            "max_length": "Storage code cannot exceed 50 characters!",
        },
    )
    name = serializers.CharField(
        max_length=100,
        error_messages={
            "required": "Please enter storage name!",
            "blank": "Storage name cannot be empty!",
            "max_length": "Storage name cannot exceed 100 characters!",
        },
    )
    provider = serializers.ChoiceField(
        choices=KNOWN_PROVIDERS,
        required=False,
        error_messages={"invalid_choice": "Provider must be LOCAL, S3 or MINIO!"},
    )
    configuration = serializers.JSONField(required=False)
    allowed_extensions = serializers.ListField(
        child=serializers.CharField(max_length=20),
        required=False,
        error_messages={"not_a_list": "Allowed extensions must be a list!"},
    )
    # declared explicitly so DRF does not add a unique validator from the
    # "one default storage" constraint; save() moves the default instead
    is_default = serializers.BooleanField(required=False)

    class Meta:
        model = StorageConfig
        fields = [
            "id",
            "code",
            "name",
            "provider",
            "configuration",
            "max_file_size_bytes",
            "allowed_extensions",
            "is_default",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        # is_default uniqueness is handled in save(), not by DRF
        validators = []

    def validate_code(self, value):
        value = value.strip().upper()
        duplicates = StorageConfig.objects.filter(code=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(f"Storage code '{value}' already exists!")
        return value

    def validate_configuration(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Configuration must be an object!")
        secret_keys = find_secret_keys(value)
        if secret_keys:
            raise serializers.ValidationError(
                "Do not store credentials in configuration "
                f"({', '.join(secret_keys)}); use environment variables instead!"
            )
        return value

    def validate_allowed_extensions(self, value):
        return sorted({ext.strip().lstrip(".").lower() for ext in value if ext.strip()})

    def validate(self, data):
        provider = data.get("provider", getattr(self.instance, "provider", "LOCAL"))
        if provider != "LOCAL":
            return data

        configuration = dict(
            data.get("configuration", getattr(self.instance, "configuration", {}))
        )
        # LOCAL files go to media/<path>/; the path defaults to the code
        path = configuration.get("path")
        if path is None:
            path = getattr(self.instance, "configuration", {}).get("path") or (
                data.get("code") or self.instance.code
            ).lower()
        if not isinstance(path, str):
            raise serializers.ValidationError(
                {"configuration": ["Path must be a string!"]}
            )
        path = path.strip().strip("/").lower()
        if not STORAGE_PATH_PATTERN.match(path):
            raise serializers.ValidationError(
                {
                    "configuration": [
                        "Path may only contain lowercase letters, digits, '_', '-' "
                        "and '/', eg: avatars or documents/contracts!"
                    ]
                }
            )

        others = StorageConfig.objects.filter(provider="LOCAL")
        if self.instance is not None:
            others = others.exclude(pk=self.instance.pk)
            # files are stored relative to the path, so it must not move
            if path != storage_path(self.instance) and self.instance.files.exists():
                raise serializers.ValidationError(
                    {
                        "configuration": [
                            "Path cannot change while the storage has files!"
                        ]
                    }
                )
        if any(storage_path(other) == path for other in others):
            raise serializers.ValidationError(
                {"configuration": [f"Path '{path}' is already used by another storage!"]}
            )

        configuration["path"] = path
        configuration["purposes"] = self.validate_purposes(
            configuration.get("purposes", []), others
        )
        data["configuration"] = configuration
        return data

    def validate_purposes(self, purposes, others):
        """
        configuration.purposes: uploads with one of these purposes use this
        storage, eg: ["avatar"]. A purpose can belong to one storage only.
        """
        if not isinstance(purposes, list) or not all(
            isinstance(purpose, str) for purpose in purposes
        ):
            raise serializers.ValidationError(
                {"configuration": ["Purposes must be a list of names!"]}
            )
        purposes = sorted({p.strip().lower() for p in purposes if p.strip()})
        for other in others:
            taken = set(purposes) & set(other.configuration.get("purposes", []))
            if taken:
                raise serializers.ValidationError(
                    {
                        "configuration": [
                            f"Purpose '{sorted(taken)[0]}' is already used by "
                            f"storage {other.code}!"
                        ]
                    }
                )
        return purposes

    @transaction.atomic
    def save(self, **kwargs):
        # only one default storage: setting a new default unsets the old one
        if self.validated_data.get("is_default"):
            others = StorageConfig.objects.filter(is_default=True)
            if self.instance is not None:
                others = others.exclude(pk=self.instance.pk)
            others.update(is_default=False)
        storage_config = super().save(**kwargs)
        # create media/<path>/ right away so it is visible before any upload
        ensure_storage_directory(storage_config)
        return storage_config


# =========================================================
# FOLDER
# =========================================================


class FolderSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        max_length=255,
        error_messages={
            "required": "Please enter folder name!",
            "blank": "Folder name cannot be empty!",
            "max_length": "Folder name cannot exceed 255 characters!",
        },
    )
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Folder.objects.all(),
        required=False,
        allow_null=True,
        pk_field=serializers.UUIDField(
            error_messages={"invalid": "Parent folder ID is not a valid UUID!"}
        ),
        error_messages={"does_not_exist": "Parent folder does not exist!"},
    )
    configuration = serializers.JSONField(required=False)
    children_count = serializers.SerializerMethodField()
    files_count = serializers.SerializerMethodField()

    class Meta:
        model = Folder
        fields = [
            "id",
            "name",
            "parent",
            "created_by",
            "configuration",
            "children_count",
            "files_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def get_children_count(self, obj):
        return obj.children.count()

    def get_files_count(self, obj):
        return obj.files.count()

    def validate_parent(self, value):
        if value is None:
            return value
        if not self.context["can_access"](value):
            raise serializers.ValidationError("Parent folder does not exist!")
        # a folder cannot be moved into itself or one of its subfolders
        if self.instance is not None:
            folder = value
            while folder is not None:
                if folder.pk == self.instance.pk:
                    raise serializers.ValidationError(
                        "A folder cannot be moved into itself or its subfolder!"
                    )
                folder = folder.parent
        return value

    def validate(self, data):
        parent = data.get("parent", getattr(self.instance, "parent", None))
        name = data.get("name", getattr(self.instance, "name", None))
        owner = getattr(self.instance, "created_by", None) or self.context["user"]
        siblings = Folder.objects.filter(
            parent=parent, name__iexact=name, created_by=owner
        )
        if self.instance is not None:
            siblings = siblings.exclude(pk=self.instance.pk)
        if siblings.exists():
            raise serializers.ValidationError(
                {"name": f"Folder '{name}' already exists here!"}
            )
        return data


# =========================================================
# FILE
# =========================================================


class StoredFileSerializer(serializers.ModelSerializer):
    storage_config_code = serializers.CharField(source="storage_config.code")
    # public link that opens the file in the browser, eg:
    # http://<BE_DOMAIN>/api/v1/media/files/2026/10/<uuid>.jpg
    # (served by the storage service, through nginx on BE_DOMAIN)
    url = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = StoredFile
        fields = [
            "id",
            "original_name",
            "extension",
            "mime_type",
            "size_bytes",
            "checksum",
            "folder",
            "uploaded_by",
            "storage_config",
            "storage_config_code",
            "configuration",
            "url",
            "download_url",
            "created_at",
            "updated_at",
        ]

    def get_url(self, obj):
        if obj.storage_config.provider != "LOCAL":
            return None
        path = get_storage(obj.storage_config).url(obj.storage_key)
        return f"{os.environ.get('BE_DOMAIN', '')}{path}"

    def get_download_url(self, obj):
        return f"/api/v1/files/{obj.pk}/download/"


class UploadFileSerializer(serializers.Serializer):
    """
    Upload a file, and optionally attach it in the same call:
    file + object_type + object_id + purpose.
    Storage: storage_config if given, else the storage whose purposes include
    purpose, else the default storage.
    """

    file = serializers.FileField(
        error_messages={
            "required": "Please select a file!",
            "invalid": "Please upload a valid file!",
            "empty": "The file is empty!",
        },
    )
    folder = serializers.PrimaryKeyRelatedField(
        queryset=Folder.objects.all(),
        required=False,
        allow_null=True,
        pk_field=serializers.UUIDField(
            error_messages={"invalid": "Folder ID is not a valid UUID!"}
        ),
        error_messages={"does_not_exist": "Folder does not exist!"},
    )
    storage_config = serializers.SlugRelatedField(
        slug_field="code",
        queryset=StorageConfig.objects.filter(is_active=True),
        required=False,
        error_messages={"does_not_exist": "Storage '{value}' does not exist!"},
    )
    object_type = serializers.ChoiceField(
        choices=list(ATTACHABLE_MODELS),
        required=False,
        error_messages={
            "invalid_choice": "Object type must be one of: "
            + ", ".join(ATTACHABLE_MODELS)
            + "!",
        },
    )
    object_id = serializers.CharField(max_length=255, required=False)
    purpose = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def validate_folder(self, value):
        if value is not None and not self.context["can_access"](value):
            raise serializers.ValidationError("Folder does not exist!")
        return value

    def validate_purpose(self, value):
        return value.strip().lower()

    def validate(self, data):
        self.validate_target(data)
        storage_config = self.choose_storage(data)
        data["storage_config"] = storage_config

        uploaded = data["file"]
        extension = os.path.splitext(uploaded.name)[1].lstrip(".").lower()
        allowed = storage_config.allowed_extensions
        if allowed and extension not in allowed:
            raise serializers.ValidationError(
                {"file": [f"File type '.{extension}' is not allowed!"]}
            )
        max_size = storage_config.max_file_size_bytes
        if max_size and uploaded.size > max_size:
            raise serializers.ValidationError(
                {"file": [f"File cannot exceed {max_size} bytes!"]}
            )
        data["extension"] = extension
        return data

    def validate_target(self, data):
        """object_type and object_id go together and must point to a record."""
        object_type, object_id = data.get("object_type"), data.get("object_id")
        if not object_type and not object_id:
            return
        if not object_type or not object_id:
            raise serializers.ValidationError(
                {"object_type": ["Object type and object ID must be sent together!"]}
            )
        model = ATTACHABLE_MODELS[object_type]
        try:
            exists = model.objects.filter(pk=object_id).exists()
        except Exception:  # malformed id, eg: not a UUID
            exists = False
        if not exists:
            raise serializers.ValidationError(
                {"object_id": [f"{model.__name__} does not exist!"]}
            )
        data["content_type"] = ContentType.objects.get_for_model(model)

    def choose_storage(self, data):
        if data.get("storage_config"):
            return data["storage_config"]
        active = StorageConfig.objects.filter(is_active=True)
        purpose = data.get("purpose")
        if purpose:
            storage_config = active.filter(
                configuration__purposes__contains=[purpose]
            ).first()
            if storage_config is not None:
                return storage_config
        storage_config = active.filter(is_default=True).first()
        if storage_config is None:
            raise serializers.ValidationError(
                {"storage_config": ["No default storage is configured!"]}
            )
        return storage_config

    @transaction.atomic
    def create(self, validated_data):
        uploaded = validated_data["file"]
        storage_config = validated_data["storage_config"]
        extension = validated_data["extension"]

        storage = get_storage(storage_config)
        storage_key = storage.save(build_storage_key(extension), uploaded)
        self.attachment = None
        try:
            stored_file = StoredFile.objects.create(
                storage_config=storage_config,
                folder=validated_data.get("folder"),
                uploaded_by=self.context["user"],
                original_name=uploaded.name[:255],
                storage_key=storage_key,
                mime_type=uploaded.content_type
                or mimetypes.guess_type(uploaded.name)[0]
                or "",
                extension=extension,
                size_bytes=uploaded.size,
                checksum=file_checksum(uploaded),
            )
            if validated_data.get("content_type"):
                self.attachment = FileAttachment.objects.create(
                    file=stored_file,
                    content_type=validated_data["content_type"],
                    object_id=validated_data["object_id"],
                    purpose=validated_data.get("purpose", ""),
                )
        except Exception:
            # do not leave an orphan file in storage when the rows fail
            storage.delete(storage_key)
            raise
        return stored_file


class UpdateFileSerializer(serializers.ModelSerializer):
    """Rename a file or move it to another folder."""

    original_name = serializers.CharField(
        max_length=255,
        error_messages={
            "required": "Please enter file name!",
            "blank": "File name cannot be empty!",
            "max_length": "File name cannot exceed 255 characters!",
        },
    )
    folder = serializers.PrimaryKeyRelatedField(
        queryset=Folder.objects.all(),
        required=False,
        allow_null=True,
        pk_field=serializers.UUIDField(
            error_messages={"invalid": "Folder ID is not a valid UUID!"}
        ),
        error_messages={"does_not_exist": "Folder does not exist!"},
    )
    configuration = serializers.JSONField(required=False)

    class Meta:
        model = StoredFile
        fields = ["original_name", "folder", "configuration"]

    def validate_folder(self, value):
        if value is not None and not self.context["can_access"](value):
            raise serializers.ValidationError("Folder does not exist!")
        return value


# =========================================================
# FILE ATTACHMENT
# =========================================================


class FileAttachmentSerializer(serializers.ModelSerializer):
    file = serializers.PrimaryKeyRelatedField(
        queryset=StoredFile.objects.all(),
        pk_field=serializers.UUIDField(
            error_messages={"invalid": "File ID is not a valid UUID!"}
        ),
        error_messages={
            "required": "Please select a file!",
            "does_not_exist": "File does not exist!",
        },
    )
    object_type = serializers.ChoiceField(
        choices=list(ATTACHABLE_MODELS),
        write_only=True,
        error_messages={
            "required": "Please enter object type!",
            "invalid_choice": "Object type must be one of: "
            + ", ".join(ATTACHABLE_MODELS)
            + "!",
        },
    )
    object_id = serializers.CharField(
        max_length=255,
        error_messages={
            "required": "Please enter object ID!",
            "blank": "Object ID cannot be empty!",
        },
    )
    purpose = serializers.CharField(max_length=50, required=False, allow_blank=True)
    configuration = serializers.JSONField(required=False)
    file_detail = StoredFileSerializer(source="file", read_only=True)
    content_type = serializers.SerializerMethodField()

    class Meta:
        model = FileAttachment
        fields = [
            "id",
            "file",
            "file_detail",
            "object_type",
            "content_type",
            "object_id",
            "purpose",
            "configuration",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
        # duplicates are checked in validate() to return a custom message
        validators = []

    def get_content_type(self, obj):
        return obj.content_type.model

    def validate_file(self, value):
        if not self.context["can_access"](value):
            raise serializers.ValidationError("File does not exist!")
        return value

    def validate(self, data):
        model = ATTACHABLE_MODELS[data["object_type"]]
        try:
            exists = model.objects.filter(pk=data["object_id"]).exists()
        except Exception:  # malformed id, e.g. not a UUID
            exists = False
        if not exists:
            raise serializers.ValidationError(
                {"object_id": [f"{model.__name__} does not exist!"]}
            )

        data["content_type"] = ContentType.objects.get_for_model(model)
        data["purpose"] = data.get("purpose", "")
        if FileAttachment.objects.filter(
            file=data["file"],
            content_type=data["content_type"],
            object_id=data["object_id"],
            purpose=data["purpose"],
        ).exists():
            raise serializers.ValidationError(
                {"file": ["File is already attached to this object!"]}
            )
        return data

    def create(self, validated_data):
        validated_data.pop("object_type")
        return super().create(validated_data)
