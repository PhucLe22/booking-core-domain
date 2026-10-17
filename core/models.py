import uuid

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django_extensions.db.models import TimeStampedModel
from django_softdelete.models import SoftDeleteModel

from .managers import (
    DeletedUserManager,
    GlobalUserManager,
    SoftDeleteUserManager,
)
from .querysets import BookingQuerySet

from core.constant import USER_DEFAULT_SYSTEM


# =========================================================
# 1. ENUM CONFIGURATION
# =========================================================

class EnumType(models.Model):
    """
    Enum group:
    RESOURCE_STATUS, BOOKING_STATUS, NOTIFICATION_TYPE, ...
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "enum_types"
        ordering = ["code"]

    def __str__(self):
        return self.code


class EnumDefinition(models.Model):
    """
    A value that belongs to an enum group.
    Example: BOOKING_STATUS -> PENDING, CONFIRMED.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    enum_type = models.ForeignKey(
        EnumType,
        on_delete=models.PROTECT,
        related_name="definitions",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    value = models.IntegerField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0)
    configuration = models.JSONField(default=dict, blank=True)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "enum_definitions"
        ordering = ["enum_type__code", "position"]
        constraints = [
            models.UniqueConstraint(
                fields=["enum_type", "code"],
                name="enum_type_code_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["enum_type", "is_active"],
                name="enum_definition_active_idx",
            ),
        ]

    def clean(self):
        super().clean()
        self.code = self.code.strip().upper()

    def __str__(self):
        return f"{self.enum_type.code}.{self.code}"


# =========================================================
# 2. IDENTITY & ACCESS CONTROL (RBAC)
# =========================================================

class Role(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    configuration = models.JSONField(default=dict, blank=True)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    permissions = models.ManyToManyField(
        "Permission",
        through="RolePermission",
        related_name="roles",
        blank=True,
    )

    class Meta:
        db_table = "roles"
        ordering = ["code"]

    def __str__(self):
        return self.code


class Permission(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "permissions"
        ordering = ["code"]

    def __str__(self):
        return self.code


class User(AbstractBaseUser, TimeStampedModel, SoftDeleteModel):
    # Keep the current primary key type to limit the impact on migrations.
    username = models.CharField(
        max_length=255,
        unique=True,
        null=True,
    )
    first_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    last_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    avatar = models.ImageField(
        upload_to="avatar/",
        blank=True,
        default=None,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["jpg", "jpeg", "png", "webp"]
            ),
        ],
        max_length=255,
    )
    status = models.BooleanField(default=True)

    roles = models.ManyToManyField(
        Role,
        through="UserRole",
        related_name="users",
        blank=True,
    )

    objects = SoftDeleteUserManager()
    global_objects = GlobalUserManager()
    deleted_objects = DeletedUserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    token_version = models.UUIDField(default=uuid.uuid4)

    class Meta:
        db_table = "users"

    def __str__(self):
        return f"{self.pk} {self.username}"

    @property
    def full_name(self) -> str:
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    def set_new_token_version(self):
        self.token_version = uuid.uuid4()
        self.save(update_fields=["token_version"])

    def get_new_token_version(self) -> str:
        return str(self.token_version)

    def is_token_version_valid(self, token_version: str) -> bool:
        return self.get_new_token_version() == token_version

    def has_role(self, *role_codes: str) -> bool:
        return self.roles.filter(code__in=role_codes, is_active=True).exists()

    def assign_role(self, role_code: str) -> "UserRole":
        role = Role.objects.get(code=role_code)
        user_role, _ = UserRole.objects.get_or_create(user=self, role=role)
        return user_role


class UserRole(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="role_assignments",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="user_assignments",
    )

    class Meta:
        db_table = "user_roles"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role"],
                name="user_role_unique",
            ),
        ]

    def __str__(self):
        return f"{self.user_id} - {self.role.code}"


class RolePermission(models.Model):
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="permission_assignments",
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name="role_assignments",
    )

    class Meta:
        db_table = "role_permissions"
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"],
                name="role_permission_unique",
            ),
        ]

    def __str__(self):
        return f"{self.role.code} - {self.permission.code}"


# =========================================================
# 3. NOTIFICATION
# =========================================================

class Notification(TimeStampedModel):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_DEFAULT,
        default=USER_DEFAULT_SYSTEM,
        null=True,
        related_name="notifications",
    )
    notify_type = models.ForeignKey(
        EnumDefinition,
        on_delete=models.PROTECT,
        related_name="notifications",
        limit_choices_to={
            "enum_type__code": "NOTIFICATION_TYPE",
        },
    )
    data = models.JSONField(null=True, blank=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = "notifications"
        ordering = ["-created"]
        indexes = [
            models.Index(
                fields=["user", "is_read"],
                name="notification_user_read_idx",
            ),
        ]

    def __str__(self):
        return f"Notification for {self.user_id} - {self.notify_type_id}"


# =========================================================
# 4. RESOURCE MANAGEMENT
# =========================================================

class ResourceType(models.Model):
    """
    Defines a resource type and the schema of its dynamic fields.
    Example: MEETING_ROOM, VEHICLE, EQUIPMENT.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    configuration = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "resource_types"
        ordering = ["code"]

    @property
    def status_enum_type(self):
        """Master data list the statuses of this type's resources come from."""
        return (self.configuration or {}).get("status_enum_type") or "RESOURCE_STATUS"

    def __str__(self):
        return self.code


class Resource(models.Model):
    """
    A specific resource that belongs to a ResourceType.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    resource_type = models.ForeignKey(
        ResourceType,
        on_delete=models.PROTECT,
        related_name="resources",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)

    # a value of the resource type's status list (configuration.status_enum_type), or blank
    status = models.ForeignKey(
        EnumDefinition,
        on_delete=models.PROTECT,
        related_name="resources",
        null=True,
        blank=True,
    )

    configuration = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "resources"
        constraints = [
            models.UniqueConstraint(
                fields=["resource_type", "code"],
                name="resource_type_code_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["resource_type", "status"],
                name="resource_type_status_idx",
            ),
        ]

    @property
    def is_bookable(self):
        """ACTIVE, or a status marked {"bookable": true} in its master data configuration."""
        status = self.status
        return status is not None and (
            status.code == "ACTIVE" or bool((status.configuration or {}).get("bookable"))
        )

    def clean(self):
        super().clean()

        expected = self.resource_type.status_enum_type
        if self.status_id and self.status.enum_type.code != expected:
            raise ValidationError({
                "status": f"Status must belong to {expected}."
            })

    def __str__(self):
        return f"{self.code} - {self.name}"


# =========================================================
# 5. BOOKING POLICIES
# =========================================================

class BookingPolicy(models.Model):
    """
    Booking rules per resource type.
    Business parameters are stored in configuration.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    resource_type = models.ForeignKey(
        ResourceType,
        on_delete=models.PROTECT,
        related_name="booking_policies",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    configuration = models.JSONField(default=dict, blank=True)
    priority = models.PositiveIntegerField(default=0)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "booking_policies"
        constraints = [
            models.UniqueConstraint(
                fields=["resource_type", "code"],
                name="resource_type_policy_code_unique",
            ),
            models.UniqueConstraint(
                fields=["resource_type"],
                condition=Q(is_default=True),
                name="one_default_policy_per_type",
            ),
        ]
        indexes = [
            models.Index(
                fields=["resource_type", "is_active", "priority"],
                name="booking_policy_lookup_idx",
            ),
        ]

    def __str__(self):
        return f"{self.resource_type.code} - {self.code}"


# =========================================================
# 6. BOOKING LIFECYCLE
# =========================================================

class Booking(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    resource = models.ForeignKey(
        Resource,
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="bookings",
        null=True,
        blank=True,
    )

    guest_name = models.CharField(max_length=255, blank=True, null=True)
    guest_email = models.EmailField(max_length=255, blank=True, null=True)
    guest_phone = models.CharField(max_length=20, blank=True, null=True)

    start_at = models.DateTimeField()
    end_at = models.DateTimeField()

    status = models.ForeignKey(
        EnumDefinition,
        on_delete=models.PROTECT,
        related_name="bookings",
        limit_choices_to={
            "enum_type__code": "BOOKING_STATUS",
        },
    )

    title = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    configuration = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = BookingQuerySet.as_manager()

    class Meta:
        db_table = "bookings"
        indexes = [
            models.Index(
                fields=["resource", "start_at"],
                name="booking_resource_start_idx",
            ),
            models.Index(
                fields=["user", "start_at"],
                name="booking_user_start_idx",
            ),
            models.Index(
                fields=["status", "start_at"],
                name="booking_status_start_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(user__isnull=False)
                | Q(guest_email__isnull=False),
                name="booking_user_or_guest",
            ),
            models.CheckConstraint(
                check=Q(end_at__gt=models.F("start_at")),
                name="booking_end_after_start",
            ),
        ]

    def clean(self):
        super().clean()

        if self.status_id and self.status.enum_type.code != "BOOKING_STATUS":
            raise ValidationError({
                "status": "Status must belong to BOOKING_STATUS."
            })

    def __str__(self):
        return self.title or str(self.pk)


# =========================================================
# 7. FILE & STORAGE MANAGEMENT
# =========================================================

class StorageConfig(models.Model):
    """
    File storage backend configuration.
    Example: LOCAL, S3, MINIO.
    Do not store secret credentials directly in configuration.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    provider = models.CharField(max_length=30, default="LOCAL")
    configuration = models.JSONField(default=dict, blank=True)
    max_file_size_bytes = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )
    allowed_extensions = models.JSONField(default=list, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "storage_configs"
        constraints = [
            models.UniqueConstraint(
                fields=["is_default"],
                condition=Q(is_default=True),
                name="one_default_storage_config",
            ),
        ]

    def __str__(self):
        return self.code


class Folder(models.Model):
    """
    Folders nested through parent.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_folders",
        null=True,
        blank=True,
    )
    configuration = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "folders"
        indexes = [
            models.Index(fields=["parent"], name="folder_parent_idx"),
        ]

    def __str__(self):
        return self.name


class StoredFile(models.Model):
    """
    File metadata.
    The file content is stored in the storage backend, not in a JSONField.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    storage_config = models.ForeignKey(
        StorageConfig,
        on_delete=models.PROTECT,
        related_name="files",
    )
    folder = models.ForeignKey(
        Folder,
        on_delete=models.SET_NULL,
        related_name="files",
        null=True,
        blank=True,
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="uploaded_files",
        null=True,
        blank=True,
    )
    original_name = models.CharField(max_length=255)
    storage_key = models.CharField(max_length=1024)
    mime_type = models.CharField(max_length=150, blank=True)
    extension = models.CharField(max_length=20, blank=True)
    size_bytes = models.PositiveBigIntegerField(
        validators=[MinValueValidator(0)],
    )
    checksum = models.CharField(max_length=128, blank=True)
    configuration = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "files"
        constraints = [
            models.UniqueConstraint(
                fields=["storage_config", "storage_key"],
                name="storage_file_key_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["folder", "created_at"],
                name="file_folder_created_idx",
            ),
            models.Index(
                fields=["uploaded_by", "created_at"],
                name="file_uploader_created_idx",
            ),
        ]

    def __str__(self):
        return self.original_name


class FileAttachment(models.Model):
    """
    Attaches a file to any model without adding a separate FK
    for Booking, Resource, Comment, ...
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    file = models.ForeignKey(
        StoredFile,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
    )
    object_id = models.CharField(max_length=255)
    content_object = GenericForeignKey("content_type", "object_id")

    purpose = models.CharField(max_length=50, blank=True)
    configuration = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "file_attachments"
        indexes = [
            models.Index(
                fields=["content_type", "object_id"],
                name="file_attachment_object_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["file", "content_type", "object_id", "purpose"],
                name="file_attachment_unique",
            ),
        ]

    def __str__(self):
        return f"{self.file_id} -> {self.content_type_id}:{self.object_id}"


# =========================================================
# 8. COMMENTS & COLLABORATION
# =========================================================

class Comment(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="comments",
    )
    resource_type = models.CharField(max_length=50)
    resource_id = models.UUIDField()
    content = models.TextField()
    configuration = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "comments"
        indexes = [
            models.Index(
                fields=["resource_type", "resource_id"],
                name="comment_resource_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Comment by {self.user_id} on "
            f"{self.resource_type}:{self.resource_id}"
        )