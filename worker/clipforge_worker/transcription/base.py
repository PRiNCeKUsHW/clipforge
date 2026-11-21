from collections.abc import Callable
from typing import Protocol

from clipforge_worker.transcript import Transcript

# Called with the fraction (0..1) of audio processed so far.
ProgressCallback = Callable[[float], None]


class Transcriber(Protocol):
    """Anything that turns an audio file into a word-timestamped transcript.

    The pipeline only talks to this interface, so the engine (faster-whisper today)
    can be swapped or mocked in tests.
    """

    def transcribe(self, audio_path: str, on_progress: ProgressCallback | None = None) -> Transcript: ...
