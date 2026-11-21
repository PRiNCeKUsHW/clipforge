import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import ClipStatus, Platform, PublishStatus


class ClipRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    start: float
    end: float
    duration: float
    hook_title: str
    virality_score: int
    score_breakdown: dict[str, Any]
    reason: str
    description: str | None
    hashtags: list[str]
    caption_style: str
    # chosen layout: auto | podcast_split | single | centered_title | blur_fit
    layout: str
    # what the reframe stage actually produced: single | split | fit (None until reframed)
    framing: str | None
    status: ClipStatus
    progress: int
    error: str | None
    transcript_text: str
    video_url: str | None
    thumbnail_url: str | None
    created_at: datetime
    updated_at: datetime


class ClipDetail(ClipRead):
    transcript_words: list[dict[str, Any]]
    project_title: str | None
    project_duration: float | None
    # presigned URL of the full source video, for previewing trims
    source_url: str | None


class ClipUpdate(BaseModel):
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, gt=0)
    hook_title: str | None = Field(default=None, min_length=1, max_length=200)
    caption_style: str | None = None
    layout: str | None = None
    # One entry per current transcript word (same order); timing never changes. "" hides a word.
    word_texts: list[str] | None = None
    description: str | None = Field(default=None, max_length=5000)
    hashtags: list[str] | None = Field(default=None, max_length=30)

    @model_validator(mode="after")
    def _one_kind_of_edit(self) -> "ClipUpdate":
        if self.word_texts is not None and (self.start is not None or self.end is not None):
            raise ValueError("Save caption text and trim changes separately")
        return self


class DownloadResponse(BaseModel):
    url: str
    filename: str


class PublishRequest(BaseModel):
    social_account_id: uuid.UUID
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    privacy_status: Literal["private", "unlisted", "public"] = "private"


class PublishJobRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    clip_id: uuid.UUID
    social_account_id: uuid.UUID | None
    platform: Platform
    status: PublishStatus
    title: str | None
    privacy_status: str | None
    external_id: str | None
    external_url: str | None
    error: str | None
    published_at: datetime | None
    created_at: datetime


class SocialAccountRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    platform: Platform
    external_account_id: str
    display_name: str | None
    expires_at: datetime | None
    created_at: datetime
