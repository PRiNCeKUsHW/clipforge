"""clip layouts: per-clip layout, per-project default layout and caption style

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-20
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("clips", sa.Column("layout", sa.String(32), server_default="auto", nullable=False))
    op.add_column("video_projects", sa.Column("layout", sa.String(32), server_default="auto", nullable=False))
    op.add_column("video_projects", sa.Column("caption_style", sa.String(32), server_default="bold", nullable=False))


def downgrade() -> None:
    op.drop_column("video_projects", "caption_style")
    op.drop_column("video_projects", "layout")
    op.drop_column("clips", "layout")
