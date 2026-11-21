import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import Platform, PublishStatus

if TYPE_CHECKING:
    from app.models.clip import Clip


class PublishJob(Base, TimestampMixin):
    __tablename__ = "publish_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    clip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clips.id", ondelete="CASCADE"), index=True)
    social_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="SET NULL")
    )
    platform: Mapped[Platform] = mapped_column(str_enum(Platform))
    status: Mapped[PublishStatus] = mapped_column(
        str_enum(PublishStatus), default=PublishStatus.queued, server_default=PublishStatus.queued.value
    )
    title: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    # YouTube: private | unlisted | public
    privacy_status: Mapped[str | None] = mapped_column(String(16))
    external_id: Mapped[str | None] = mapped_column(String(255))
    external_url: Mapped[str | None] = mapped_column(String(500))
    error: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    clip: Mapped["Clip"] = relationship(back_populates="publish_jobs")
