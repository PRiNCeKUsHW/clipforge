import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import Platform

if TYPE_CHECKING:
    from app.models.user import User


class SocialAccount(Base, TimestampMixin):
    """A connected YouTube / Instagram account. Tokens are Fernet-encrypted (see app.core.crypto)."""

    __tablename__ = "social_accounts"
    __table_args__ = (UniqueConstraint("user_id", "platform", "external_account_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    platform: Mapped[Platform] = mapped_column(str_enum(Platform))
    external_account_id: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    access_token_encrypted: Mapped[str] = mapped_column(Text)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="social_accounts")
