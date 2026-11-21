from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from clipforge_worker.transcript import Segment


@dataclass
class TranscriptChunk:
    index: int
    start: float
    end: float
    segments: list[Segment] = field(default_factory=list)


def chunk_transcript(
    segments: Sequence[Segment],
    total_duration: float,
    *,
    threshold: float = 3600,
    chunk_seconds: float = 1500,
    overlap_seconds: float = 120,
) -> list[TranscriptChunk]:
    """Split long transcripts into overlapping time windows.

    The overlap means a great moment that straddles a window edge is still fully visible
    in at least one window. Duplicates found in two windows are removed later by
    `remove_overlaps`. Short videos (<= threshold) come back as a single chunk.
    """
    if overlap_seconds >= chunk_seconds:
        raise ValueError("overlap_seconds must be smaller than chunk_seconds")
    if total_duration <= threshold:
        return [TranscriptChunk(0, 0.0, total_duration, list(segments))]

    step = chunk_seconds - overlap_seconds
    chunks: list[TranscriptChunk] = []
    start = 0.0
    while True:
        end = min(start + chunk_seconds, total_duration)
        segs = [s for s in segments if s.end > start and s.start < end]
        if segs:
            chunks.append(TranscriptChunk(len(chunks), start, end, segs))
        if end >= total_duration:
            break
        start += step
    return chunks
