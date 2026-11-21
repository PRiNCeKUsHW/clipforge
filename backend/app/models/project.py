import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import ProjectStatus, SourceType

if TYPE_CHECKING:
    from app.models.clip import Clip
    from app.models.user import User


class VideoProject(Base, TimestampMixin):
    __tablename__ = "video_projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    source_type: Mapped[SourceType] = mapped_column(str_enum(SourceType))
    source_url: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(String(1024))
    title: Mapped[str | None] = mapped_column(String(300))
    duration: Mapped[float | None] = mapped_column(Float)
    # Optional user guidance for highlight selection, e.g. "only funny moments"
    instruction: Mapped[str | None] = mapped_column(Text)
    # Defaults applied to every clip found in this project (each clip can still be changed later)
    layout: Mapped[str] = mapped_column(String(32), default="auto", server_default="auto")
    caption_style: Mapped[str] = mapped_column(String(32), default="bold", server_default="bold")
    # How long each clip should be ("auto", "1m", "2m"; see services.editing.CLIP_LENGTHS)
    clip_length: Mapped[str] = mapped_column(String(16), default="auto", server_default="auto")
    # How many clips the user wants (1-10); None lets Gemini decide
    target_clips: Mapped[int | None] = mapped_column(Integer)

    status: Mapped[ProjectStatus] = mapped_column(
        str_enum(ProjectStatus), default=ProjectStatus.queued, server_default=ProjectStatus.queued.value, index=True
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status_message: Mapped[str | None] = mapped_column(String(300))
    error: Mapped[str | None] = mapped_column(Text)

    language: Mapped[str | None] = mapped_column(String(16))
    # {"language", "duration", "segments": [{start, end, text, speaker?, words: [{word, start, end, speaker?}]}]}
    transcript: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    user: Mapped["User"] = relationship(back_populates="projects")
    clips: Mapped[list["Clip"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
