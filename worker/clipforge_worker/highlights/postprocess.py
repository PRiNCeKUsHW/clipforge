"""Deterministic clean-up of LLM-proposed clips: snap to sentence boundaries, drop overlaps."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, TypeVar

from clipforge_worker.transcript import Word

# A word ends a sentence if it ends in . ! ? or … (optionally followed by closing quotes/brackets).
_SENTENCE_END_RE = re.compile(r"[.!?…।][\"'”’)\]]*$")


@dataclass(frozen=True)
class SnapConfig:
    min_duration: float = 20.0
    max_duration: float = 90.0
    # Clips shorter than this after snapping are discarded
    hard_min_duration: float = 10.0
    # How far (s) to look for a sentence start around the proposed start
    start_window: float = 4.0
    # A silence at least this long also counts as a sentence boundary
    pause_gap: float = 0.8
    # Small padding so cuts don't clip the first/last syllable (never reaches into neighbouring words)
    pad_start: float = 0.15
    pad_end: float = 0.3


def is_sentence_end(word: Word, next_word: Word | None, pause_gap: float) -> bool:
    if next_word is None:
        return True
    if _SENTENCE_END_RE.search(word.word.strip()):
        return True
    return next_word.start - word.end >= pause_gap


def sentence_boundaries(words: Sequence[Word], pause_gap: float = 0.8) -> tuple[list[int], list[int]]:
    """Return (indices of sentence-starting words, indices of sentence-ending words)."""
    if not words:
        return [], []
    starts, ends = [0], []
    for i, w in enumerate(words):
        nxt = words[i + 1] if i + 1 < len(words) else None
        if is_sentence_end(w, nxt, pause_gap):
            ends.append(i)
            if nxt is not None:
                starts.append(i + 1)
    return starts, ends


def _nearest(indices: Sequence[int], key: Sequence[float], target: float) -> int | None:
    best, best_d = None, float("inf")
    for i in indices:
        d = abs(key[i] - target)
        if d < best_d:
            best, best_d = i, d
    return best


def snap_clip(
    start: float,
    end: float,
    words: Sequence[Word],
    cfg: SnapConfig = SnapConfig(),
    media_duration: float | None = None,
) -> tuple[float, float] | None:
    """Move [start, end] so the clip begins at a sentence start and ends at a sentence end,
    keeping the duration within [min_duration, max_duration] when possible.

    Returns None if no acceptable clip (>= hard_min_duration) can be formed.
    `words` must be sorted by start time.
    """
    limit = media_duration if media_duration is not None else float("inf")
    if not words:
        s, e = max(0.0, start), min(end, limit)
        return (s, e) if e - s >= cfg.hard_min_duration else None

    word_starts = [w.start for w in words]
    word_ends = [w.end for w in words]
    sent_starts, sent_ends = sentence_boundaries(words, cfg.pause_gap)

    # --- start: nearest sentence start within the window, else the nearest word start
    near_starts = [i for i in sent_starts if abs(word_starts[i] - start) <= cfg.start_window]
    si = _nearest(near_starts, word_starts, start)
    if si is None:
        si = _nearest(range(len(words)), word_starts, start)
    assert si is not None
    s = word_starts[si]

    # --- end: the sentence end closest to the proposed end that keeps the duration in range.
    later_ends = [i for i in sent_ends if i >= si]
    in_range = [i for i in later_ends if cfg.min_duration <= word_ends[i] - s <= cfg.max_duration]
    ei = _nearest(in_range, word_ends, end)
    if ei is None:
        # No sentence end fits: accept a shorter (but not too short) sentence-complete clip...
        short_ok = [i for i in later_ends if cfg.hard_min_duration <= word_ends[i] - s <= cfg.max_duration]
        ei = _nearest(short_ok, word_ends, end)
    if ei is None:
        # ...or, as a last resort, cut on the nearest word boundary within max_duration.
        any_ok = [i for i in range(si, len(words)) if 0 < word_ends[i] - s <= cfg.max_duration]
        ei = _nearest(any_ok, word_ends, min(end, s + cfg.max_duration))
    if ei is None:
        return None
    e = word_ends[ei]
    if e - s < cfg.hard_min_duration:
        return None

    # --- padding, without bleeding into the neighbouring words
    prev_end = word_ends[si - 1] if si > 0 else 0.0
    next_start = word_starts[ei + 1] if ei + 1 < len(words) else limit
    s = max(0.0, prev_end, s - cfg.pad_start)
    e = min(limit, next_start, e + cfg.pad_end, s + cfg.max_duration)  # padding never exceeds the cap
    return round(s, 3), round(e, 3)


class _Scored(Protocol):
    start: float
    end: float
    virality_score: int


T = TypeVar("T", bound=_Scored)


def overlap_seconds(a: _Scored, b: _Scored) -> float:
    return max(0.0, min(a.end, b.end) - max(a.start, b.start))


def remove_overlaps(clips: Sequence[T], tolerance: float = 0.5) -> list[T]:
    """Greedy: walk clips from highest to lowest score and keep a clip only if it overlaps
    every already-kept clip by at most `tolerance` seconds. Result is sorted by score (desc)."""
    kept: list[T] = []
    for clip in sorted(clips, key=lambda c: (-c.virality_score, c.start)):
        if all(overlap_seconds(clip, k) <= tolerance for k in kept):
            kept.append(clip)
    return kept
