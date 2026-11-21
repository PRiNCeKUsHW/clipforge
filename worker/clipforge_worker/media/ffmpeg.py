"""Thin wrappers around the ffmpeg / ffprobe command-line tools."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from clipforge_worker.errors import PipelineError


@dataclass(frozen=True)
class ProbeInfo:
    duration: float
    has_video: bool
    has_audio: bool
    width: int | None = None
    height: int | None = None


def run(cmd: list[str], what: str, timeout: float | None = None) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise PipelineError(f"{cmd[0]} is not installed in the worker image") from exc
    except subprocess.TimeoutExpired as exc:
        raise PipelineError(f"{what} timed out") from exc
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").strip().splitlines()[-4:])
        raise PipelineError(f"{what} failed: {tail or 'unknown ffmpeg error'}")
    return proc


def probe(path: str | Path) -> ProbeInfo:
    proc = run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        "Reading the video file",
        timeout=120,
    )
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video" and s.get("disposition", {}).get("attached_pic") != 1), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = float(data.get("format", {}).get("duration") or (video or {}).get("duration") or 0.0)
    return ProbeInfo(
        duration=duration,
        has_video=video is not None,
        has_audio=audio is not None,
        width=int(video["width"]) if video and video.get("width") else None,
        height=int(video["height"]) if video and video.get("height") else None,
    )


def extract_audio(src: str | Path, dst: str | Path) -> None:
    """16 kHz mono 16-bit WAV: exactly what Whisper consumes, so no resampling at transcription time."""
    tmp = Path(str(dst) + ".tmp.wav")
    run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(tmp)],
        "Extracting audio",
    )
    tmp.replace(dst)  # atomic: a crash never leaves a half-written file that looks complete


@dataclass(frozen=True)
class CropBox:
    w: int
    h: int
    x: int
    y: int


_CROPDETECT_RE = re.compile(r"crop=(\d+):(\d+):(\d+):(\d+)")


def detect_letterbox(src: str | Path, start: float, duration: float, frame_w: int, frame_h: int) -> CropBox | None:
    """Black bars baked into the picture (e.g. a widescreen film inside a 16:9 frame).
    Returns the picture area if there are top/bottom bars worth removing, else None.
    Only letterboxing is handled: side bars would shift the face-tracking x coordinates."""
    if frame_w <= 0 or frame_h <= 0:
        return None
    probe_len = max(1.0, min(duration, 12.0))
    proc = subprocess.run(
        [
            "ffmpeg", "-v", "info", "-ss", f"{max(0.0, start):.3f}", "-i", str(src), "-t", f"{probe_len:.3f}",
            "-vf", "fps=2,cropdetect=limit=24:round=2:reset=0", "-an", "-f", "null", "-",
        ],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    found = _CROPDETECT_RE.findall(proc.stderr or "")
    if not found:
        return None
    w, h, x, y = (int(v) for v in found[-1])  # with reset=0 the last line covers the whole probe
    if w < frame_w * 0.98 or h > frame_h * 0.95 or h < frame_h * 0.4:
        return None  # side bars, no real bars, or a mostly-black/unstable picture
    # shave a few pixels more: bar edges are often a soft dark gradient, not pure black
    margin = 4
    return CropBox(w=frame_w, h=h - 2 * margin, x=0, y=y + margin)


def cut_clip(src: str | Path, dst: str | Path, start: float, end: float, crop: CropBox | None = None) -> None:
    """Frame-accurate cut, re-encoded to H.264/AAC with loudness normalised to -14 LUFS (the
    level YouTube/Instagram normalise to). +faststart lets the browser play before full download.
    `crop` removes baked-in letterbox bars."""
    tmp = Path(str(dst) + ".tmp.mp4")
    duration = max(0.1, end - start)
    vf = ["-vf", f"crop={crop.w}:{crop.h}:{crop.x}:{crop.y}"] if crop else []
    run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{duration:.3f}",
            "-map", "0:v:0", "-map", "0:a:0?",
            *vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
            "-movflags", "+faststart",
            str(tmp),
        ],
        "Cutting the clip",
    )  # fmt: skip
    tmp.replace(dst)


def extract_frame(src: str | Path, dst: str | Path, t: float, width: int = 640, quality: int = 4) -> None:
    run(
        [
            "ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(src),
            "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", str(quality), str(dst),
        ],
        "Extracting a frame",
        timeout=120,
    )  # fmt: skip
