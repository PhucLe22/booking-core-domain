import hashlib
import os
import re
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from rest_framework.exceptions import ValidationError

SUPPORTED_PROVIDERS = ["LOCAL"]
KNOWN_PROVIDERS = ["LOCAL", "S3", "MINIO"]

# relative folder under STORAGE_ROOT: lowercase words separated by "/", "_" or "-"
STORAGE_PATH_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*(/[a-z0-9][a-z0-9_-]*)*$")


def storage_path(storage_config):
    """Folder of a LOCAL storage under STORAGE_ROOT, eg: "avatars"."""
    return storage_config.configuration.get("path") or "files"


def ensure_storage_directory(storage_config):
    """Create STORAGE_ROOT/<path> for a LOCAL storage (no-op for other providers)."""
    if storage_config.provider != "LOCAL":
        return None
    directory = os.path.join(settings.STORAGE_ROOT, storage_path(storage_config))
    os.makedirs(directory, exist_ok=True)
    return directory


def get_storage(storage_config):
    """
    Return the Django storage backend of a StorageConfig.
    LOCAL stores files under STORAGE_ROOT/<configuration.path> (default "files").
    """
    if storage_config.provider != "LOCAL":
        raise ValidationError(
            {
                "storage_config": [
                    f"Storage provider '{storage_config.provider}' is not supported yet!"
                ]
            }
        )
    path = storage_path(storage_config)
    return FileSystemStorage(
        location=os.path.join(settings.STORAGE_ROOT, path),
        base_url=f"{settings.STORAGE_URL}{path}/",
    )


def build_storage_key(extension):
    """Unique key like 2026/10/<uuid>.pdf, so original names never clash."""
    now = timezone.now()
    suffix = f".{extension}" if extension else ""
    return f"{now:%Y}/{now:%m}/{uuid.uuid4().hex}{suffix}"


def file_checksum(uploaded_file):
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    return digest.hexdigest()
