import numpy as np
import pytest

from clipforge_worker.reframe.planner import ReframeOptions, plan_crop, simplify, smooth_path
from clipforge_worker.reframe.tracking import (
    SpeakerTimeline,
    build_tracks,
    choose_targets,
    compute_activity,
    map_speakers,
)
from clipforge_worker.reframe.types import FaceBox, Sample

W, H = 1920, 1080
CROP_W = (H * 9 / 16) / W  # 0.316


def face(cx, cy=0.4, size=0.12, patch_value=None):
    patch = None if patch_value is None else np.full((16, 24), patch_value, dtype=np.uint8)
    return FaceBox(cx=cx, cy=cy, w=size, h=size * 1.7, patch=patch)


def samples_at(fps, seconds, faces_fn):
    return [Sample(t=round(i / fps, 3), faces=faces_fn(i)) for i in range(int(seconds * fps))]


# ---------------------------------------------------------------- tracking
def test_tracks_follow_people_across_samples():
    samples = samples_at(3, 5, lambda i: [face(0.2 + i * 0.005), face(0.8 - i * 0.005)])
    tracks = build_tracks(samples)
    assert len(tracks) == 2
    assert all(len(t.boxes) == len(samples) for t in tracks)


def test_track_survives_short_dropout_but_new_person_far_away_gets_new_track():
    def faces(i):
        if 3 <= i <= 5:
            return []  # missed detections
        return [face(0.5)] if i < 10 else [face(0.5), face(0.9)]

    tracks = build_tracks(samples_at(3, 5, faces))
    assert len(tracks) == 2
    assert len(tracks[0].boxes) == 12  # 15 samples minus 3 missed


def test_activity_and_speaker_mapping():
    # left person's mouth moves in the first half, right person's in the second half
    def faces(i):
        moving_left = i < 15
        return [
            face(0.2, patch_value=(i % 2) * 120 if moving_left else 10),
            face(0.8, patch_value=10 if moving_left else (i % 2) * 120),
        ]

    samples = samples_at(3, 10, faces)
    tracks = build_tracks(samples)
    compute_activity(tracks)
    words = [
        {"word": "hi", "start": 0.0, "end": 4.9, "speaker": "SPEAKER_00"},
        {"word": "yo", "start": 5.0, "end": 10.0, "speaker": "SPEAKER_01"},
    ]
    mapping = map_speakers(tracks, samples, SpeakerTimeline(words))
    left = min(tracks, key=lambda t: t.mean_cx())
    right = max(tracks, key=lambda t: t.mean_cx())
    assert mapping == {"SPEAKER_00": left.id, "SPEAKER_01": right.id}

    targets = choose_targets(tracks, samples, SpeakerTimeline(words), mapping)
    assert targets[2] == left.id and targets[-2] == right.id


def test_without_diarization_the_largest_face_wins_and_choice_is_sticky():
    def faces(i):
        # small face on the left, bigger face on the right; sizes wobble slightly
        return [face(0.2, size=0.10 + 0.002 * (i % 2)), face(0.8, size=0.13)]

    samples = samples_at(3, 3, faces)
    tracks = build_tracks(samples)
    targets = choose_targets(tracks, samples)
    right = max(tracks, key=lambda t: t.mean_cx())
    assert set(targets) == {right.id}


# ---------------------------------------------------------------- smoothing
def test_deadzone_ignores_jitter():
    times = [i / 3 for i in range(30)]
    centers = [0.5 + (0.01 if i % 2 else -0.01) for i in range(30)]
    kf = smooth_path(times, centers, [0] * 30, CROP_W, ReframeOptions(deadzone=0.05))
    assert {k["x"] for k in kf} == {round(0.49, 4)}
    assert len(kf) == 2  # simplified to first/last


def test_follows_a_moving_face_smoothly_and_stays_in_frame():
    times = [i / 3 for i in range(60)]
    centers = [min(0.95, 0.3 + i * 0.02) for i in range(60)]
    kf = smooth_path(times, centers, [0] * 60, CROP_W)
    xs = [k["x"] for k in kf]
    assert xs == sorted(xs), "camera should move monotonically with the face"
    assert max(xs) <= 1 - CROP_W / 2 + 1e-9 and min(xs) >= CROP_W / 2 - 1e-9
    steps = [b - a for a, b in zip(xs, xs[1:])]
    assert max(steps) < 0.1, "no jumps when the same person moves"


def test_cuts_instead_of_panning_when_speaker_changes_far_away():
    times = [i / 3 for i in range(12)]
    centers = [0.2] * 6 + [0.8] * 6
    ids = [0] * 6 + [1] * 6
    kf = smooth_path(times, centers, ids, CROP_W)
    # right before the cut the camera is still left; at the cut time it's right
    cut = next(k for k in kf if k["t"] == pytest.approx(2.0))
    before = [k for k in kf if k["t"] < 2.0][-1]
    assert before["t"] == pytest.approx(1.99) and before["x"] == pytest.approx(0.2, abs=0.01)
    assert cut["x"] == pytest.approx(0.8, abs=0.01)


def test_missing_face_holds_then_returns_to_center():
    times = [i / 3 for i in range(15)]
    centers = [0.2, 0.2, 0.2] + [None] * 12
    kf = smooth_path(times, centers, [0, 0, 0] + [None] * 12, CROP_W, ReframeOptions(hold_seconds=1.0))
    xs = {round(k["t"], 2): k["x"] for k in kf}
    assert xs[0.0] == pytest.approx(0.2, abs=0.01)
    assert kf[-1]["x"] > 0.4  # drifting back toward centre


def test_simplify_keeps_endpoints():
    kf = [{"t": float(i), "x": 0.5} for i in range(10)]
    assert simplify(kf) == [kf[0], kf[-1]]


# ---------------------------------------------------------------- planner
def test_no_faces_is_center_crop():
    plan = plan_crop(samples_at(3, 5, lambda i: []), W, H)
    assert plan["layout"] == "single"
    assert {k["x"] for k in plan["keyframes"]} == {0.5}
    assert plan["crop_w"] == pytest.approx(CROP_W, abs=1e-3)


def test_vertical_source_fits():
    assert plan_crop([], 1080, 1920)["layout"] == "fit"


def test_two_people_side_by_side_become_split_screen():
    plan = plan_crop(samples_at(3, 10, lambda i: [face(0.22), face(0.78)]), W, H)
    assert plan["layout"] == "split"
    top, bottom = plan["panels"]
    assert top[0]["x"] < 0.5 < bottom[0]["x"]


def test_split_screen_can_be_disabled():
    plan = plan_crop(samples_at(3, 10, lambda i: [face(0.22), face(0.78)]), W, H, opts=ReframeOptions(split_screen="false"))
    assert plan["layout"] == "single"


def test_single_speaker_is_followed():
    plan = plan_crop(samples_at(3, 10, lambda i: [face(0.7)]), W, H)
    assert plan["layout"] == "single"
    assert plan["keyframes"][-1]["x"] == pytest.approx(0.7, abs=0.02)
    assert plan["speaker_follow"] is False


def test_podcast_layout_forces_split_with_two_people_close_together():
    # two faces close enough to share one 9:16 crop: auto keeps one panel, force still splits
    faces = lambda i: [face(0.42), face(0.58)]  # noqa: E731
    assert plan_crop(samples_at(3, 10, faces), W, H)["layout"] == "single"
    plan = plan_crop(samples_at(3, 10, faces), W, H, opts=ReframeOptions(split_screen="force"))
    assert plan["layout"] == "split"
    top, bottom = plan["panels"]
    assert top[0]["x"] < bottom[0]["x"]


def test_podcast_layout_with_one_or_no_person_uses_static_halves():
    for faces in (lambda i: [face(0.5)], lambda i: []):
        plan = plan_crop(samples_at(3, 5, faces), W, H, opts=ReframeOptions(split_screen="force"))
        assert plan["layout"] == "split"
        xs = [p[0]["x"] for p in plan["panels"]]
        assert xs[0] < 0.5 < xs[1]
        for x in xs:  # panels stay inside the frame
            assert plan["crop_w"] / 2 <= x <= 1 - plan["crop_w"] / 2
