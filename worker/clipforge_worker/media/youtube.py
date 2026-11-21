"""YouTube downloads via yt-dlp."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from clipforge_worker.errors import PipelineError, TransientError

log = logging.getLogger(__name__)

# 403 on the media stream is usually YouTube throttling/expired stream URLs: worth retrying with backoff.
_TRANSIENT_HINTS = (
    "timed out",
    "connection reset",
    "temporary failure",
    "http error 5",
    "unable to download webpage",
    "http error 403",
    "http error 429",
)


def _readable(exc: Exception) -> Exception:
    msg = str(exc).replace("ERROR: ", "").strip()
    low = msg.lower()
    if any(h in low for h in _TRANSIENT_HINTS):
        return TransientError(msg)
    if "private video" in low:
        return PipelineError("This YouTube video is private.")
    if "sign in to confirm your age" in low or "age-restricted" in low:
        return PipelineError("This video is age-restricted. Provide a cookies file via YTDLP_COOKIES_FILE to download it.")
    if "not a bot" in low:
        return PipelineError(
            "YouTube is asking to confirm this isn't a bot. Set YTDLP_COOKIES_FILE to a cookies.txt "
            "exported from your browser and retry."
        )
    if "video unavailable" in low or "removed" in low:
        return PipelineError("This YouTube video is unavailable.")
    if "is live" in low or "live event" in low:
        return PipelineError("Live streams can't be processed until they've finished.")
    return PipelineError(f"Couldn't download the YouTube video: {msg[:300]}")


def download_youtube(
    url: str,
    out_dir: Path,
    *,
    max_height: int = 1080,
    max_duration_s: float | None = None,
    cookies_file: str | None = None,
    on_progress: Callable[[float], None] | None = None,
) -> tuple[Path, dict[str, Any]]:
    import yt_dlp

    out_dir.mkdir(parents=True, exist_ok=True)

    def hook(d: dict[str, Any]) -> None:
        if on_progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                on_progress(min(d.get("downloaded_bytes", 0) / total, 1.0))

    h = max_height
    opts: dict[str, Any] = {
        # Prefer <=30fps H.264 MP4 + M4A (half the size of 60fps, fast to cut, plays everywhere);
        # fall back to anything <= max height.
        "format": (
            f"bv*[height<={h}][fps<=30][vcodec^=avc1]+ba[ext=m4a]/"
            f"bv*[height<={h}][vcodec^=avc1]+ba[ext=m4a]/bv*[height<={h}][ext=mp4]+ba[ext=m4a]/"
            f"bv*[height<={h}]+ba/b[height<={h}]/b"
        ),
        "merge_output_format": "mp4",
        "outtmpl": str(out_dir / "source.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "retries": 5,
        "fragment_retries": 5,
        "progress_hooks": [hook],
        # YouTube's signature challenges need a JS runtime. The Docker image ships Deno;
        # Node works too (handy when running outside Docker).
        "js_runtimes": {"deno": {}, "node": {}},
    }
    if cookies_file:
        opts["cookiefile"] = cookies_file

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                raise PipelineError("Couldn't read that YouTube link.")
            if info.get("is_live"):
                raise PipelineError("Live streams can't be processed until they've finished.")
            duration = info.get("duration") or 0
            if max_duration_s and duration > max_duration_s:
                raise PipelineError(
                    f"This video is {duration / 60:.0f} minutes long; the limit is {max_duration_s / 60:.0f} minutes "
                    "(MAX_VIDEO_MINUTES)."
                )
            info = ydl.process_ie_result(info, download=True)
    except (PipelineError, TransientError):
        raise
    except yt_dlp.utils.DownloadError as exc:
        raise _readable(exc) from exc

    files = [p for p in out_dir.glob("source.*") if p.suffix not in (".part", ".ytdl") and p.is_file()]
    if not files:
        raise PipelineError("yt-dlp finished but no video file was produced.")
    path = max(files, key=lambda p: p.stat().st_size)
    return path, info
