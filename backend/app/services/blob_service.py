from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from app.config import get_settings


def store_upload(container: str, filename: str, content: bytes) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name) or "upload.bin"
    blob_name = f"{uuid4().hex}-{safe_name}"
    connection_string = get_settings().require_azure_storage()
    from azure.storage.blob import BlobServiceClient

    service = BlobServiceClient.from_connection_string(connection_string)
    container_client = service.get_container_client(container)
    try:
        container_client.create_container()
    except Exception as exc:
        if getattr(exc, "error_code", "") != "ContainerAlreadyExists":
            raise
    blob = container_client.get_blob_client(blob_name)
    blob.upload_blob(content, overwrite=True)
    return blob.url
