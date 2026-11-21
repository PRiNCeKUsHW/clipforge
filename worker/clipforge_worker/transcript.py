"""Transcript data model. Stored as JSON on VideoProject.transcript."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Word(BaseModel):
    word: str
    start: float
    end: float
    probability: float | None = None
    speaker: str | None = None


class Segment(BaseModel):
    start: float
    end: float
    text: str
    speaker: str | None = None
    words: list[Word] = Field(default_factory=list)


class Transcript(BaseModel):
    language: str | None = None
    duration: float
    segments: list[Segment] = Field(default_factory=list)

    def all_words(self) -> list[Word]:
        return [w for s in self.segments for w in s.words]

    @property
    def has_speakers(self) -> bool:
        return any(s.speaker for s in self.segments)

    def words_per_minute(self) -> float:
        if self.duration <= 0:
            return 0.0
        return len(self.all_words()) / (self.duration / 60)

    def words_between(self, start: float, end: float) -> list[Word]:
        """Words whose midpoint falls inside [start, end]."""
        return [w for w in self.all_words() if start <= (w.start + w.end) / 2 <= end]
