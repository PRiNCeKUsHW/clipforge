import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.project import VideoProject
    from app.models.social_account import SocialAccount


class User(Base, TimestampMixin):
    """Columns match what fastapi-users expects, defined by hand so the worker
    can import the models without depending on fastapi-users."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(1024))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    projects: Mapped[list["VideoProject"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    social_accounts: Mapped[list["SocialAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
