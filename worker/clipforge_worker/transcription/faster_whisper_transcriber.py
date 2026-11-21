"""Local transcription with faster-whisper (Whisper re-implemented on CTranslate2: ~4x faster, less RAM).

Long audio is transcribed in chunks: faster-whisper decodes the whole input and computes the
spectrogram for all of it at once, which for a 2-3 hour video needs several GB of RAM. Chunking
keeps memory flat regardless of video length. Chunks are cut at the quietest point near each
boundary so words aren't split, and timestamps are shifted back to absolute video time.
"""

from __future__ import annotations

import logging
import wave
from typing import Any

import numpy as np

from clipforge_worker.transcript import Segment, Transcript, Word
from clipforge_worker.transcription.base import ProgressCallback
from clipforge_worker.transcription.device import WhisperConfig

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000


def quietest_split(samples: np.ndarray, frame: int = 320) -> int:
    """Index (within `samples`) of the centre of the lowest-energy 20 ms frame."""
    usable = len(samples) - len(samples) % frame
    if usable < frame:
        return len(samples)
    rms = np.sqrt(np.mean(samples[:usable].reshape(-1, frame).astype(np.float64) ** 2, axis=1))
    return int(np.argmin(rms)) * frame + frame // 2


def plan_chunks(wav: wave.Wave_read, chunk_seconds: float, search_seconds: float) -> list[tuple[int, int]]:
    """[(start_sample, end_sample)] covering the file, each ending at a quiet point."""
    n = wav.getnframes()
    chunk = int(chunk_seconds * SAMPLE_RATE)
    search = int(search_seconds * SAMPLE_RATE)
    bounds: list[tuple[int, int]] = []
    pos = 0
    while pos < n:
        end = min(pos + chunk, n)
        if end < n and search > 0:
            lo = max(pos + chunk // 2, end - search)
            wav.setpos(lo)
            window = np.frombuffer(wav.readframes(end - lo), dtype=np.int16)
            end = lo + quietest_split(window)
        bounds.append((pos, end))
        pos = end
    return bounds


def _read_float(wav: wave.Wave_read, start: int, end: int) -> np.ndarray:
    wav.setpos(start)
    return np.frombuffer(wav.readframes(end - start), dtype=np.int16).astype(np.float32) / 32768.0


def _open_pcm16_mono(path: str) -> wave.Wave_read | None:
    """Our pipeline extracts 16 kHz mono 16-bit WAV; anything else falls back to whole-file mode."""
    try:
        wav = wave.open(path, "rb")
    except (OSError, EOFError, wave.Error):
        return None
    if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != SAMPLE_RATE:
        wav.close()
        return None
    return wav


class FasterWhisperTranscriber:
    def __init__(
        self,
        config: WhisperConfig,
        *,
        download_root: str | None = None,
        language: str | None = None,
        model: Any | None = None,  # injectable for tests
        chunk_seconds: float = 600,
        beam_size: int = 5,
        split_search_seconds: float = 8,
    ) -> None:
        self.config = config
        self.language = language or None
        self.chunk_seconds = chunk_seconds
        self.beam_size = beam_size
        self.split_search_seconds = split_search_seconds
        if model is None:
            from faster_whisper import WhisperModel

            log.info("Loading Whisper model %s on %s (%s)", config.model, config.device, config.compute_type)
            model = WhisperModel(
                config.model, device=config.device, compute_type=config.compute_type, download_root=download_root
            )
        self.model = model

    # ------------------------------------------------------------------ public
    def transcribe(self, audio_path: str, on_progress: ProgressCallback | None = None) -> Transcript:
        wav = _open_pcm16_mono(audio_path)
        if wav is None:
            return self._transcribe_whole(audio_path, on_progress)
        with wav:
            n = wav.getnframes()
            duration = n / SAMPLE_RATE
            bounds = plan_chunks(wav, self.chunk_seconds, self.split_search_seconds)
            if len(bounds) > 1:
                log.info("Transcribing %.0fs of audio in %d chunks", duration, len(bounds))

            language = self.language
            segments: list[Segment] = []
            for start, end in bounds:
                offset = start / SAMPLE_RATE
                # Carry the tail of the previous text as context so style/spelling stays consistent.
                prompt = " ".join(s.text for s in segments[-3:])[-200:] or None

                def chunk_progress(t: float, _start: int = start) -> None:
                    if on_progress and n:
                        on_progress(min((_start + t * SAMPLE_RATE) / n, 1.0))

                chunk_segments, detected = self._run(_read_float(wav, start, end), language, prompt, offset, chunk_progress)
                segments += chunk_segments
                # Lock the language after the first chunk so a bilingual video doesn't flip-flop.
                language = language or detected
        if on_progress:
            on_progress(1.0)
        return Transcript(language=language, duration=round(duration, 3), segments=segments)

    # ------------------------------------------------------------------ internals
    def _transcribe_whole(self, audio_path: str, on_progress: ProgressCallback | None) -> Transcript:
        segments_iter, info = self.model.transcribe(
            audio_path, language=self.language, word_timestamps=True, vad_filter=True, beam_size=self.beam_size
        )
        duration = float(getattr(info, "duration", 0.0) or 0.0)

        def progress(t: float) -> None:
            if on_progress and duration > 0:
                on_progress(min(t / duration, 1.0))

        segments = [self._convert(seg, 0.0) for seg in self._iterate(segments_iter, progress)]
        if on_progress:
            on_progress(1.0)
        return Transcript(language=getattr(info, "language", None), duration=duration, segments=segments)

    def _run(self, audio: np.ndarray, language: str | None, prompt: str | None, offset: float, progress):
        # segments is a lazy generator: decoding happens as we iterate, which is what lets us
        # report progress by processed audio time.
        segments_iter, info = self.model.transcribe(
            audio,
            language=language,
            initial_prompt=prompt,
            word_timestamps=True,
            vad_filter=True,  # skip silence (Silero VAD): faster and fewer hallucinations
            beam_size=self.beam_size,
        )
        segments = [self._convert(seg, offset) for seg in self._iterate(segments_iter, progress)]
        return segments, getattr(info, "language", None)

    @staticmethod
    def _iterate(segments_iter, progress):
        for seg in segments_iter:
            yield seg
            progress(float(seg.end))

    @staticmethod
    def _convert(seg: Any, offset: float) -> Segment:
        words = [
            Word(
                word=w.word.strip(),
                start=round(float(w.start) + offset, 3),
                end=round(float(w.end) + offset, 3),
                probability=round(float(w.probability), 3) if w.probability is not None else None,
            )
            for w in (seg.words or [])
            if w.word.strip()
        ]
        return Segment(
            start=round(float(seg.start) + offset, 3),
            end=round(float(seg.end) + offset, 3),
            text=seg.text.strip(),
            words=words,
        )
