import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ProjectStatus, SourceType
from app.services.editing import CAPTION_STYLES, CLIP_LENGTHS, LAYOUTS, TARGET_CLIPS_RANGE
from app.services.youtube import is_youtube_url


class ProjectCreate(BaseModel):
    source_type: SourceType
    source_url: str | None = Field(default=None, max_length=2048)
    storage_key: str | None = Field(default=None, max_length=1024)
    title: str | None = Field(default=None, max_length=300)
    instruction: str | None = Field(default=None, max_length=500)
    # Defaults for every clip found in this project
    layout: str = "auto"
    caption_style: str = "bold"
    clip_length: str = "auto"
    # None = let Gemini decide how many clips
    target_clips: int | None = Field(default=None, ge=TARGET_CLIPS_RANGE[0], le=TARGET_CLIPS_RANGE[1])

    @model_validator(mode="after")
    def _check_source(self) -> "ProjectCreate":
        if self.source_type == SourceType.youtube:
            if not self.source_url or not is_youtube_url(self.source_url):
                raise ValueError("Please paste a valid YouTube video link")
            self.storage_key = None
        else:
            if not self.storage_key:
                raise ValueError("storage_key is required for uploads")
            self.source_url = None
        if self.layout not in LAYOUTS:
            raise ValueError(f"Unknown layout {self.layout!r}")
        if self.caption_style not in CAPTION_STYLES:
            raise ValueError(f"Unknown caption style {self.caption_style!r}")
        if self.clip_length not in CLIP_LENGTHS:
            raise ValueError(f"Unknown clip length {self.clip_length!r}")
        if self.instruction is not None:
            self.instruction = self.instruction.strip() or None
        if self.title is not None:
            self.title = self.title.strip() or None
        return self


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_type: SourceType
    source_url: str | None
    title: str | None
    duration: float | None
    instruction: str | None
    layout: str
    caption_style: str
    clip_length: str = "auto"
    target_clips: int | None = None
    status: ProjectStatus
    progress: int
    status_message: str | None
    error: str | None
    language: str | None
    created_at: datetime
    updated_at: datetime
    clip_count: int = 0
    # unfinished, but no progress for a long time (worker probably died); can be retried
    stalled: bool = False


class ProgressEvent(BaseModel):
    """Payload of each Server-Sent Event on /projects/{id}/events (the worker publishes the same shape)."""

    id: uuid.UUID
    status: ProjectStatus
    progress: int
    status_message: str | None = None
    error: str | None = None


class PresignUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)
    size: int = Field(gt=0)


class PresignUploadResponse(BaseModel):
    storage_key: str
    upload_url: str
    content_type: str
    expires_in: int
