"""Plan the 9:16 crop for a clip. Output is a small JSON "crop path" the Remotion renderer applies.

crop_path = {
  "layout": "single" | "split" | "fit",
  "source": {"w": 1920, "h": 1080},
  "crop_w": 0.316,                       # crop width as a fraction of source width
  "keyframes": [{"t": 0.0, "x": 0.42}],  # single: crop centre x over time (seconds from clip start)
  "panels": [[...], [...]],              # split: keyframes for the top and bottom panel
  "speaker_follow": true
}
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from clipforge_worker.reframe.tracking import (
    SpeakerTimeline,
    build_tracks,
    choose_targets,
    compute_activity,
    drop_noise,
    map_speakers,
)
from clipforge_worker.reframe.types import Sample, Track

OUT_ASPECT = 9 / 16  # 1080x1920
PANEL_ASPECT = 9 / 8  # each half of a split screen is 1080x960


@dataclass(frozen=True)
class ReframeOptions:
    smoothing: float = 0.35  # EMA factor per sample (higher = follows faster)
    deadzone: float = 0.05  # ignore target moves smaller than this (fraction of source width)
    hold_seconds: float = 1.0  # keep framing a face this long after it disappears
    split_screen: str = "auto"  # auto | true | false | force (always split, e.g. the podcast layout)
    split_min_presence: float = 0.6


def smooth_path(
    times: Sequence[float],
    centers: Sequence[float | None],
    target_ids: Sequence[int | None],
    crop_w: float,
    opts: ReframeOptions = ReframeOptions(),
) -> list[dict[str, float]]:
    """EMA + dead-zone camera that hard-cuts when the framed person changes and is far away."""
    lo, hi = crop_w / 2, 1 - crop_w / 2
    clamp = lambda v: min(max(v, lo), hi)  # noqa: E731
    first = next((c for c in centers if c is not None), 0.5)
    cam = clamp(first)
    last_seen = times[0] if times else 0.0
    prev_id = next((i for i in target_ids if i is not None), None)
    out: list[dict[str, float]] = []
    for t, c, tid in zip(times, centers, target_ids):
        if c is None:
            target = cam if t - last_seen <= opts.hold_seconds else 0.5
        else:
            target, last_seen = c, t
        target = clamp(target)
        if tid is not None and prev_id is not None and tid != prev_id and abs(target - cam) > crop_w / 2:
            # Speaker change to someone off-frame: cut, don't pan. The duplicate keyframe just
            # before t keeps the renderer from interpolating a whip-pan.
            out.append({"t": round(max(0.0, t - 0.01), 3), "x": round(cam, 4)})
            cam = target
        elif abs(target - cam) > opts.deadzone:
            cam = clamp(cam + opts.smoothing * (target - cam))
        if tid is not None:
            prev_id = tid
        out.append({"t": round(t, 3), "x": round(cam, 4)})
    return simplify(out)


def simplify(keyframes: list[dict[str, float]], eps: float = 0.002) -> list[dict[str, float]]:
    """Drop keyframes in the middle of a run of (near) identical positions."""
    if len(keyframes) <= 2:
        return keyframes
    out = [keyframes[0]]
    for i in range(1, len(keyframes) - 1):
        prev, cur, nxt = out[-1], keyframes[i], keyframes[i + 1]
        if abs(cur["x"] - prev["x"]) <= eps and abs(nxt["x"] - cur["x"]) <= eps:
            continue
        out.append(cur)
    out.append(keyframes[-1])
    return out


def _centers_for(track: Track, n: int) -> list[float | None]:
    return [track.boxes[i].cx if i in track.boxes else None for i in range(n)]


def _split_pair(tracks: Sequence[Track], n: int, crop_w: float, opts: ReframeOptions) -> tuple[Track, Track] | None:
    """Two people on screen most of the time, too far apart to fit in one 9:16 crop."""
    if opts.split_screen == "false" or len(tracks) < 2:
        return None
    top2 = sorted(tracks, key=lambda t: -len(t.boxes))[:2]
    together = len(set(top2[0].boxes) & set(top2[1].boxes)) / n
    apart = abs(top2[0].mean_cx() - top2[1].mean_cx()) > crop_w * 0.9
    if opts.split_screen in ("true", "force") and (apart or opts.split_screen == "force"):
        return tuple(sorted(top2, key=lambda t: t.mean_cx()))  # type: ignore[return-value]
    if together >= opts.split_min_presence and apart:
        return tuple(sorted(top2, key=lambda t: t.mean_cx()))  # type: ignore[return-value]
    return None


def _static_split(source: dict[str, int], panel_w: float) -> dict[str, Any]:
    lo, hi = panel_w / 2, 1 - panel_w / 2
    left, right = max(lo, 0.25), min(hi, 0.75)
    return {
        "layout": "split",
        "source": source,
        "crop_w": round(panel_w, 4),
        "panels": [[{"t": 0.0, "x": round(left, 4)}], [{"t": 0.0, "x": round(right, 4)}]],
    }


def plan_crop(
    samples: Sequence[Sample],
    src_w: int,
    src_h: int,
    words: Sequence[dict[str, Any]] = (),
    opts: ReframeOptions = ReframeOptions(),
) -> dict[str, Any]:
    source = {"w": src_w, "h": src_h}
    if src_w <= 0 or src_h <= 0 or src_w / src_h <= 0.75:
        # Already (near) vertical: scale to fill, nothing to track.
        return {"layout": "fit", "source": source}

    crop_w = min(1.0, (src_h * OUT_ASPECT) / src_w)
    panel_w = (src_h * PANEL_ASPECT) / src_w
    n = len(samples)
    if n == 0:
        if opts.split_screen == "force" and panel_w < 1:
            return _static_split(source, panel_w)
        return {"layout": "single", "source": source, "crop_w": crop_w, "keyframes": [{"t": 0.0, "x": 0.5}]}

    tracks = drop_noise(build_tracks(samples), n)
    compute_activity(tracks)
    times = [s.t for s in samples]

    pair = _split_pair(tracks, n, crop_w, opts) if panel_w < 1 else None
    if pair is None and opts.split_screen == "force" and panel_w < 1:
        # Podcast layout requested but fewer than two people were found: left half on top, right half below.
        return _static_split(source, panel_w)
    if pair:
        panels = [
            smooth_path(times, _centers_for(t, n), [t.id if i in t.boxes else None for i in range(n)], panel_w, opts)
            for t in pair
        ]
        return {"layout": "split", "source": source, "crop_w": round(panel_w, 4), "panels": panels}

    timeline = SpeakerTimeline(words)
    mapping = map_speakers(tracks, samples, timeline) if timeline else {}
    targets = choose_targets(tracks, samples, timeline, mapping)
    by_id = {t.id: t for t in tracks}
    centers = [by_id[tid].boxes[i].cx if tid is not None else None for i, tid in enumerate(targets)]
    return {
        "layout": "single",
        "source": source,
        "crop_w": round(crop_w, 4),
        "keyframes": smooth_path(times, centers, targets, crop_w, opts),
        "speaker_follow": bool(mapping),
    }
