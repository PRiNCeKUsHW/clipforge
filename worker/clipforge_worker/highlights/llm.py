"""LLM client interface + the Gemini implementation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from clipforge_worker.errors import PipelineError, TransientError
from clipforge_worker.highlights.parse import HighlightParseError
from clipforge_worker.highlights.schemas import GEMINI_RESPONSE_SCHEMA

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FrameImage:
    timestamp: float
    jpeg: bytes


class LLMClient(Protocol):
    def generate_json(self, prompt: str, *, images: list[FrameImage] | None = None) -> str:
        """Return the raw JSON text the model produced."""
        ...


class GeminiClient:
    def __init__(self, api_key: str, model: str, temperature: float = 0.4) -> None:
        if not api_key:
            raise PipelineError(
                "GEMINI_API_KEY is not set. Add it to your .env file (free key: https://aistudio.google.com/apikey) "
                "and restart the worker."
            )
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self.model = model
        self.temperature = temperature

    def generate_json(self, prompt: str, *, images: list[FrameImage] | None = None) -> str:
        from google.genai import errors, types

        contents: list = [prompt]
        for frame in images or []:
            contents.append(f"Frame at {frame.timestamp:.1f}s:")
            contents.append(types.Part.from_bytes(data=frame.jpeg, mime_type="image/jpeg"))

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GEMINI_RESPONSE_SCHEMA,
            temperature=self.temperature,
        )
        try:
            response = self._client.models.generate_content(model=self.model, contents=contents, config=config)
        except errors.APIError as exc:
            code = getattr(exc, "code", None)
            message = getattr(exc, "message", None) or str(exc)
            if code in (408, 429, 500, 502, 503, 504):
                raise TransientError(f"Gemini temporarily unavailable ({code}): {message}") from exc
            if code in (401, 403):
                raise PipelineError(f"Gemini rejected the API key ({code}). Check GEMINI_API_KEY.") from exc
            if code == 404:
                raise PipelineError(f"Gemini model '{self.model}' was not found. Check GEMINI_MODEL.") from exc
            raise PipelineError(f"Gemini request failed ({code}): {message}") from exc

        text = getattr(response, "text", None)
        if not text:
            reason = None
            try:
                reason = response.candidates[0].finish_reason  # type: ignore[index]
            except Exception:
                pass
            raise HighlightParseError(f"Gemini returned no content (finish reason: {reason})")
        return text
