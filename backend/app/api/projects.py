import json
import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.auth import current_active_user
from app.core.channels import project_channel
from app.core.config import get_settings
from app.core.db import SessionLocal, get_session
from app.core.deps import get_storage
from app.core.storage import Storage
from app.core.tasks import enqueue_pipeline
from app.models import TERMINAL_STATUSES, Clip, ProjectStatus, SourceType, User, VideoProject
from app.schemas.clip import ClipRead
from app.schemas.project import ProgressEvent, ProjectCreate, ProjectRead
from app.services.projects import (
    clip_counts,
    clip_download_name,
    clip_to_read,
    get_owned_project,
    is_stalled,
    project_to_read,
)
from app.services.text import safe_filename
from app.services.zipstream import iter_zip

log = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
) -> ProjectRead:
    title = body.title
    if body.source_type == SourceType.upload:
        assert body.storage_key is not None
        # Users may only start projects from objects they uploaded themselves.
        if not body.storage_key.startswith(f"uploads/{user.id}/") or ".." in body.storage_key:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid upload key")
        if not storage.exists(body.storage_key):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Upload not found. Did the upload finish?")
        title = title or os.path.splitext(body.storage_key.rsplit("/", 1)[-1])[0]

    project = VideoProject(
        user_id=user.id,
        source_type=body.source_type,
        source_url=body.source_url,
        storage_key=body.storage_key,
        title=title,
        instruction=body.instruction,
        layout=body.layout,
        caption_style=body.caption_style,
        clip_length=body.clip_length,
        target_clips=body.target_clips,
        status=ProjectStatus.queued,
        progress=0,
        status_message="Waiting for a worker",
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    enqueue_pipeline(project.id)
    return project_to_read(project)


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    user: User = Depends(current_active_user), session: AsyncSession = Depends(get_session)
) -> list[ProjectRead]:
    projects = (
        await session.execute(
            select(VideoProject).where(VideoProject.user_id == user.id).order_by(VideoProject.created_at.desc())
        )
    ).scalars().all()
    counts = await clip_counts(session, [p.id for p in projects])
    return [project_to_read(p, counts.get(p.id, 0)) for p in projects]


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: uuid.UUID, user: User = Depends(current_active_user), session: AsyncSession = Depends(get_session)
) -> ProjectRead:
    project = await get_owned_project(session, project_id, user)
    counts = await clip_counts(session, [project.id])
    return project_to_read(project, counts.get(project.id, 0))


@router.post("/{project_id}/retry", response_model=ProjectRead)
async def retry_project(
    project_id: uuid.UUID, user: User = Depends(current_active_user), session: AsyncSession = Depends(get_session)
) -> ProjectRead:
    """Re-run a failed or stalled project. Stages that already finished are skipped (each stage is idempotent)."""
    project = await get_owned_project(session, project_id, user)
    if project.status != ProjectStatus.failed and not is_stalled(project):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Only failed projects, or ones with no progress for 20+ minutes, can be retried"
        )
    project.status = ProjectStatus.queued
    project.error = None
    project.status_message = "Retrying"
    await session.commit()
    await session.refresh(project)
    enqueue_pipeline(project.id)
    return project_to_read(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
) -> Response:
    project = await get_owned_project(session, project_id, user)
    pid = str(project.id)
    upload = project.storage_key if project.source_type == SourceType.upload else None
    await session.delete(project)
    await session.commit()
    try:
        storage.delete_prefix(f"sources/{pid}/")
        storage.delete_prefix(f"clips/{pid}/")
        if upload:
            storage.delete(upload)
    except Exception:  # storage cleanup is best-effort; the DB row is already gone
        log.exception("Failed to delete storage objects for project %s", pid)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/clips", response_model=list[ClipRead])
async def list_clips(
    project_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
) -> list[ClipRead]:
    project = await get_owned_project(session, project_id, user)
    clips = (
        await session.execute(
            select(Clip).where(Clip.project_id == project.id).order_by(Clip.virality_score.desc(), Clip.start)
        )
    ).scalars().all()
    expires = get_settings().presign_expiry_seconds
    return [clip_to_read(c, storage, expires=expires) for c in clips]


@router.get("/{project_id}/download.zip")
async def download_all(
    project_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
) -> StreamingResponse:
    """All rendered clips as one zip, best first. Streamed: nothing is buffered on the server."""
    project = await get_owned_project(session, project_id, user)
    clips = (
        await session.execute(
            select(Clip)
            .where(Clip.project_id == project.id, Clip.output_key.is_not(None))
            .order_by(Clip.virality_score.desc(), Clip.start)
        )
    ).scalars().all()
    if not clips:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No rendered clips yet")
    entries = [(clip_download_name(c, rank=i + 1), c.output_key) for i, c in enumerate(clips)]
    name = f"{safe_filename(project.title or 'clipforge', default='clipforge')}-clips.zip"
    return StreamingResponse(
        iter_zip(storage, entries),  # type: ignore[arg-type]
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


def _event(project: VideoProject) -> dict:
    payload = ProgressEvent(
        id=project.id,
        status=project.status,
        progress=project.progress,
        status_message=project.status_message,
        error=project.error,
    )
    return {"event": "progress", "data": payload.model_dump_json()}


@router.get("/{project_id}/events")
async def project_events(
    project_id: uuid.UUID, request: Request, user: User = Depends(current_active_user)
) -> EventSourceResponse:
    """Server-Sent Events stream of pipeline progress.

    SSE is a long-lived HTTP response the server keeps writing `event:`/`data:` lines to;
    the browser's EventSource API reconnects automatically if it drops.
    """
    # Short-lived session for the ownership check; don't hold a DB connection for the stream's lifetime.
    async with SessionLocal() as session:
        await get_owned_project(session, project_id, user)

    async def stream():
        redis = Redis.from_url(get_settings().redis_url)
        pubsub = redis.pubsub()
        try:
            # Subscribe *before* reading the snapshot so no update can slip in between.
            await pubsub.subscribe(project_channel(str(project_id)))
            async with SessionLocal() as session:
                project = await session.get(VideoProject, project_id)
            if project is None:
                return
            yield _event(project)
            if project.status in TERMINAL_STATUSES:
                return
            while not await request.is_disconnected():
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=10.0)
                if msg is None:
                    continue
                data = msg["data"].decode() if isinstance(msg["data"], bytes) else msg["data"]
                yield {"event": "progress", "data": data}
                try:
                    if json.loads(data).get("status") in TERMINAL_STATUSES:
                        return
                except ValueError:
                    continue
        finally:
            await pubsub.aclose()
            await redis.aclose()

    return EventSourceResponse(stream(), ping=15, headers={"X-Accel-Buffering": "no"})
