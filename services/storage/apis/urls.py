from django.conf import settings
from django.urls import include, path, re_path
from django.views.static import serve
from rest_framework.routers import DefaultRouter

from .views import (
    FileAttachmentViewSet,
    FolderViewSet,
    StorageConfigViewSet,
    StoredFileViewSet,
)

router = DefaultRouter()
router.register(r"v1/storage_configs", StorageConfigViewSet, basename="storage_config")
router.register(r"v1/folders", FolderViewSet, basename="folder")
router.register(r"v1/files", StoredFileViewSet, basename="file")
router.register(r"v1/attachments", FileAttachmentViewSet, basename="attachment")

urlpatterns = [
    path("", include(router.urls)),
    # public file links (no login), eg: /api/v1/media/documents/2026/10/<uuid>.png
    # serve() rejects paths outside STORAGE_ROOT and does not list directories
    re_path(
        r"^v1/media/(?P<path>.+)$",
        serve,
        {"document_root": settings.STORAGE_ROOT},
        name="storage_media",
    ),
]
