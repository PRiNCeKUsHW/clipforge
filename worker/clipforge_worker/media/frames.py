from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from clipforge_worker.errors import PipelineError
from clipforge_worker.highlights.llm import FrameImage
from clipforge_worker.media.ffmpeg import extract_frame

log = logging.getLogger(__name__)


def frame_timestamps(duration: float, max_frames: int, min_interval: float = 10.0) -> list[float]:
    """Evenly spaced sample times, at most one every `min_interval` seconds, skipping the very start/end."""
    if duration <= 0 or max_frames <= 0:
        return []
    count = min(max_frames, max(1, int(duration // min_interval)))
    step = duration / (count + 1)
    return [round(step * (i + 1), 2) for i in range(count)]


def sample_frames(video: str | Path, duration: float, max_frames: int) -> list[FrameImage]:
    """Small JPEG frames for Gemini to judge visual moments in low-dialogue videos."""
    frames: list[FrameImage] = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, t in enumerate(frame_timestamps(duration, max_frames)):
            out = Path(tmp) / f"f{i:03d}.jpg"
            try:
                extract_frame(video, out, t, width=512, quality=6)
                frames.append(FrameImage(timestamp=t, jpeg=out.read_bytes()))
            except PipelineError as exc:
                log.warning("Skipping frame at %.1fs: %s", t, exc.user_message)
    return frames
