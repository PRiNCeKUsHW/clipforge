"""clip post copy (description, hashtags), render progress; publish job privacy + url

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-19
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("clips", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "clips",
        sa.Column("hashtags", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
    )
    op.add_column("clips", sa.Column("progress", sa.Integer(), server_default="0", nullable=False))
    op.add_column("publish_jobs", sa.Column("privacy_status", sa.String(16), nullable=True))
    op.add_column("publish_jobs", sa.Column("external_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("publish_jobs", "external_url")
    op.drop_column("publish_jobs", "privacy_status")
    op.drop_column("clips", "progress")
    op.drop_column("clips", "hashtags")
    op.drop_column("clips", "description")
