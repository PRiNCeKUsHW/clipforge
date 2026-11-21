"""Real ffmpeg on a tiny generated video. Skipped when ffmpeg isn't on PATH."""

import shutil

import pytest

from clipforge_worker.media import ffmpeg
from clipforge_worker.media.frames import frame_timestamps

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@pytest.fixture(scope="module")
def sample_video(tmp_path_factory):
    path = tmp_path_factory.mktemp("media") / "sample.mp4"
    ffmpeg.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", "testsrc=size=320x180:rate=25:duration=8",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=8",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path),
        ],
        "making sample",
    )  # fmt: skip
    return path


@needs_ffmpeg
def test_probe(sample_video):
    info = ffmpeg.probe(sample_video)
    assert info.has_video and info.has_audio
    assert info.duration == pytest.approx(8.0, abs=0.2)
    assert (info.width, info.height) == (320, 180)


@needs_ffmpeg
def test_extract_audio_is_16k_mono(sample_video, tmp_path):
    out = tmp_path / "a.wav"
    ffmpeg.extract_audio(sample_video, out)
    proc = ffmpeg.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(out)], "probe")
    import json

    stream = json.loads(proc.stdout)["streams"][0]
    assert stream["sample_rate"] == "16000"
    assert stream["channels"] == 1


@needs_ffmpeg
def test_cut_clip_and_thumbnail(sample_video, tmp_path):
    clip = tmp_path / "c.mp4"
    ffmpeg.cut_clip(sample_video, clip, 2.0, 5.0)
    assert ffmpeg.probe(clip).duration == pytest.approx(3.0, abs=0.15)
    thumb = tmp_path / "t.jpg"
    ffmpeg.extract_frame(clip, thumb, 1.0, width=160)
    assert thumb.stat().st_size > 0


@needs_ffmpeg
def test_errors_are_readable(tmp_path):
    from clipforge_worker.errors import PipelineError

    with pytest.raises(PipelineError, match="Reading the video file failed"):
        ffmpeg.probe(tmp_path / "missing.mp4")


def test_frame_timestamps():
    assert frame_timestamps(0, 10) == []
    ts = frame_timestamps(600, 40)
    assert len(ts) == 40 and ts == sorted(ts) and 0 < ts[0] and ts[-1] < 600
    assert len(frame_timestamps(25, 40)) == 2  # at most one every 10s


@needs_ffmpeg
def test_letterbox_bars_are_detected_and_removed(tmp_path):
    # 2.39:1 picture padded to 16:9 with black bars, like a film inside a YouTube upload
    src = tmp_path / "letterbox.mp4"
    ffmpeg.run(
        [
            "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x268:rate=25:duration=4",
            "-vf", "pad=640:360:0:46:black", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src),
        ],
        "making letterboxed sample",
    )  # fmt: skip
    box = ffmpeg.detect_letterbox(src, 0, 4, 640, 360)
    assert box is not None and box.w == 640 and 252 <= box.h <= 264 and 46 <= box.y <= 54
    out = tmp_path / "cut.mp4"
    ffmpeg.cut_clip(src, out, 0.5, 2.5, crop=box)
    assert ffmpeg.probe(out).height == box.h


@needs_ffmpeg
def test_no_bars_means_no_crop(sample_video):
    assert ffmpeg.detect_letterbox(sample_video, 0, 4, 320, 180) is None
