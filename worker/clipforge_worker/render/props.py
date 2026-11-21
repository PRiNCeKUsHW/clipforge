"""Build the input props for the Remotion `Clip` composition (see renderer/src/types.ts)."""

from __future__ import annotations

from typing import Any

# "none" renders the clip without captions
CAPTION_STYLES = ("bold", "karaoke", "minimal", "beast", "none")
LAYOUTS = ("auto", "podcast_split", "single", "centered_title", "blur_fit")
FRAMED_LAYOUTS = ("centered_title", "blur_fit")  # whole frame shown: no face tracking needed


def split_mode_for(layout: str, default: str) -> str:
    """Reframe split-screen mode for a chosen layout."""
    return {"podcast_split": "force", "single": "false"}.get(layout, default)


def caption_words(transcript_words: list[dict[str, Any]], clip_start: float, clip_end: float) -> list[dict[str, Any]]:
    """Clip words with times relative to the clip start, clamped to the clip. Empty (deleted) words
    are kept out; edited text keeps the original timing."""
    duration = clip_end - clip_start
    out = []
    for w in transcript_words:
        text = str(w.get("word", "")).strip()
        if not text:
            continue
        start = float(w["start"]) - clip_start
        end = float(w["end"]) - clip_start
        if end <= 0 or start >= duration:
            continue
        out.append({"text": text, "start": round(max(0.0, start), 3), "end": round(min(duration, end), 3)})
    return out


def build_props(
    *,
    clip_start: float,
    clip_end: float,
    transcript_words: list[dict[str, Any]],
    crop_path: dict[str, Any],
    caption_style: str,
    fps: int = 30,
    layout: str = "auto",
    title: str = "",
) -> dict[str, Any]:
    style = caption_style if caption_style in CAPTION_STYLES else "bold"
    return {
        "layout": layout if layout in LAYOUTS else "auto",
        "title": title,
        "durationInSeconds": round(clip_end - clip_start, 3),
        "fps": fps,
        "crop": crop_path,
        "words": caption_words(transcript_words, clip_start, clip_end),
        "style": style,
    }
