from __future__ import annotations

import json
import os
from pathlib import Path


def _build_drive_service():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        return None
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    info = json.loads(raw)
    scopes = ["https://www.googleapis.com/auth/drive"]
    credentials = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    return build("drive", "v3", credentials=credentials)


def download_file(file_id: str, destination: str | Path) -> Path | None:
    service = _build_drive_service()
    if service is None:
        return None
    import io
    from googleapiclient.http import MediaIoBaseDownload

    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    out = Path(destination)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(buffer.getvalue())
    return out


def upload_file(path: str | Path, folder_id: str | None = None) -> str | None:
    service = _build_drive_service()
    if service is None:
        return None
    from googleapiclient.http import MediaFileUpload

    file_path = Path(path)
    metadata = {"name": file_path.name}
    if folder_id:
        metadata["parents"] = [folder_id]
    media = MediaFileUpload(str(file_path), resumable=True)
    created = service.files().create(body=metadata, media_body=media, fields="id").execute()
    return created.get("id")
