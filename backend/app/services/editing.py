"""Clip editing helpers: re-slicing words after a trim, applying caption text edits."""

from __future__ import annotations

from typing import Any

# "none" renders the clip without captions
CAPTION_STYLES = ("bold", "karaoke", "minimal", "beast", "none")
# auto: follow the speaker, split screen when two people sit side by side
# podcast_split: always two panels (left person top, right person bottom), captions on the seam
# single: one full-screen speaker crop, never split
# centered_title: whole 16:9 frame in the middle on a blurred background, clip title above
# blur_fit: whole 16:9 frame in the middle on a blurred background, no title
LAYOUTS = ("auto", "podcast_split", "single", "centered_title", "blur_fit")
# Length range Gemini aims for when finding clips, as (min, max) seconds.
# "auto" means the worker's own default (20-59 s, see worker config).
CLIP_LENGTHS: dict[str, tuple[float, float] | None] = {"auto": None, "1m": (15.0, 60.0), "2m": (30.0, 120.0)}
# How many clips a user may ask for; None (not set) lets Gemini decide (5-10).
TARGET_CLIPS_RANGE = (1, 10)
MIN_CLIP_SECONDS = 3.0
MAX_CLIP_SECONDS = 180.0


def _key(w: dict[str, Any]) -> tuple[float, float]:
    return (round(float(w["start"]), 3), round(float(w["end"]), 3))


def words_in_range(transcript: dict[str, Any] | None, start: float, end: float) -> list[dict[str, Any]]:
    """Transcript words whose midpoint lies inside [start, end]."""
    out = []
    for seg in (transcript or {}).get("segments", []):
        for w in seg.get("words", []):
            mid = (float(w["start"]) + float(w["end"])) / 2
            if start <= mid <= end:
                out.append({k: v for k, v in w.items() if k in ("word", "start", "end", "speaker")})
    return out


def retime_words(
    transcript: dict[str, Any] | None,
    current_words: list[dict[str, Any]],
    start: float,
    end: float,
) -> list[dict[str, Any]]:
    """Words for a new clip range, keeping the user's caption edits for words that are still inside."""
    edits = {_key(w): w.get("word", "") for w in current_words}
    words = words_in_range(transcript, start, end)
    for w in words:
        if _key(w) in edits:
            w["word"] = edits[_key(w)]
    return words


def apply_word_texts(current_words: list[dict[str, Any]], texts: list[str]) -> list[dict[str, Any]]:
    """Replace caption text word-for-word; timings are untouched. An empty string hides a word."""
    if len(texts) != len(current_words):
        raise ValueError(f"Expected {len(current_words)} words, got {len(texts)}")
    return [{**w, "word": " ".join(t.split())[:60]} for w, t in zip(current_words, texts)]
