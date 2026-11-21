"""initial schema: users, social accounts, projects, clips, publish jobs

Revision ID: 0001
Revises:
Create Date: 2026-11-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(1024), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_superuser", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default="false", nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "social_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("external_account_id", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_social_accounts_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_social_accounts"),
        sa.UniqueConstraint("user_id", "platform", "external_account_id", name="uq_social_accounts_user_id"),
    )
    op.create_index("ix_social_accounts_user_id", "social_accounts", ["user_id"])

    op.create_table(
        "video_projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("storage_key", sa.String(1024), nullable=True),
        sa.Column("title", sa.String(300), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("instruction", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), server_default="queued", nullable=False),
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status_message", sa.String(300), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("transcript", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_video_projects_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_video_projects"),
    )
    op.create_index("ix_video_projects_user_id", "video_projects", ["user_id"])
    op.create_index("ix_video_projects_status", "video_projects", ["status"])

    op.create_table(
        "clips",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("hook_title", sa.String(200), nullable=False),
        sa.Column("virality_score", sa.Integer(), nullable=False),
        sa.Column("score_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("transcript_words", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("crop_path", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("caption_style", sa.String(32), server_default="bold", nullable=False),
        sa.Column("output_key", sa.String(1024), nullable=True),
        sa.Column("thumbnail_key", sa.String(1024), nullable=True),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["project_id"], ["video_projects.id"], name="fk_clips_project_id_video_projects", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_clips"),
    )
    op.create_index("ix_clips_project_id", "clips", ["project_id"])
    op.create_index("ix_clips_virality_score", "clips", ["virality_score"])

    op.create_table(
        "publish_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clip_id", sa.Uuid(), nullable=False),
        sa.Column("social_account_id", sa.Uuid(), nullable=True),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), server_default="queued", nullable=False),
        sa.Column("title", sa.String(300), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["clip_id"], ["clips.id"], name="fk_publish_jobs_clip_id_clips", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["social_account_id"],
            ["social_accounts.id"],
            name="fk_publish_jobs_social_account_id_social_accounts",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_publish_jobs"),
    )
    op.create_index("ix_publish_jobs_clip_id", "publish_jobs", ["clip_id"])


def downgrade() -> None:
    op.drop_table("publish_jobs")
    op.drop_table("clips")
    op.drop_table("video_projects")
    op.drop_table("social_accounts")
    op.drop_table("users")
