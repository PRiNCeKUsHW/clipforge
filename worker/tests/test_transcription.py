from types import SimpleNamespace

import pytest

from clipforge_worker.transcription import device
from clipforge_worker.transcription.device import resolve_whisper_config
from clipforge_worker.transcription.faster_whisper_transcriber import FasterWhisperTranscriber
from clipforge_worker.transcription.whisperx_refine import fill_missing_word_times


class FakeWhisperModel:
    """Mimics faster_whisper.WhisperModel.transcribe(): (lazy segment generator, info)."""

    def __init__(self):
        self.kwargs = None

    def transcribe(self, audio_path, **kwargs):
        self.kwargs = kwargs
        w = lambda word, s, e: SimpleNamespace(word=word, start=s, end=e, probability=0.9)  # noqa: E731
        segs = [
            SimpleNamespace(start=0.0, end=2.0, text=" Hello world.", words=[w(" Hello", 0.0, 0.5), w(" world.", 0.6, 1.9)]),
            SimpleNamespace(start=5.0, end=10.0, text=" Second line.", words=[w(" Second", 5.0, 5.5), w(" line.", 5.6, 10.0)]),
        ]
        return iter(segs), SimpleNamespace(duration=10.0, language="en")


def test_transcriber_maps_words_and_reports_progress():
    model = FakeWhisperModel()
    t = FasterWhisperTranscriber(resolve_whisper_config("cpu"), model=model)
    progress: list[float] = []
    result = t.transcribe("audio.wav", on_progress=progress.append)

    assert model.kwargs["word_timestamps"] is True
    assert model.kwargs["vad_filter"] is True
    assert result.language == "en"
    assert result.duration == 10.0
    assert [w.word for w in result.all_words()] == ["Hello", "world.", "Second", "line."]
    assert result.segments[0].text == "Hello world."
    # progress based on processed audio time: 2s/10s, then 10s/10s, then the final 1.0
    assert progress == [0.2, 1.0, 1.0]


def test_device_auto_uses_cpu_defaults_without_cuda(monkeypatch):
    monkeypatch.setattr(device, "cuda_available", lambda: False)
    cfg = resolve_whisper_config("auto", "auto", "auto")
    assert (cfg.device, cfg.model, cfg.compute_type) == ("cpu", "small", "int8")


def test_device_auto_uses_gpu_defaults_with_cuda(monkeypatch):
    monkeypatch.setattr(device, "cuda_available", lambda: True)
    cfg = resolve_whisper_config("auto", "auto", "auto")
    assert (cfg.device, cfg.model, cfg.compute_type) == ("cuda", "large-v3-turbo", "float16")


def test_forced_cuda_falls_back_when_missing(monkeypatch):
    monkeypatch.setattr(device, "cuda_available", lambda: False)
    assert resolve_whisper_config("cuda").device == "cpu"


def test_explicit_model_is_respected(monkeypatch):
    monkeypatch.setattr(device, "cuda_available", lambda: False)
    assert resolve_whisper_config("auto", "medium", "int8_float32").model == "medium"


@pytest.mark.parametrize(
    "words,expected",
    [
        (
            [{"word": "I", "start": 0.0, "end": 0.2}, {"word": "1999"}, {"word": "ok", "start": 1.0, "end": 1.2}],
            [(0.0, 0.2), (0.2, 1.0), (1.0, 1.2)],
        ),
        ([{"word": "42"}, {"word": "x", "start": 2.0, "end": 2.5}], [(1.0, 2.0), (2.0, 2.5)]),
        ([{"word": "a", "start": 1.0, "end": 1.5}, {"word": "7"}, {"word": "8"}], [(1.0, 1.5), (1.5, 2.25), (2.25, 3.0)]),
    ],
)
def test_fill_missing_word_times(words, expected):
    out = fill_missing_word_times(words, seg_start=1.0 if words[0].get("start") is None else 0.0, seg_end=3.0)
    assert [(w["start"], w["end"]) for w in out] == expected
