import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import current_active_user
from app.core.config import get_settings
from app.core.deps import get_storage
from app.core.storage import Storage, upload_key
from app.models import User
from app.schemas.project import PresignUploadRequest, PresignUploadResponse
from app.services.text import safe_filename

router = APIRouter(prefix="/uploads", tags=["uploads"])

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}


@router.post("/presign", response_model=PresignUploadResponse)
async def presign_upload(
    body: PresignUploadRequest,
    user: User = Depends(current_active_user),
    storage: Storage = Depends(get_storage),
) -> PresignUploadResponse:
    """Step 1 of an upload: get a presigned URL, then the browser PUTs the file straight to storage
    (the bytes never pass through the API). Step 2: POST /projects with the returned storage_key."""
    settings = get_settings()
    stem, ext = os.path.splitext(body.filename)
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported file type {ext or '(none)'}; use MP4, MOV, MKV or WebM")
    if not body.content_type.startswith("video/"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File must be a video")
    if body.size > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB")

    key = upload_key(str(user.id), uuid.uuid4().hex, f"{safe_filename(stem, default='video')}{ext}")
    url = storage.presign_put(key, body.content_type, settings.presign_expiry_seconds)
    return PresignUploadResponse(
        storage_key=key, upload_url=url, content_type=body.content_type, expires_in=settings.presign_expiry_seconds
    )
