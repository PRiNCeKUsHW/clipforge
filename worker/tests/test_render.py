import json
from pathlib import Path

import httpx
import pytest

from clipforge_worker.errors import PipelineError, TransientError
from clipforge_worker.render.client import RendererClient
from clipforge_worker.render.props import build_props, caption_words

WORDS = [
    {"word": "before", "start": 9.0, "end": 9.8},  # entirely before the clip
    {"word": "Hello", "start": 9.9, "end": 10.4},  # straddles the start
    {"word": "", "start": 10.5, "end": 10.8},  # deleted in the editor
    {"word": "world.", "start": 11.0, "end": 11.5, "speaker": "SPEAKER_00"},
    {"word": "tail", "start": 39.8, "end": 40.4},  # straddles the end
    {"word": "after", "start": 41.0, "end": 41.5},
]


def test_caption_words_are_relative_and_clamped():
    assert caption_words(WORDS, 10.0, 40.0) == [
        {"text": "Hello", "start": 0.0, "end": 0.4},
        {"text": "world.", "start": 1.0, "end": 1.5},
        {"text": "tail", "start": 29.8, "end": 30.0},
    ]


def test_build_props_defaults_unknown_style():
    crop = {"layout": "single", "source": {"w": 1920, "h": 1080}, "keyframes": [{"t": 0, "x": 0.5}]}
    props = build_props(clip_start=10, clip_end=40, transcript_words=WORDS, crop_path=crop, caption_style="nope", fps=30)
    assert props["style"] == "bold"
    assert props["durationInSeconds"] == 30
    assert props["crop"] is crop
    assert len(props["words"]) == 3


def make_client(handler):
    return RendererClient("http://renderer:3100", timeout_seconds=5, poll_interval=0, transport=httpx.MockTransport(handler))


def test_render_polls_until_done_and_reports_progress(tmp_path: Path):
    states = iter([{"status": "queued", "progress": 0}, {"status": "rendering", "progress": 0.5}, {"status": "done", "progress": 1}])
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            seen["body"] = json.loads(request.content)
            return httpx.Response(202, json={"id": "job1"})
        assert request.url.path == "/jobs/job1"
        return httpx.Response(200, json=next(states))

    progress: list[float] = []
    make_client(handler).render(tmp_path / "in.mp4", tmp_path / "out.mp4", {"style": "bold"}, on_progress=progress.append)
    assert progress == [0, 0.5, 1]
    assert seen["body"]["input"].endswith("in.mp4") and seen["body"]["props"] == {"style": "bold"}


def test_render_failure_is_readable(tmp_path: Path):
    def handler(request):
        if request.method == "POST":
            return httpx.Response(202, json={"id": "j"})
        return httpx.Response(200, json={"status": "failed", "progress": 0.1, "error": "boom"})

    with pytest.raises(PipelineError, match="Rendering failed: boom"):
        make_client(handler).render(tmp_path / "a", tmp_path / "b", {})


def test_unreachable_or_restarted_renderer_is_transient(tmp_path: Path):
    def down(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(TransientError):
        make_client(down).render(tmp_path / "a", tmp_path / "b", {})

    def forgot(request):
        if request.method == "POST":
            return httpx.Response(202, json={"id": "j"})
        return httpx.Response(404, json={"error": "unknown job"})

    with pytest.raises(TransientError, match="restarted"):
        make_client(forgot).render(tmp_path / "a", tmp_path / "b", {})


def test_bad_request_is_not_retried(tmp_path: Path):
    with pytest.raises(PipelineError, match="paths must be inside"):
        make_client(lambda r: httpx.Response(400, json={"error": "paths must be inside WORK_ROOT"})).render(
            tmp_path / "a", tmp_path / "b", {}
        )


def test_no_captions_style_is_kept():
    crop = {"layout": "single", "source": {"w": 1920, "h": 1080}, "keyframes": [{"t": 0, "x": 0.5}]}
    props = build_props(clip_start=10, clip_end=40, transcript_words=WORDS, crop_path=crop, caption_style="none")
    assert props["style"] == "none"


def test_layout_and_title_props_and_split_mode():
    from clipforge_worker.render.props import split_mode_for

    crop = {"layout": "single", "source": {"w": 1920, "h": 1080}, "keyframes": [{"t": 0, "x": 0.5}]}
    props = build_props(
        clip_start=10, clip_end=40, transcript_words=WORDS, crop_path=crop, caption_style="bold",
        layout="centered_title", title="Big news #Shorts",
    )  # fmt: skip
    assert props["layout"] == "centered_title" and props["title"] == "Big news #Shorts"
    assert build_props(clip_start=0, clip_end=1, transcript_words=[], crop_path=crop, caption_style="bold", layout="weird")["layout"] == "auto"
    assert split_mode_for("podcast_split", "auto") == "force"
    assert split_mode_for("single", "auto") == "false"
    assert split_mode_for("auto", "auto") == "auto"
