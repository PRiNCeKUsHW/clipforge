"""Optional WhisperX post-processing: tighter word alignment (wav2vec2) and speaker diarization (pyannote).

Both are opt-in (ALIGN_WORDS / DIARIZE) and need the worker built with INSTALL_WHISPERX=true.
If WhisperX isn't installed we log a warning and keep the faster-whisper transcript as-is.
"""

from __future__ import annotations

import logging
from typing import Any

from clipforge_worker.transcript import Segment, Transcript, Word

log = logging.getLogger(__name__)


def fill_missing_word_times(words: list[dict[str, Any]], seg_start: float, seg_end: float) -> list[dict[str, Any]]:
    """WhisperX can't align some tokens (numbers, symbols) and leaves them without start/end.
    Give them times interpolated between their aligned neighbours."""
    out = [dict(w) for w in words]
    n = len(out)
    i = 0
    while i < n:
        if out[i].get("start") is not None and out[i].get("end") is not None:
            i += 1
            continue
        j = i
        while j < n and (out[j].get("start") is None or out[j].get("end") is None):
            j += 1
        left = out[i - 1]["end"] if i > 0 else seg_start
        right = out[j]["start"] if j < n else seg_end
        if right < left:
            right = left
        step = (right - left) / (j - i)
        for k in range(i, j):
            out[k]["start"] = round(left + step * (k - i), 3)
            out[k]["end"] = round(left + step * (k - i + 1), 3)
        i = j
    return out


def _to_whisperx(transcript: Transcript) -> dict[str, Any]:
    return {
        "language": transcript.language,
        "segments": [
            {
                "start": s.start,
                "end": s.end,
                "text": s.text,
                "words": [{"word": w.word, "start": w.start, "end": w.end, "score": w.probability} for w in s.words],
            }
            for s in transcript.segments
        ],
    }


def _from_whisperx(result: dict[str, Any], transcript: Transcript) -> Transcript:
    segments: list[Segment] = []
    for seg in result.get("segments", []):
        start, end = float(seg.get("start", 0.0)), float(seg.get("end", 0.0))
        raw_words = fill_missing_word_times(seg.get("words", []), start, end)
        words = [
            Word(
                word=str(w.get("word", "")).strip(),
                start=float(w["start"]),
                end=float(w["end"]),
                probability=w.get("score"),
                speaker=w.get("speaker"),
            )
            for w in raw_words
            if str(w.get("word", "")).strip()
        ]
        segments.append(
            Segment(start=start, end=end, text=str(seg.get("text", "")).strip(), speaker=seg.get("speaker"), words=words)
        )
    return Transcript(language=transcript.language, duration=transcript.duration, segments=segments)


def refine_transcript(
    transcript: Transcript,
    audio_path: str,
    *,
    device: str,
    align_words: bool,
    diarize: bool,
    hf_token: str = "",
    model_dir: str | None = None,
) -> Transcript:
    if not (align_words or diarize):
        return transcript
    try:
        import whisperx  # type: ignore[import-not-found]
    except ImportError:
        log.warning(
            "ALIGN_WORDS/DIARIZE requested but WhisperX isn't installed. "
            "Rebuild the worker with INSTALL_WHISPERX=true. Continuing without it."
        )
        return transcript

    audio = whisperx.load_audio(audio_path)
    result = _to_whisperx(transcript)

    if align_words and transcript.language:
        try:
            model_a, metadata = whisperx.load_align_model(
                language_code=transcript.language, device=device, model_dir=model_dir
            )
            result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
        except Exception:  # e.g. no alignment model for this language
            log.exception("WhisperX alignment failed; keeping faster-whisper word timings")
            result = _to_whisperx(transcript)

    if diarize:
        if not hf_token:
            log.warning("DIARIZE=true but HF_TOKEN is empty; skipping speaker diarization")
        else:
            try:
                try:
                    from whisperx.diarize import DiarizationPipeline  # type: ignore[import-not-found]
                except ImportError:
                    DiarizationPipeline = whisperx.DiarizationPipeline  # noqa: N806
                try:
                    pipeline = DiarizationPipeline(use_auth_token=hf_token, device=device)
                except TypeError:  # newer WhisperX renamed the argument
                    pipeline = DiarizationPipeline(token=hf_token, device=device)
                diarization = pipeline(audio)
                result = whisperx.assign_word_speakers(diarization, result)
            except Exception:
                log.exception(
                    "Speaker diarization failed (did you accept the pyannote model terms on Hugging Face?). "
                    "Continuing without speaker labels."
                )

    return _from_whisperx(result, transcript)
