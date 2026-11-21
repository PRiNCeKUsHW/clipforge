"""Highlight selection: transcript -> (chunk) -> Gemini -> validate (retry once) -> snap -> de-overlap -> top N."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from clipforge_worker.errors import PipelineError
from clipforge_worker.highlights.chunking import chunk_transcript
from clipforge_worker.highlights.llm import FrameImage, LLMClient
from clipforge_worker.highlights.parse import HighlightParseError, parse_highlight_response
from clipforge_worker.highlights.postprocess import SnapConfig, remove_overlaps, snap_clip
from clipforge_worker.highlights.prompt import build_prompt, format_transcript
from clipforge_worker.highlights.schemas import HighlightCandidate
from clipforge_worker.transcript import Transcript

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class HighlightOptions:
    min_seconds: float = 20
    max_seconds: float = 59
    min_clips: int = 5
    max_clips: int = 10
    chunk_threshold: float = 3600
    chunk_seconds: float = 1500
    chunk_overlap: float = 120


def request_highlights(
    llm: LLMClient,
    prompt: str,
    *,
    images: list[FrameImage] | None = None,
    video_duration: float | None = None,
) -> list[HighlightCandidate]:
    """Ask the model; if the output fails validation, retry once with the error appended."""
    raw = llm.generate_json(prompt, images=images)
    try:
        return parse_highlight_response(raw, video_duration=video_duration)
    except HighlightParseError as first:
        log.warning("Invalid highlight output, retrying once: %s", first)
        retry_prompt = (
            f"{prompt}\n\nIMPORTANT: your previous answer was rejected because {first}. "
            "Return ONLY valid JSON matching the schema, with end > start and scores between 0 and 100."
        )
        try:
            raw = llm.generate_json(retry_prompt, images=images)
            return parse_highlight_response(raw, video_duration=video_duration)
        except HighlightParseError as second:
            raise PipelineError(f"Gemini returned invalid highlight data twice ({second}). Please retry.") from second


def select_highlights(
    transcript: Transcript,
    llm: LLMClient,
    options: HighlightOptions = HighlightOptions(),
    *,
    instruction: str | None = None,
    frames: list[FrameImage] | None = None,
) -> list[HighlightCandidate]:
    duration = transcript.duration
    chunks = chunk_transcript(
        transcript.segments,
        duration,
        threshold=options.chunk_threshold,
        chunk_seconds=options.chunk_seconds,
        overlap_seconds=options.chunk_overlap,
    )
    multi = len(chunks) > 1
    candidates: list[HighlightCandidate] = []
    failures: list[str] = []

    # Visual-only videos may have no transcript at all; still let Gemini look at the frames.
    if not chunks and frames:
        chunks = chunk_transcript([], duration, threshold=float("inf"))

    for chunk in chunks:
        chunk_frames = [f for f in (frames or []) if chunk.start <= f.timestamp <= chunk.end] or None
        prompt = build_prompt(
            format_transcript(chunk.segments, transcript.has_speakers) or "(no speech detected)",
            min_seconds=options.min_seconds,
            max_seconds=options.max_seconds,
            # Each window proposes a few clips; merging keeps the best overall.
            min_clips=min(max(2, options.min_clips // 2), options.max_clips) if multi else options.min_clips,
            max_clips=options.max_clips,
            instruction=instruction,
            window=(chunk.start, chunk.end) if multi else None,
            has_speakers=transcript.has_speakers,
            has_frames=bool(chunk_frames),
        )
        try:
            candidates += request_highlights(llm, prompt, images=chunk_frames, video_duration=duration)
        except PipelineError as exc:
            if not multi:
                raise
            # One bad window shouldn't sink a 3-hour podcast; keep the rest.
            log.warning("Highlight chunk %s failed: %s", chunk.index, exc.user_message)
            failures.append(exc.user_message)

    if not candidates and failures:
        raise PipelineError(failures[0])

    words = transcript.all_words()
    snap_cfg = SnapConfig(min_duration=options.min_seconds, max_duration=options.max_seconds)
    snapped: list[HighlightCandidate] = []
    for c in candidates:
        bounds = snap_clip(c.start, c.end, words, snap_cfg, media_duration=duration)
        if bounds is None:
            log.info("Dropping clip %r: no valid boundaries near %.1f-%.1f", c.hook_title, c.start, c.end)
            continue
        snapped.append(c.model_copy(update={"start": bounds[0], "end": bounds[1]}))

    final = remove_overlaps(snapped)[: options.max_clips]
    if not final:
        raise PipelineError(
            "Gemini didn't find any clip-worthy moments in this video. "
            "Try a video with more talking, or relax your instruction."
        )
    return final
