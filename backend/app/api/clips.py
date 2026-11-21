import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import current_active_user
from app.core.config import get_settings
from app.core.db import get_session
from app.core.deps import get_storage
from app.core.storage import Storage
from app.core.tasks import enqueue_publish, enqueue_render
from app.models import ClipStatus, PublishJob, PublishStatus, SocialAccount, User, VideoProject
from app.schemas.clip import ClipDetail, ClipUpdate, DownloadResponse, PublishJobRead, PublishRequest
from app.services.editing import (
    CAPTION_STYLES,
    LAYOUTS,
    MAX_CLIP_SECONDS,
    MIN_CLIP_SECONDS,
    apply_word_texts,
    retime_words,
)
from app.services.projects import clip_download_name, clip_to_read, get_owned_clip

router = APIRouter(prefix="/clips", tags=["clips"])


async def _detail(session: AsyncSession, clip, storage: Storage) -> ClipDetail:
    project = await session.get(VideoProject, clip.project_id)
    return clip_to_read(clip, storage, detail=True, expires=get_settings().presign_expiry_seconds, project=project)  # type: ignore[return-value]


@router.get("/{clip_id}", response_model=ClipDetail)
async def get_clip(
    clip_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
) -> ClipDetail:
    clip = await get_owned_clip(session, clip_id, user)
    return await _detail(session, clip, storage)


@router.patch("/{clip_id}", response_model=ClipDetail)
async def update_clip(
    clip_id: uuid.UUID,
    body: ClipUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
) -> ClipDetail:
    """Edit a clip. Changes show up in the video after POST /clips/{id}/render."""
    clip = await get_owned_clip(session, clip_id, user)
    if clip.status == ClipStatus.rendering:
        raise HTTPException(status.HTTP_409_CONFLICT, "This clip is rendering; wait until it finishes")
    project = await session.get(VideoProject, clip.project_id)
    assert project is not None

    if body.start is not None or body.end is not None:
        start = body.start if body.start is not None else clip.start
        end = body.end if body.end is not None else clip.end
        if end - start < MIN_CLIP_SECONDS or end - start > MAX_CLIP_SECONDS:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Clips must be {MIN_CLIP_SECONDS:.0f}-{MAX_CLIP_SECONDS:.0f} seconds long",
            )
        if project.duration and end > project.duration + 0.5:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The clip can't end after the video ends")
        if (round(start, 3), round(end, 3)) != (round(clip.start, 3), round(clip.end, 3)):
            clip.transcript_words = retime_words(project.transcript, list(clip.transcript_words or []), start, end)
            clip.start, clip.end = start, end
            clip.crop_path = None  # re-track faces for the new range on the next render

    if body.word_texts is not None:
        try:
            clip.transcript_words = apply_word_texts(list(clip.transcript_words or []), body.word_texts)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    if body.caption_style is not None:
        if body.caption_style not in CAPTION_STYLES:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown caption style {body.caption_style!r}")
        clip.caption_style = body.caption_style
    if body.layout is not None and body.layout != clip.layout:
        if body.layout not in LAYOUTS:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown layout {body.layout!r}")
        clip.layout = body.layout
        clip.crop_path = None  # re-plan framing for the new layout on the next render
    if body.hook_title is not None:
        clip.hook_title = body.hook_title.strip()
    if body.description is not None:
        clip.description = body.description.strip() or None
    if body.hashtags is not None:
        clip.hashtags = [t.strip().lstrip("#") for t in body.hashtags if t.strip().lstrip("#")][:30]

    await session.commit()
    await session.refresh(clip)
    return await _detail(session, clip, storage)


@router.post("/{clip_id}/render", response_model=ClipDetail, status_code=status.HTTP_202_ACCEPTED)
async def render_clip(
    clip_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
) -> ClipDetail:
    clip = await get_owned_clip(session, clip_id, user)
    if clip.status == ClipStatus.rendering:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already rendering")
    clip.status, clip.progress, clip.error = ClipStatus.rendering, 0, None
    await session.commit()
    await session.refresh(clip)
    enqueue_render(clip.id)
    return await _detail(session, clip, storage)


@router.get("/{clip_id}/download", response_model=DownloadResponse)
async def download_clip(
    clip_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
) -> DownloadResponse:
    clip = await get_owned_clip(session, clip_id, user)
    if not clip.output_key:
        raise HTTPException(status.HTTP_409_CONFLICT, "This clip hasn't finished rendering yet")
    filename = clip_download_name(clip)
    url = storage.presign_get(clip.output_key, get_settings().presign_expiry_seconds, download_name=filename)
    return DownloadResponse(url=url, filename=filename)


@router.post("/{clip_id}/publish", response_model=PublishJobRead, status_code=status.HTTP_202_ACCEPTED)
async def publish_clip(
    clip_id: uuid.UUID,
    body: PublishRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> PublishJob:
    clip = await get_owned_clip(session, clip_id, user)
    if clip.status != ClipStatus.ready or not clip.output_key:
        raise HTTPException(status.HTTP_409_CONFLICT, "Render the clip before publishing it")
    account = await session.get(SocialAccount, body.social_account_id)
    if account is None or account.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connected account not found")
    job = PublishJob(
        clip_id=clip.id,
        social_account_id=account.id,
        platform=account.platform,
        status=PublishStatus.queued,
        title=body.title.strip(),
        description=body.description.strip(),
        privacy_status=body.privacy_status,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    enqueue_publish(job.id)
    return job


@router.get("/{clip_id}/publish-jobs", response_model=list[PublishJobRead])
async def list_publish_jobs(
    clip_id: uuid.UUID, user: User = Depends(current_active_user), session: AsyncSession = Depends(get_session)
) -> list[PublishJob]:
    clip = await get_owned_clip(session, clip_id, user)
    rows = await session.execute(
        select(PublishJob).where(PublishJob.clip_id == clip.id).order_by(PublishJob.created_at.desc())
    )
    return list(rows.scalars().all())
