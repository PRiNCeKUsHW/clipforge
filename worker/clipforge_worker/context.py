"""Lazily-created, per-process shared resources (storage client, Redis, Whisper model)."""

from __future__ import annotations

import shutil
import uuid
from functools import lru_cache
from pathlib import Path

from redis import Redis
from sqlalchemy import update

from app.core.storage import Storage
from app.models import VideoProject
from clipforge_worker.config import get_settings
from clipforge_worker.progress import ProgressReporter
from clipforge_worker.transcription.base import Transcriber


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    return Storage(
        bucket=s.s3_bucket,
        access_key=s.s3_access_key,
        secret_key=s.s3_secret_key,
        endpoint_url=s.s3_endpoint_url,
        public_endpoint_url=s.s3_public_endpoint_url,
        region=s.s3_region,
    )


@lru_cache
def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url)


@lru_cache
def get_transcriber() -> Transcriber:
    """Loaded once per worker process (model load takes seconds and lots of RAM)."""
    from clipforge_worker.transcription.device import resolve_whisper_config
    from clipforge_worker.transcription.faster_whisper_transcriber import FasterWhisperTranscriber

    s = get_settings()
    cfg = resolve_whisper_config(s.whisper_device, s.whisper_model, s.whisper_compute_type)
    return FasterWhisperTranscriber(
        cfg,
        download_root=str(Path(s.model_dir) / "whisper"),
        language=s.whisper_language or None,
        beam_size=s.whisper_beam_size,
    )


@lru_cache
def get_detector():
    """Face detector, created once per worker process."""
    from clipforge_worker.reframe.detect import make_detector

    s = get_settings()
    return make_detector(s.reframe_detector, s.mediapipe_model_path)


def _write_project(project_id: uuid.UUID, fields: dict) -> None:
    from clipforge_worker.db import session_scope

    with session_scope() as session:
        session.execute(update(VideoProject).where(VideoProject.id == project_id).values(**fields))


def reporter_for(project_id: uuid.UUID) -> ProgressReporter:
    return ProgressReporter(project_id, write=_write_project, publish=lambda ch, msg: get_redis().publish(ch, msg))


# ---------- local scratch files (shared docker volume between the worker containers) ----------
def project_dir(project_id: uuid.UUID | str) -> Path:
    path = Path(get_settings().work_dir) / str(project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_project_dir(project_id: uuid.UUID | str) -> None:
    shutil.rmtree(Path(get_settings().work_dir) / str(project_id), ignore_errors=True)
