import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import ClipStatus

if TYPE_CHECKING:
    from app.models.project import VideoProject
    from app.models.publish_job import PublishJob


class Clip(Base, TimestampMixin):
    __tablename__ = "clips"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("video_projects.id", ondelete="CASCADE"), index=True)

    # Seconds in the source video. ("end" is an SQL keyword, hence the column names.)
    start: Mapped[float] = mapped_column("start_time", Float)
    end: Mapped[float] = mapped_column("end_time", Float)

    hook_title: Mapped[str] = mapped_column(String(200))
    # Post copy suggested by Gemini, editable before publishing
    description: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    virality_score: Mapped[int] = mapped_column(Integer, index=True)
    # {"hook": int, "payoff": int, "emotion": int, "standalone": int}
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    reason: Mapped[str] = mapped_column(Text, default="")

    # Editable copy of the words in this clip: [{word, start, end, speaker?}], absolute source times
    transcript_words: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # Reframe keyframes for 9:16 (Phase 3)
    crop_path: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    caption_style: Mapped[str] = mapped_column(String(32), default="bold", server_default="bold")
    # Chosen clip layout: auto | podcast_split | single | centered_title | blur_fit
    layout: Mapped[str] = mapped_column(String(32), default="auto", server_default="auto")

    output_key: Mapped[str | None] = mapped_column(String(1024))
    thumbnail_key: Mapped[str | None] = mapped_column(String(1024))
    status: Mapped[ClipStatus] = mapped_column(
        str_enum(ClipStatus), default=ClipStatus.pending, server_default=ClipStatus.pending.value
    )
    # 0-100 while (re-)rendering
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(Text)

    project: Mapped["VideoProject"] = relationship(back_populates="clips")
    publish_jobs: Mapped[list["PublishJob"]] = relationship(
        back_populates="clip", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)
