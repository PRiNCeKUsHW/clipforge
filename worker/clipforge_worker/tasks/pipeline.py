"""The video pipeline as a Celery chain:

    ingest -> extract_audio -> transcribe -> find_highlights -> reframe_clips -> render_clips

Every stage is idempotent: it first checks whether its output already exists and skips
the work if so. That makes Celery retries and the "Retry" button safe, and lets a failed
project resume from where it stopped.
"""

from __future__ import annotations

import json
import tempfile
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from botocore.exceptions import ConnectionClosedError, EndpointConnectionError
from celery import Task, chain
from celery.exceptions import Ignore
from celery.utils.log import get_task_logger
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.channels import project_channel
from app.core.storage import clip_key, source_key, thumbnail_key
from app.core.crypto import TokenCipher
from app.models import (
    Clip,
    ClipStatus,
    Platform,
    ProjectStatus,
    PublishJob,
    PublishStatus,
    SocialAccount,
    SourceType,
    VideoProject,
)
from clipforge_worker.celery_app import app
from clipforge_worker.config import get_settings
from clipforge_worker.context import (
    cleanup_project_dir,
    get_detector,
    get_redis,
    get_storage,
    get_transcriber,
    project_dir,
    reporter_for,
)
from clipforge_worker.db import session_scope
from clipforge_worker.errors import PipelineError, TransientError
from clipforge_worker.highlights.llm import GeminiClient
from clipforge_worker.highlights.selector import HighlightOptions, select_highlights
from clipforge_worker.media import ffmpeg
from clipforge_worker.media.frames import sample_frames
from clipforge_worker.media.youtube import download_youtube
from clipforge_worker.publish import instagram as instagram_api
from clipforge_worker.publish import youtube as youtube_api
from clipforge_worker.reframe.planner import ReframeOptions, plan_crop
from clipforge_worker.reframe.video import sample_faces, video_size
from clipforge_worker.render.client import RendererClient
from clipforge_worker.render.props import FRAMED_LAYOUTS, build_props, split_mode_for
from clipforge_worker.transcript import Transcript
from clipforge_worker.transcription.whisperx_refine import refine_transcript

log = get_task_logger(__name__)


# ---------------------------------------------------------------- failure handling
def readable_error(exc: BaseException, stage_label: str) -> str:
    if isinstance(exc, PipelineError):
        return exc.user_message
    if isinstance(exc, TransientError) and "403" in str(exc):
        return (
            f"YouTube refused the download (HTTP 403) even after retries. Try again later, update yt-dlp "
            f"(rebuild the worker), or set YTDLP_COOKIES_FILE. Details: {exc}"
        )
    if isinstance(exc, TransientError | EndpointConnectionError | ConnectionClosedError | ConnectionError):
        return f"A temporary problem kept happening while {stage_label} (retried several times): {exc}"
    return f"Unexpected error while {stage_label}: {type(exc).__name__}: {str(exc)[:300]}"


def mark_failed(project_id: str, message: str) -> None:
    pid = uuid.UUID(project_id)
    with session_scope() as session:
        project = session.get(VideoProject, pid)
        if project is None:
            return
        project.status = ProjectStatus.failed
        project.error = message
        project.status_message = None
        progress = project.progress
    payload = {"id": project_id, "status": "failed", "progress": progress, "status_message": None, "error": message}
    try:
        get_redis().publish(project_channel(project_id), json.dumps(payload))
    except Exception:
        log.warning("Could not publish failure event", exc_info=True)


class PipelineTask(Task):
    """Base task: retries transient errors with exponential backoff; on final failure stores a
    readable error on the project so the UI can show it."""

    autoretry_for = (TransientError, EndpointConnectionError, ConnectionClosedError, ConnectionError, TimeoutError)
    retry_backoff = 10
    retry_backoff_max = 300
    retry_jitter = True
    max_retries = 3
    stage_label = "processing the video"

    def on_failure(self, exc, task_id, args, kwargs, einfo):  # noqa: D401
        project_id = args[0] if args else kwargs.get("project_id")
        if project_id:
            log.error("Project %s failed in %s: %s", project_id, self.name, exc)
            mark_failed(project_id, readable_error(exc, self.stage_label))


def _load(session: Session, project_id: str) -> VideoProject:
    project = session.get(VideoProject, uuid.UUID(project_id))
    if project is None:
        # Deleted while processing: stop quietly (Ignore also stops the rest of the chain).
        raise Ignore()
    return project


# ---------------------------------------------------------------- local file helpers
def ensure_local_source(project_id: str, key: str) -> Path:
    """Local copy of the source video, downloaded from storage if missing or incomplete."""
    storage = get_storage()
    head = storage.head(key)
    if head is None:
        raise PipelineError("The source video is missing from storage. Please submit it again.")
    local = project_dir(project_id) / f"source{Path(key).suffix or '.mp4'}"
    if not local.exists() or local.stat().st_size != int(head.get("ContentLength", -1)):
        storage.download_file(key, local)
    return local


def ensure_audio(project_id: str, source: Path) -> Path:
    audio = project_dir(project_id) / "audio.wav"
    if audio.exists() and audio.stat().st_size > 0:
        return audio
    if not ffmpeg.probe(source).has_audio:
        raise PipelineError("This video has no audio track, so there's nothing to transcribe.")
    ffmpeg.extract_audio(source, audio)
    return audio


# ---------------------------------------------------------------- tasks
@app.task(bind=True, base=PipelineTask, name="clipforge.pipeline.start", stage_label="starting the pipeline")
def start_pipeline(self, project_id: str) -> None:
    chain(
        ingest.si(project_id),
        extract_audio.si(project_id),
        transcribe.si(project_id),
        find_highlights.si(project_id),
        reframe_clips.si(project_id),
        render_clips.si(project_id),
    ).apply_async()


@app.task(bind=True, base=PipelineTask, name="clipforge.pipeline.ingest", stage_label="downloading the video")
def ingest(self, project_id: str) -> None:
    settings = get_settings()
    storage = get_storage()
    rep = reporter_for(uuid.UUID(project_id))
    with session_scope() as session:
        p = _load(session, project_id)
        source_type, url, key = p.source_type, p.source_url, p.storage_key

    is_youtube = source_type == SourceType.youtube
    rep.stage("downloading", 0, "Downloading video" if is_youtube else "Checking upload", force=True)

    if is_youtube and not (key and storage.exists(key)):
        assert url
        path, info = download_youtube(
            url,
            project_dir(project_id),
            max_height=settings.ytdlp_max_height,
            max_duration_s=settings.max_video_minutes * 60,
            cookies_file=settings.ytdlp_cookies_file or None,
            on_progress=lambda f: rep.stage("downloading", f * 0.9, f"Downloading video {int(f * 100)}%"),
        )
        rep.stage("downloading", 0.92, "Saving video", force=True)
        key = source_key(project_id, path.suffix.lstrip(".") or "mp4")
        storage.upload_file(path, key, content_type="video/mp4")
        with session_scope() as session:
            p = _load(session, project_id)
            p.storage_key = key
            if not p.title and info.get("title"):
                p.title = str(info["title"])[:300]

    if not key or not storage.exists(key):
        raise PipelineError("The uploaded video couldn't be found. Please upload it again.")

    local = ensure_local_source(project_id, key)
    info = ffmpeg.probe(local)
    if not info.has_video:
        raise PipelineError("That file doesn't contain a video stream.")
    if info.duration <= 0:
        raise PipelineError("Couldn't determine the video's length; the file may be corrupt.")
    if info.duration > settings.max_video_minutes * 60:
        raise PipelineError(
            f"This video is {info.duration / 60:.0f} minutes long; the limit is {settings.max_video_minutes} minutes."
        )
    with session_scope() as session:
        _load(session, project_id).duration = info.duration
    rep.stage("downloading", 1.0, "Video ready", force=True)


@app.task(bind=True, base=PipelineTask, name="clipforge.pipeline.extract_audio", stage_label="extracting audio")
def extract_audio(self, project_id: str) -> None:
    rep = reporter_for(uuid.UUID(project_id))
    with session_scope() as session:
        p = _load(session, project_id)
        if p.transcript is not None:
            return  # already transcribed: no audio needed
        key = p.storage_key
    assert key
    rep.stage("extracting_audio", 0, "Extracting audio", force=True)
    ensure_audio(project_id, ensure_local_source(project_id, key))
    rep.stage("extracting_audio", 1.0, "Audio ready", force=True)


@app.task(bind=True, base=PipelineTask, name="clipforge.pipeline.transcribe", stage_label="transcribing")
def transcribe(self, project_id: str) -> None:
    settings = get_settings()
    rep = reporter_for(uuid.UUID(project_id))
    with session_scope() as session:
        p = _load(session, project_id)
        if p.transcript is not None:
            return
        key = p.storage_key
    assert key
    # Normally the audio is already on the shared volume; recreate it if this worker can't see it.
    audio = ensure_audio(project_id, ensure_local_source(project_id, key))

    rep.stage("transcribing", 0, "Loading speech model (first run downloads it)", force=True)
    transcriber = get_transcriber()
    refining = settings.align_words or settings.diarize
    span = 0.9 if refining else 1.0
    rep.stage("transcribing", 0, "Transcribing", force=True)
    transcript = transcriber.transcribe(
        str(audio), on_progress=lambda f: rep.stage("transcribing", f * span, f"Transcribing {int(f * 100)}%")
    )
    if refining:
        rep.stage("transcribing", 0.92, "Aligning words / identifying speakers", force=True)
        cfg = getattr(transcriber, "config", None)
        transcript = refine_transcript(
            transcript,
            str(audio),
            device=getattr(cfg, "device", "cpu"),
            align_words=settings.align_words,
            diarize=settings.diarize,
            hf_token=settings.hf_token,
            model_dir=str(Path(settings.model_dir) / "align"),
        )

    with session_scope() as session:
        p = _load(session, project_id)
        p.transcript = transcript.model_dump(mode="json", exclude_none=True)
        p.language = transcript.language
    rep.stage("transcribing", 1.0, f"Transcribed {len(transcript.all_words())} words", force=True)


@app.task(bind=True, base=PipelineTask, name="clipforge.pipeline.find_highlights", stage_label="finding highlights")
def find_highlights(self, project_id: str) -> None:
    settings = get_settings()
    rep = reporter_for(uuid.UUID(project_id))
    pid = uuid.UUID(project_id)
    with session_scope() as session:
        p = _load(session, project_id)
        if session.scalar(select(func.count(Clip.id)).where(Clip.project_id == pid)):
            return  # highlights already chosen
        if p.transcript is None:
            raise PipelineError("The transcript is missing; please retry.")
        transcript = Transcript.model_validate(p.transcript)
        if p.duration:
            transcript = transcript.model_copy(update={"duration": p.duration})
        instruction, key = p.instruction, p.storage_key
        project_layout, project_style = p.layout, p.caption_style

    rep.stage("finding_highlights", 0, "Asking Gemini for the best moments", force=True)
    mode = settings.highlight_use_frames
    use_frames = mode == "true" or (
        mode == "auto" and transcript.words_per_minute() < settings.low_dialogue_words_per_minute
    )
    if not transcript.all_words() and not use_frames:
        raise PipelineError("No speech was detected in this video, so no clips could be found.")
    frames = None
    if use_frames and key:
        rep.stage("finding_highlights", 0.1, "Sampling video frames", force=True)
        frames = sample_frames(ensure_local_source(project_id, key), transcript.duration, settings.max_frames)

    options = HighlightOptions(
        min_seconds=settings.highlight_min_seconds,
        max_seconds=settings.highlight_max_seconds,
        min_clips=settings.highlight_min_clips,
        max_clips=settings.highlight_max_clips,
        chunk_threshold=settings.highlight_chunk_threshold_seconds,
        chunk_seconds=settings.highlight_chunk_seconds,
        chunk_overlap=settings.highlight_chunk_overlap_seconds,
    )
    rep.stage("finding_highlights", 0.2, "Asking Gemini for the best moments", force=True)
    selected = select_highlights(
        transcript, GeminiClient(settings.gemini_api_key, settings.gemini_model), options,
        instruction=instruction, frames=frames,
    )  # fmt: skip

    with session_scope() as session:
        _load(session, project_id)
        if session.scalar(select(func.count(Clip.id)).where(Clip.project_id == pid)):
            return  # another run won the race
        for c in selected:
            session.add(
                Clip(
                    project_id=pid,
                    start=c.start,
                    end=c.end,
                    hook_title=c.hook_title[:200],
                    virality_score=c.virality_score,
                    score_breakdown=c.score_breakdown.model_dump(),
                    reason=c.reason,
                    description=c.description or None,
                    hashtags=c.hashtags,
                    caption_style=project_style or settings.default_caption_style,
                    layout=project_layout or "auto",
                    transcript_words=[w.model_dump(exclude_none=True) for w in transcript.words_between(c.start, c.end)],
                    status=ClipStatus.pending,
                )
            )
    rep.stage("finding_highlights", 1.0, f"Found {len(selected)} clips", force=True)


@app.task(bind=True, base=PipelineTask, name="clipforge.pipeline.reframe_clips", stage_label="reframing to 9:16")
def reframe_clips(self, project_id: str) -> None:
    """Compute a 9:16 crop path (face tracking, speaker following, split screen) for every clip."""
    rep = reporter_for(uuid.UUID(project_id))
    pid = uuid.UUID(project_id)
    with session_scope() as session:
        p = _load(session, project_id)
        key = p.storage_key
        todo = [c.id for c in session.scalars(select(Clip).where(Clip.project_id == pid, Clip.crop_path.is_(None)))]
    if not todo:
        return
    assert key
    local = ensure_local_source(project_id, key)
    for i, clip_id in enumerate(todo):
        rep.stage("reframing", i / len(todo), f"Tracking faces in clip {i + 1} of {len(todo)}", force=True)
        reframe_one(clip_id, local)
    rep.stage("reframing", 1.0, "Framing ready", force=True)


def reframe_one(clip_id: uuid.UUID, source: Path) -> dict:
    settings = get_settings()
    with session_scope() as session:
        clip = session.get(Clip, clip_id)
        if clip is None:
            raise Ignore()
        start, end, layout = clip.start, clip.end, clip.layout or "auto"
        words = [
            {"start": float(w["start"]) - start, "end": float(w["end"]) - start, "speaker": w.get("speaker")}
            for w in clip.transcript_words or []
        ]
    src_w, src_h = video_size(source)
    try:
        # Framed layouts show the whole frame, so there's nothing to track.
        samples = (
            []
            if layout in FRAMED_LAYOUTS
            else sample_faces(source, start, end, get_detector(), sample_fps=settings.reframe_sample_fps)
        )
    except PipelineError:
        raise
    except Exception as exc:  # face tracking is an enhancement: fall back to a centre crop
        log.warning("Face tracking failed for clip %s (%s); using a centre crop", clip_id, exc)
        samples = []
    crop = plan_crop(
        samples,
        src_w,
        src_h,
        words,
        ReframeOptions(
            smoothing=settings.reframe_smoothing,
            deadzone=settings.reframe_deadzone,
            split_screen=split_mode_for(layout, settings.reframe_split_screen),
        ),
    )
    with session_scope() as session:
        clip = session.get(Clip, clip_id)
        if clip is not None:
            clip.crop_path = crop
    return crop


class ClipProgress:
    """Throttled writes of a clip's render progress (0-100) to the database."""

    def __init__(self, clip_id: uuid.UUID, min_interval: float = 1.5) -> None:
        self.clip_id = clip_id
        self.min_interval = min_interval
        self._last = 0.0
        self._last_pct = -1

    def __call__(self, fraction: float) -> None:
        pct = int(max(0.0, min(1.0, fraction)) * 100)
        now = time.monotonic()
        if pct == self._last_pct or (now - self._last < self.min_interval and pct < 100):
            return
        self._last, self._last_pct = now, pct
        with session_scope() as session:
            session.execute(update(Clip).where(Clip.id == self.clip_id).values(progress=pct))


def render_one(project_id: str, clip_id: uuid.UUID, on_progress) -> None:
    """Cut the clip segment, render it with Remotion (crop + captions), upload video + thumbnail."""
    settings = get_settings()
    storage = get_storage()
    with session_scope() as session:
        clip = session.get(Clip, clip_id)
        if clip is None:
            raise Ignore()
        project = session.get(VideoProject, clip.project_id)
        key = project.storage_key if project else None
        start, end = clip.start, clip.end
        words, crop, style = list(clip.transcript_words or []), clip.crop_path, clip.caption_style
        layout, title = clip.layout or "auto", clip.hook_title
        clip.status, clip.error, clip.progress = ClipStatus.rendering, None, 0
    if not key:
        raise PipelineError("The source video is missing; please re-submit the project.")

    source = ensure_local_source(project_id, key)
    if crop is None:
        on_progress(0.02)
        crop = reframe_one(clip_id, source)

    out_dir = project_dir(project_id) / "render"
    out_dir.mkdir(parents=True, exist_ok=True)
    segment, output, thumb = out_dir / f"{clip_id}_src.mp4", out_dir / f"{clip_id}.mp4", out_dir / f"{clip_id}.jpg"
    try:
        info = ffmpeg.probe(source)
        bars = ffmpeg.detect_letterbox(source, start, end - start, info.width or 0, info.height or 0)
        ffmpeg.cut_clip(source, segment, start, end, crop=bars)
        if bars:
            # Letterbox only trims top/bottom, so face-tracking x positions stay valid;
            # the renderer just needs the new picture size.
            crop = {**crop, "source": {"w": bars.w, "h": bars.h}}
        on_progress(0.1)
        props = build_props(
            clip_start=start, clip_end=end, transcript_words=words, crop_path=crop, caption_style=style,
            layout=layout, title=title,
            fps=settings.render_fps,
        )  # fmt: skip
        RendererClient(settings.renderer_url, settings.render_timeout_seconds).render(
            segment, output, props, on_progress=lambda f: on_progress(0.1 + 0.85 * f)
        )
        ffmpeg.extract_frame(output, thumb, t=min(1.0, (end - start) / 2), width=540)
        storage.upload_file(output, clip_key(project_id, str(clip_id)), "video/mp4")
        storage.upload_file(thumb, thumbnail_key(project_id, str(clip_id)), "image/jpeg")
    finally:
        for f in (segment, output, thumb):
            f.unlink(missing_ok=True)

    with session_scope() as session:
        clip = session.get(Clip, clip_id)
        if clip is not None:
            clip.output_key = clip_key(project_id, str(clip_id))
            clip.thumbnail_key = thumbnail_key(project_id, str(clip_id))
            clip.status, clip.error, clip.progress = ClipStatus.ready, None, 100


@app.task(bind=True, base=PipelineTask, name="clipforge.pipeline.render_clips", stage_label="rendering clips")
def render_clips(self, project_id: str) -> None:
    """Render every clip that isn't ready yet (vertical 1080x1920, animated captions)."""
    settings = get_settings()
    rep = reporter_for(uuid.UUID(project_id))
    pid = uuid.UUID(project_id)
    with session_scope() as session:
        _load(session, project_id)
        todo = [
            c.id
            for c in session.scalars(
                select(Clip)
                .where(Clip.project_id == pid, or_(Clip.status != ClipStatus.ready, Clip.output_key.is_(None)))
                .order_by(Clip.virality_score.desc())
            )
        ]

    for i, clip_id in enumerate(todo):
        label = f"Rendering clip {i + 1} of {len(todo)}"
        rep.stage("rendering", i / len(todo), label, force=True)
        clip_progress = ClipProgress(clip_id)

        def progress(f: float, _i: int = i, _label: str = label, _cp: ClipProgress = clip_progress) -> None:
            _cp(f)
            rep.stage("rendering", (_i + f) / len(todo), f"{_label} ({int(f * 100)}%)")

        try:
            render_one(project_id, clip_id, progress)
        except PipelineError as exc:
            log.warning("Clip %s failed: %s", clip_id, exc.user_message)
            with session_scope() as session:
                clip = session.get(Clip, clip_id)
                if clip:
                    clip.status, clip.error = ClipStatus.failed, exc.user_message

    with session_scope() as session:
        ready = session.scalar(select(func.count(Clip.id)).where(Clip.project_id == pid, Clip.status == ClipStatus.ready))
        first_error = session.scalar(select(Clip.error).where(Clip.project_id == pid, Clip.error.is_not(None)).limit(1))
    if not ready:
        raise PipelineError(f"None of the clips could be rendered. {first_error or ''}".strip())

    rep.update(status=ProjectStatus.ready, progress=100, message=f"{ready} clips ready", force=True)
    if settings.cleanup_work_files:
        cleanup_project_dir(project_id)


# ---------------------------------------------------------------- editor: re-render one clip
class ClipTask(Task):
    autoretry_for = PipelineTask.autoretry_for
    retry_backoff = 10
    retry_backoff_max = 120
    max_retries = 2

    def on_failure(self, exc, task_id, args, kwargs, einfo):  # noqa: D401
        clip_id = args[0] if args else kwargs.get("clip_id")
        with session_scope() as session:
            clip = session.get(Clip, uuid.UUID(clip_id))
            if clip:
                clip.status = ClipStatus.failed
                clip.error = readable_error(exc, "re-rendering the clip")


@app.task(bind=True, base=ClipTask, name="clipforge.render.clip")
def rerender_clip(self, clip_id: str) -> None:
    cid = uuid.UUID(clip_id)
    with session_scope() as session:
        clip = session.get(Clip, cid)
        if clip is None:
            raise Ignore()
        project_id = str(clip.project_id)
    render_one(project_id, cid, ClipProgress(cid))


# ---------------------------------------------------------------- publishing
class PublishTask(Task):
    autoretry_for = PipelineTask.autoretry_for
    retry_backoff = 30
    retry_backoff_max = 600
    max_retries = 4

    def on_failure(self, exc, task_id, args, kwargs, einfo):  # noqa: D401
        job_id = args[0] if args else kwargs.get("job_id")
        with session_scope() as session:
            job = session.get(PublishJob, uuid.UUID(job_id))
            if job:
                job.status = PublishStatus.failed
                job.error = readable_error(exc, "publishing")


def public_media_url(key: str) -> str:
    base = get_settings().public_media_base_url.rstrip("/")
    return f"{base}/{key}" if base else get_storage().presign_get(key, 6 * 3600)


@app.task(bind=True, base=PublishTask, name="clipforge.publish.run")
def publish_clip(self, job_id: str) -> None:
    settings = get_settings()
    jid = uuid.UUID(job_id)
    with session_scope() as session:
        job = session.get(PublishJob, jid)
        if job is None:
            raise Ignore()
        if job.status == PublishStatus.published:
            return
        clip = session.get(Clip, job.clip_id)
        account = session.get(SocialAccount, job.social_account_id) if job.social_account_id else None
        if clip is None or not clip.output_key:
            raise PipelineError("The clip has no rendered video to publish.")
        if account is None:
            raise PipelineError("The connected account was removed. Reconnect it and try again.")
        job.status, job.error = PublishStatus.uploading, None
        platform, title, description, privacy = job.platform, job.title or clip.hook_title, job.description or "", job.privacy_status
        output_key, tags = clip.output_key, list(clip.hashtags or [])
        acc_id, ext_id = account.id, account.external_account_id
        access_enc, refresh_enc, expires_at = account.access_token_encrypted, account.refresh_token_encrypted, account.expires_at

    cipher = TokenCipher(settings.token_encryption_key)
    with httpx.Client(timeout=60) as http:
        if platform == Platform.youtube:
            access = cipher.decrypt(access_enc)
            if refresh_enc and (expires_at is None or expires_at <= datetime.now(UTC) + timedelta(minutes=2)):
                access, new_expiry = youtube_api.refresh_access_token(
                    http, settings.google_client_id, settings.google_client_secret, cipher.decrypt(refresh_enc)
                )
                with session_scope() as session:
                    acc = session.get(SocialAccount, acc_id)
                    if acc:
                        acc.access_token_encrypted, acc.expires_at = cipher.encrypt(access), new_expiry
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "clip.mp4"
                get_storage().download_file(output_key, path)
                video_id = youtube_api.upload_video(
                    http, access, path, title=title, description=description, tags=tags,
                    privacy_status=privacy or "private",
                )  # fmt: skip
            external_id, external_url = video_id, f"https://youtube.com/shorts/{video_id}"
        elif platform == Platform.instagram:
            media_id, permalink = instagram_api.publish_reel(
                http, cipher.decrypt(access_enc), ext_id, public_media_url(output_key), description,
                graph_version=settings.meta_graph_version,
            )  # fmt: skip
            external_id, external_url = media_id, permalink
        else:
            raise PipelineError(f"Unsupported platform {platform}")

    with session_scope() as session:
        job = session.get(PublishJob, jid)
        if job:
            job.status, job.error = PublishStatus.published, None
            job.external_id, job.external_url = external_id, external_url
            job.published_at = datetime.now(UTC)
