from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# All coordinates are normalised to the source frame: 0..1 left->right, top->bottom.


@dataclass
class FaceBox:
    cx: float
    cy: float
    w: float
    h: float
    score: float = 1.0
    # small grayscale patch of the lower half of the face (mouth area), used to tell who's talking
    patch: Any = None

    @property
    def area(self) -> float:
        return self.w * self.h


@dataclass
class Sample:
    t: float  # seconds from the start of the clip
    faces: list[FaceBox] = field(default_factory=list)


@dataclass
class Track:
    """One person followed across samples."""

    id: int
    boxes: dict[int, FaceBox] = field(default_factory=dict)  # sample index -> box
    activity: dict[int, float] = field(default_factory=dict)  # sample index -> mouth movement 0..1

    def last_index(self) -> int:
        return max(self.boxes)

    def presence(self, n_samples: int) -> float:
        return len(self.boxes) / n_samples if n_samples else 0.0

    def mean_cx(self) -> float:
        return sum(b.cx for b in self.boxes.values()) / len(self.boxes)
