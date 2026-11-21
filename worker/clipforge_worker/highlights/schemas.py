from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field, field_validator, model_validator


def _round_number(v: Any) -> Any:
    # LLMs sometimes return 87.0 or "87" for integer scores; accept those, reject garbage.
    if isinstance(v, str):
        v = v.strip()
        try:
            v = float(v)
        except ValueError:
            return v
    if isinstance(v, float):
        return round(v)
    return v


Score = Annotated[int, BeforeValidator(_round_number), Field(ge=0, le=100)]


class ScoreBreakdown(BaseModel):
    hook: Score
    payoff: Score
    emotion: Score
    standalone: Score


class HighlightCandidate(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    hook_title: str = Field(min_length=1, max_length=200)
    virality_score: Score
    score_breakdown: ScoreBreakdown
    reason: str = Field(default="", max_length=2000)
    # Post copy for publishing (optional: older/partial outputs still validate)
    description: str = Field(default="", max_length=2000)
    hashtags: list[str] = Field(default_factory=list)

    @field_validator("hook_title", "reason", "description", mode="before")
    @classmethod
    def _strip(cls, v: Any) -> Any:
        return v.strip() if isinstance(v, str) else v

    @field_validator("hashtags", mode="before")
    @classmethod
    def _clean_tags(cls, v: Any) -> list[str]:
        if not isinstance(v, list):
            return []
        seen: list[str] = []
        for tag in v:
            if not isinstance(tag, str):
                continue
            t = "".join(ch for ch in tag.strip().lstrip("#") if ch.isalnum() or ch == "_")
            if t and t.lower() not in (s.lower() for s in seen):
                seen.append(t[:40])
        return seen[:8]

    @model_validator(mode="after")
    def _check_order(self) -> HighlightCandidate:
        if self.end <= self.start:
            raise ValueError(f"end ({self.end}) must be after start ({self.start})")
        return self

    @property
    def duration(self) -> float:
        return self.end - self.start


# JSON schema handed to Gemini's structured-output mode (OpenAPI-subset dialect Gemini accepts).
_SCORE = {"type": "INTEGER", "minimum": 0, "maximum": 100}
GEMINI_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "clips": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "start": {"type": "NUMBER", "description": "Clip start, seconds from video start"},
                    "end": {"type": "NUMBER", "description": "Clip end, seconds from video start"},
                    "hook_title": {"type": "STRING", "description": "Catchy title, max ~70 characters"},
                    "virality_score": _SCORE,
                    "score_breakdown": {
                        "type": "OBJECT",
                        "properties": {"hook": _SCORE, "payoff": _SCORE, "emotion": _SCORE, "standalone": _SCORE},
                        "required": ["hook", "payoff", "emotion", "standalone"],
                        "propertyOrdering": ["hook", "payoff", "emotion", "standalone"],
                    },
                    "reason": {"type": "STRING", "description": "One or two sentences on why this works"},
                    "description": {"type": "STRING", "description": "Short social post caption for the clip"},
                    "hashtags": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "description": "3-6 relevant hashtags without the # sign",
                    },
                },
                "required": ["start", "end", "hook_title", "virality_score", "score_breakdown", "reason", "description", "hashtags"],
                "propertyOrdering": [
                    "start", "end", "hook_title", "virality_score", "score_breakdown", "reason", "description", "hashtags",
                ],
            },
        }
    },
    "required": ["clips"],
}
