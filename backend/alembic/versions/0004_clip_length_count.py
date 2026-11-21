"""clip length and number of clips chosen when creating a project

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-21
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("video_projects", sa.Column("clip_length", sa.String(16), server_default="auto", nullable=False))
    op.add_column("video_projects", sa.Column("target_clips", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("video_projects", "target_clips")
    op.drop_column("video_projects", "clip_length")
