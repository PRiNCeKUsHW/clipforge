import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import Storage
from app.models import TERMINAL_STATUSES, Clip, User, VideoProject
from app.schemas.clip import ClipDetail, ClipRead
from app.schemas.project import ProjectRead
from app.services.text import safe_filename, words_to_text


async def get_owned_project(session: AsyncSession, project_id: uuid.UUID, user: User) -> VideoProject:
    project = await session.get(VideoProject, project_id)
    # 404 (not 403) for other users' projects so ids can't be probed.
    if project is None or project.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


async def get_owned_clip(session: AsyncSession, clip_id: uuid.UUID, user: User) -> Clip:
    row = (
        await session.execute(
            select(Clip).join(VideoProject).where(Clip.id == clip_id, VideoProject.user_id == user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clip not found")
    return row


async def clip_counts(session: AsyncSession, project_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not project_ids:
        return {}
    rows = await session.execute(
        select(Clip.project_id, func.count(Clip.id)).where(Clip.project_id.in_(project_ids)).group_by(Clip.project_id)
    )
    return {pid: n for pid, n in rows.all()}


STALL_AFTER = timedelta(minutes=20)


def is_stalled(project: VideoProject, now: datetime | None = None) -> bool:
    """Still unfinished but no progress update for a long time: most likely the worker died
    mid-task (e.g. out of memory). Such projects may be retried."""
    if project.status in TERMINAL_STATUSES or project.updated_at is None:
        return False
    now = now or datetime.now(UTC)
    return now - project.updated_at > STALL_AFTER


def project_to_read(project: VideoProject, clip_count: int = 0) -> ProjectRead:
    data = ProjectRead.model_validate(project, from_attributes=True)
    data.clip_count = clip_count
    data.stalled = is_stalled(project)
    return data


def clip_to_read(
    clip: Clip,
    storage: Storage,
    *,
    detail: bool = False,
    expires: int = 3600,
    project: VideoProject | None = None,
) -> ClipRead:
    fields = dict(
        id=clip.id,
        project_id=clip.project_id,
        start=clip.start,
        end=clip.end,
        duration=round(clip.duration, 2),
        hook_title=clip.hook_title,
        virality_score=clip.virality_score,
        score_breakdown=clip.score_breakdown or {},
        reason=clip.reason or "",
        description=clip.description,
        hashtags=list(clip.hashtags or []),
        caption_style=clip.caption_style,
        layout=clip.layout or "auto",
        framing=(clip.crop_path or {}).get("layout"),
        status=clip.status,
        progress=clip.progress or 0,
        error=clip.error,
        transcript_text=words_to_text(clip.transcript_words or []),
        video_url=storage.presign_get(clip.output_key, expires) if clip.output_key else None,
        thumbnail_url=storage.presign_get(clip.thumbnail_key, expires) if clip.thumbnail_key else None,
        created_at=clip.created_at,
        updated_at=clip.updated_at,
    )
    if detail:
        return ClipDetail(
            **fields,
            transcript_words=clip.transcript_words or [],
            project_title=project.title if project else None,
            project_duration=project.duration if project else None,
            source_url=storage.presign_get(project.storage_key, expires) if project and project.storage_key else None,
        )
    return ClipRead(**fields)


def clip_download_name(clip: Clip, rank: int | None = None) -> str:
    stem = safe_filename(clip.hook_title, default="clip")
    prefix = f"{rank:02d}-" if rank is not None else ""
    return f"{prefix}{stem}.mp4"
