from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://clipforge:clipforge@localhost:5432/clipforge"
    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_public_endpoint_url: str | None = None
    s3_access_key: str = "clipforge"
    s3_secret_key: str = "clipforge-dev-secret"
    s3_bucket: str = "clipforge"
    s3_region: str = "us-east-1"

    work_dir: str = "/data/work"
    model_dir: str = "/models"
    cleanup_work_files: bool = True
    max_video_minutes: int = 180

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    highlight_min_seconds: float = 20
    # 59, not 90: Shorts over 1 minute that carry a copyright claim get blocked by YouTube
    highlight_max_seconds: float = 59
    highlight_min_clips: int = 5
    highlight_max_clips: int = 10
    highlight_chunk_threshold_seconds: float = 3600
    highlight_chunk_seconds: float = 1500
    highlight_chunk_overlap_seconds: float = 120
    highlight_use_frames: Literal["auto", "true", "false"] = "auto"
    # "auto" frames mode kicks in below this speech density
    low_dialogue_words_per_minute: float = 40
    max_frames: int = 40

    # Transcription
    whisper_device: str = "auto"
    whisper_model: str = "auto"
    whisper_compute_type: str = "auto"
    whisper_language: str = ""
    # 5 = most accurate (Whisper default); 1 = greedy decoding, roughly 2x faster
    whisper_beam_size: int = 5
    align_words: bool = False
    diarize: bool = False
    hf_token: str = ""

    # yt-dlp
    ytdlp_max_height: int = 1080
    ytdlp_cookies_file: str = ""

    # Smart 9:16 reframe
    reframe_sample_fps: float = 3.0
    reframe_detector: Literal["mediapipe", "haar"] = "mediapipe"
    # Baked into the image outside /models (that path is a volume and would hide it)
    mediapipe_model_path: str = "/opt/models/blaze_face_short_range.tflite"
    reframe_split_screen: Literal["auto", "true", "false"] = "auto"
    reframe_smoothing: float = 0.35
    reframe_deadzone: float = 0.05

    # Rendering (Remotion service)
    renderer_url: str = "http://renderer:3100"
    render_fps: int = 30
    default_caption_style: str = "bold"
    render_timeout_seconds: int = 1800

    # Publishing
    token_encryption_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_graph_version: str = "v21.0"
    # Public base URL for clip files (e.g. an R2 public bucket/custom domain). Instagram must
    # download the video from a public URL; if empty a presigned URL is used.
    public_media_base_url: str = ""


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
