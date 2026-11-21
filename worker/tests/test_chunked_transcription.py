"""Long audio is transcribed in chunks split at quiet points, with timestamps shifted back."""

import wave
from types import SimpleNamespace

import numpy as np
import pytest

from clipforge_worker.transcription.device import WhisperConfig
from clipforge_worker.transcription.faster_whisper_transcriber import (
    SAMPLE_RATE,
    FasterWhisperTranscriber,
    quietest_split,
)

CPU = WhisperConfig(model="tiny", device="cpu", compute_type="int8")


def write_wav(path, seconds: float, silences: list[tuple[float, float]]):
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    audio = 0.5 * np.sin(2 * np.pi * 220 * t)
    for a, b in silences:
        audio[int(a * SAMPLE_RATE) : int(b * SAMPLE_RATE)] = 0.0
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes((audio * 32767).astype(np.int16).tobytes())


class ChunkRecordingModel:
    """Returns one segment per chunk spanning the whole chunk (times relative to the chunk)."""

    def __init__(self, detected="hi"):
        self.calls = []
        self.detected = detected

    def transcribe(self, audio, **kwargs):
        assert isinstance(audio, np.ndarray) and audio.dtype == np.float32
        i = len(self.calls)
        length = len(audio) / SAMPLE_RATE
        self.calls.append({"length": length, **kwargs})
        word = SimpleNamespace(word=f" chunk{i}.", start=0.5, end=1.0, probability=0.9)
        seg = SimpleNamespace(start=0.0, end=length, text=f" chunk{i}.", words=[word])
        return iter([seg]), SimpleNamespace(duration=length, language=self.detected)


def test_quietest_split_finds_the_silence():
    samples = np.full(SAMPLE_RATE, 10_000, dtype=np.int16)
    samples[8000:8640] = 0
    assert 8000 <= quietest_split(samples) <= 8640


def test_long_audio_is_chunked_at_silences_with_absolute_times(tmp_path):
    path = tmp_path / "a.wav"
    write_wav(path, 25.0, silences=[(9.0, 9.4), (18.6, 19.0)])
    model = ChunkRecordingModel()
    tr = FasterWhisperTranscriber(CPU, model=model, chunk_seconds=10, split_search_seconds=3)
    progress: list[float] = []
    result = tr.transcribe(str(path), on_progress=progress.append)

    assert len(model.calls) == 3
    starts = [s.start for s in result.segments]
    # chunk 2 starts inside the first silence, chunk 3 inside the second
    assert starts[0] == 0.0
    assert 9.0 <= starts[1] <= 9.4
    assert 18.6 <= starts[2] <= 19.0
    # chunks cover the whole file without gaps
    assert result.segments[-1].end == pytest.approx(25.0, abs=0.01)
    for a, b in zip(result.segments, result.segments[1:]):
        assert a.end == pytest.approx(b.start, abs=0.001)
    # word timestamps are shifted to absolute time
    assert result.segments[1].words[0].start == pytest.approx(starts[1] + 0.5, abs=0.001)
    assert result.duration == pytest.approx(25.0)
    # progress is monotonic and ends at 1.0
    assert progress == sorted(progress) and progress[-1] == 1.0


def test_language_is_locked_after_first_chunk_and_context_is_carried(tmp_path):
    path = tmp_path / "a.wav"
    write_wav(path, 25.0, silences=[])
    model = ChunkRecordingModel(detected="hi")
    result = FasterWhisperTranscriber(CPU, model=model, chunk_seconds=10, split_search_seconds=0).transcribe(str(path))
    assert [c["language"] for c in model.calls] == [None, "hi", "hi"]
    assert model.calls[0]["initial_prompt"] is None
    assert model.calls[1]["initial_prompt"] == "chunk0."
    assert result.language == "hi"


def test_configured_language_is_used_for_every_chunk(tmp_path):
    path = tmp_path / "a.wav"
    write_wav(path, 25.0, silences=[])
    model = ChunkRecordingModel(detected="hi")
    FasterWhisperTranscriber(CPU, model=model, language="en", chunk_seconds=10, split_search_seconds=0).transcribe(str(path))
    assert {c["language"] for c in model.calls} == {"en"}


def test_short_audio_is_a_single_chunk(tmp_path):
    path = tmp_path / "a.wav"
    write_wav(path, 5.0, silences=[])
    model = ChunkRecordingModel()
    result = FasterWhisperTranscriber(CPU, model=model, chunk_seconds=600).transcribe(str(path))
    assert len(model.calls) == 1
    assert model.calls[0]["length"] == pytest.approx(5.0)
    assert result.segments[0].start == 0.0


def test_non_pcm_input_falls_back_to_whole_file(tmp_path):
    path = tmp_path / "a.wav"
    with wave.open(str(path), "wb") as w:  # stereo: not what our pipeline produces
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(np.zeros(SAMPLE_RATE * 2, dtype=np.int16).tobytes())

    class PathModel:
        def transcribe(self, audio, **kwargs):
            assert isinstance(audio, str)
            return iter([]), SimpleNamespace(duration=1.0, language="en")

    assert FasterWhisperTranscriber(CPU, model=PathModel()).transcribe(str(path)).segments == []
