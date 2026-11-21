from __future__ import annotations

import json
import re

from pydantic import ValidationError

from clipforge_worker.highlights.schemas import HighlightCandidate

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class HighlightParseError(ValueError):
    """The model's output wasn't usable. The selector retries once on this."""


def parse_highlight_response(raw: str, *, video_duration: float | None = None) -> list[HighlightCandidate]:
    """Validate Gemini's JSON. Individual bad clips are dropped; if none survive, raise.

    Accepts {"clips": [...]} or a bare list, optionally wrapped in a ```json fence.
    """
    if raw is None or not str(raw).strip():
        raise HighlightParseError("empty response")
    text = str(raw).strip()
    if m := _FENCE_RE.match(text):
        text = m.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HighlightParseError(f"response is not valid JSON ({exc.msg} at char {exc.pos})") from exc

    if isinstance(data, list):
        data = {"clips": data}
    if not isinstance(data, dict) or not isinstance(data.get("clips"), list):
        raise HighlightParseError('expected an object with a "clips" array')

    valid: list[HighlightCandidate] = []
    problems: list[str] = []
    for i, item in enumerate(data["clips"]):
        try:
            clip = HighlightCandidate.model_validate(item)
        except ValidationError as exc:
            first = exc.errors()[0]
            loc = ".".join(str(p) for p in first.get("loc", ()))
            problems.append(f"clip {i}: {loc or 'value'} {first.get('msg')}")
            continue
        if video_duration is not None:
            if clip.start >= video_duration:
                problems.append(f"clip {i}: starts after the video ends")
                continue
            if clip.end > video_duration:
                clip.end = video_duration
        valid.append(clip)

    if not valid:
        detail = "; ".join(problems[:3]) if problems else "the clips array was empty"
        raise HighlightParseError(f"no valid clips ({detail})")
    return valid
