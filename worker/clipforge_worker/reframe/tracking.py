"""Turn per-frame face detections into people (tracks), and decide whom the camera follows."""

from __future__ import annotations

import bisect
from collections.abc import Sequence
from typing import Any

import numpy as np

from clipforge_worker.reframe.types import Sample, Track


def build_tracks(samples: Sequence[Sample], max_jump: float = 0.12, max_gap: int = 6) -> list[Track]:
    """Greedy nearest-centre association. A face continues a track if its centre moved less than
    `max_jump` (fraction of frame width) since the track was last seen `max_gap` samples ago at most."""
    tracks: list[Track] = []
    for i, sample in enumerate(samples):
        candidates = [t for t in tracks if i - t.last_index() <= max_gap]
        pairs = []
        for fi, face in enumerate(sample.faces):
            for t in candidates:
                last = t.boxes[t.last_index()]
                d = ((face.cx - last.cx) ** 2 + (face.cy - last.cy) ** 2) ** 0.5
                if d <= max_jump:
                    pairs.append((d, fi, t.id))
        used_faces: set[int] = set()
        used_tracks: set[int] = set()
        by_id = {t.id: t for t in tracks}
        for _, fi, tid in sorted(pairs):
            if fi in used_faces or tid in used_tracks:
                continue
            by_id[tid].boxes[i] = sample.faces[fi]
            used_faces.add(fi)
            used_tracks.add(tid)
        for fi, face in enumerate(sample.faces):
            if fi not in used_faces:
                tracks.append(Track(id=len(tracks), boxes={i: face}))
    return tracks


def drop_noise(tracks: list[Track], n_samples: int, min_presence: float = 0.12) -> list[Track]:
    """Remove flickering false detections (faces seen in only a few samples)."""
    keep = max(2, int(n_samples * min_presence))
    return [t for t in tracks if len(t.boxes) >= min(keep, n_samples)]


def compute_activity(tracks: Sequence[Track]) -> None:
    """Mouth-area change between consecutive sightings of the same person ~ "is talking"."""
    for t in tracks:
        idx = sorted(t.boxes)
        for a, b in zip(idx, idx[1:]):
            pa, pb = t.boxes[a].patch, t.boxes[b].patch
            if pa is None or pb is None or np.shape(pa) != np.shape(pb):
                continue
            t.activity[b] = float(np.mean(np.abs(np.asarray(pa, dtype=np.float32) - np.asarray(pb, dtype=np.float32))) / 255.0)


class SpeakerTimeline:
    """Who is speaking at time t (seconds from clip start), from diarized words."""

    def __init__(self, words: Sequence[dict[str, Any]], tolerance: float = 0.25) -> None:
        spoken = sorted((w for w in words if w.get("speaker")), key=lambda w: w["start"])
        self.starts = [float(w["start"]) for w in spoken]
        self.words = spoken
        self.tolerance = tolerance

    def __bool__(self) -> bool:
        return bool(self.words)

    def speaker_at(self, t: float) -> str | None:
        i = bisect.bisect_right(self.starts, t + self.tolerance) - 1
        if i < 0:
            return None
        w = self.words[i]
        return w["speaker"] if float(w["end"]) + self.tolerance >= t else None


def map_speakers(tracks: Sequence[Track], samples: Sequence[Sample], timeline: SpeakerTimeline) -> dict[str, int]:
    """Match diarization speakers to on-screen people: a speaker belongs to the face whose mouth
    moves most while that speaker is talking. One-to-one, greedy by score."""
    scores: dict[tuple[str, int], float] = {}
    for i, sample in enumerate(samples):
        speaker = timeline.speaker_at(sample.t)
        if speaker is None:
            continue
        present = [t for t in tracks if i in t.activity]
        total = sum(t.activity[i] for t in present) + 1e-6
        for t in present:
            scores[(speaker, t.id)] = scores.get((speaker, t.id), 0.0) + t.activity[i] / total
    mapping: dict[str, int] = {}
    taken: set[int] = set()
    for (speaker, tid), _ in sorted(scores.items(), key=lambda kv: -kv[1]):
        if speaker in mapping or tid in taken:
            continue
        mapping[speaker] = tid
        taken.add(tid)
    return mapping


def choose_targets(
    tracks: Sequence[Track],
    samples: Sequence[Sample],
    timeline: SpeakerTimeline | None = None,
    mapping: dict[str, int] | None = None,
    stickiness: float = 0.7,
) -> list[int | None]:
    """Track id to frame on at each sample: the current speaker's face when known, otherwise the
    largest / most active face. Sticks with the previous choice unless another face is clearly better."""
    targets: list[int | None] = []
    prev: int | None = None
    for i, sample in enumerate(samples):
        present = [t for t in tracks if i in t.boxes]
        if not present:
            targets.append(None)
            continue
        chosen: int | None = None
        if timeline and mapping:
            speaker = timeline.speaker_at(sample.t)
            tid = mapping.get(speaker) if speaker else None
            if tid is not None and any(t.id == tid for t in present):
                chosen = tid
        if chosen is None:
            def score(t: Track) -> float:
                return t.boxes[i].area * (1.0 + 4.0 * t.activity.get(i, 0.0))

            best = max(present, key=score)
            prev_track = next((t for t in present if t.id == prev), None)
            chosen = prev_track.id if prev_track and score(prev_track) >= stickiness * score(best) else best.id
        targets.append(chosen)
        prev = chosen
    return targets
