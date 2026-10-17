from drf_spectacular.utils import OpenApiParameter, OpenApiTypes

from core.serializers.storage_serializers import (
    ATTACHABLE_MODELS,
    FileAttachmentSerializer,
    FolderSerializer,
    StorageConfigSerializer,
    StoredFileSerializer,
    UpdateFileSerializer,
)


def id_parameter(description):
    return OpenApiParameter(
        "id", type=str, location=OpenApiParameter.PATH, description=description
    )


PAGINATION_PARAMETERS = [
    OpenApiParameter("page", int, required=False, default=1, description="Page number"),
    OpenApiParameter(
        "page_size", int, required=False, default=5, description="Items per page."
    ),
]

# ---------- storage configs ----------

list_storage_configs_document = {
    "summary": "Get list of storage configs",
    "description": "Admin only.",
    "responses": {200: StorageConfigSerializer(many=True)},
}

create_storage_config_document = {
    "summary": "Create storage config",
    "description": "Admin only. Only LOCAL is supported for now. Never put credentials in configuration.",
    "request": StorageConfigSerializer,
    "responses": {201: StorageConfigSerializer},
}

update_storage_config_document = {
    "parameters": [id_parameter("UUID of the storage config")],
    "summary": "Update storage config",
    "description": "Admin only. Setting is_default=true unsets the previous default.",
    "request": StorageConfigSerializer,
    "responses": {200: StorageConfigSerializer},
}

delete_storage_config_document = {
    "parameters": [id_parameter("UUID of the storage config")],
    "summary": "Delete storage config",
    "description": "Admin only. A storage config that still has files cannot be deleted.",
    "responses": {200: None},
}

# ---------- folders ----------

list_folders_document = {
    "summary": "Get list of folders",
    "description": "Your own folders (admin and staff: all). eg: ?is_root=true or ?parent=<uuid>",
    "parameters": [
        *PAGINATION_PARAMETERS,
        OpenApiParameter("parent", str, required=False, description="Parent folder UUID"),
        OpenApiParameter("is_root", bool, required=False, description="Only top level folders"),
        OpenApiParameter("name", str, required=False, description="Name contains"),
    ],
    "responses": {200: FolderSerializer(many=True)},
}

retrieve_folder_document = {
    "parameters": [id_parameter("UUID of the folder")],
    "summary": "Get folder detail",
    "description": "Get folder detail",
    "responses": {200: FolderSerializer},
}

create_folder_document = {
    "summary": "Create folder",
    "description": "Create a folder, at the top level or inside parent.",
    "request": FolderSerializer,
    "responses": {201: FolderSerializer},
}

update_folder_document = {
    "parameters": [id_parameter("UUID of the folder")],
    "summary": "Update folder",
    "description": "Rename or move a folder. It cannot be moved into itself or its subfolders.",
    "request": FolderSerializer,
    "responses": {200: FolderSerializer},
}

delete_folder_document = {
    "parameters": [id_parameter("UUID of the folder")],
    "summary": "Delete folder",
    "description": "Deletes the folder and its subfolders. Their files are kept and moved to the top level.",
    "responses": {200: None},
}

# ---------- files ----------

list_files_document = {
    "summary": "Get list of files",
    "description": "Your own files (admin and staff: all). eg: ?folder=<uuid>&extension=pdf",
    "parameters": [
        *PAGINATION_PARAMETERS,
        OpenApiParameter("folder", str, required=False, description="Folder UUID"),
        OpenApiParameter("is_root", bool, required=False, description="Only files outside folders"),
        OpenApiParameter("name", str, required=False, description="File name contains"),
        OpenApiParameter("extension", str, required=False, description="eg: pdf"),
    ],
    "responses": {200: StoredFileSerializer(many=True)},
}

retrieve_file_document = {
    "parameters": [id_parameter("UUID of the file")],
    "summary": "Get file detail",
    "description": "Get file metadata. Use download_url to get the content.",
    "responses": {200: StoredFileSerializer},
}

upload_file_document = {
    "summary": "Upload file",
    "description": "multipart/form-data. Optional: folder (UUID), storage_config (code), and object_type + object_id + purpose to attach the file in the same call. Storage: storage_config if given, else the storage whose configuration.purposes contains purpose, else the default storage.",
    "request": {
        "multipart/form-data": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "format": "binary"},
                "folder": {"type": "string", "format": "uuid"},
                "storage_config": {"type": "string", "example": "LOCAL"},
                "object_type": {
                    "type": "string",
                    "enum": ["booking", "resource", "resource_type", "comment", "user"],
                },
                "object_id": {"type": "string", "example": "5"},
                "purpose": {"type": "string", "example": "avatar"},
            },
            "required": ["file"],
        }
    },
    "responses": {201: StoredFileSerializer},
}

update_file_document = {
    "parameters": [id_parameter("UUID of the file")],
    "summary": "Update file",
    "description": "Rename a file or move it to another folder (folder=null: top level).",
    "request": UpdateFileSerializer,
    "responses": {200: StoredFileSerializer},
}

delete_file_document = {
    "parameters": [id_parameter("UUID of the file")],
    "summary": "Delete file",
    "description": "Deletes the file, its content and its attachments.",
    "responses": {200: None},
}

download_file_document = {
    "parameters": [id_parameter("UUID of the file")],
    "summary": "Download file",
    "description": "Returns the file content with its original name.",
    "responses": {(200, "application/octet-stream"): OpenApiTypes.BINARY},
}

# ---------- attachments ----------

list_attachments_document = {
    "summary": "Get list of attachments",
    "description": "eg: ?object_type=booking&object_id=<uuid>",
    "parameters": [
        *PAGINATION_PARAMETERS,
        OpenApiParameter(
            "object_type",
            str,
            required=False,
            description="One of: " + ", ".join(ATTACHABLE_MODELS),
        ),
        OpenApiParameter("object_id", str, required=False, description="ID of the object"),
        OpenApiParameter("file", str, required=False, description="File UUID"),
        OpenApiParameter("purpose", str, required=False, description="eg: photo, contract"),
    ],
    "responses": {200: FileAttachmentSerializer(many=True)},
}

create_attachment_document = {
    "summary": "Attach file",
    "description": "Attach one of your files to a booking, resource, resource_type, comment or user.",
    "request": FileAttachmentSerializer,
    "responses": {201: FileAttachmentSerializer},
}

delete_attachment_document = {
    "parameters": [id_parameter("UUID of the attachment")],
    "summary": "Detach file",
    "description": "Removes the link only; the file is kept.",
    "responses": {200: None},
}
