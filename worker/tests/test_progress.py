import json
import uuid

from app.models import ProjectStatus
from clipforge_worker.progress import ProgressReporter, stage_progress


def test_stage_progress_maps_into_overall_range():
    assert stage_progress("downloading", 0) == (ProjectStatus.downloading, 0)
    assert stage_progress("transcribing", 0.5) == (ProjectStatus.transcribing, 45)
    assert stage_progress("transcribing", 1.0) == (ProjectStatus.transcribing, 70)
    assert stage_progress("rendering", 2.0) == (ProjectStatus.rendering, 99)  # clamped
    assert stage_progress("finding_highlights", -1) == (ProjectStatus.finding_highlights, 70)


def test_reporter_writes_publishes_and_throttles():
    writes, pubs = [], []
    pid = uuid.uuid4()
    rep = ProgressReporter(pid, write=lambda p, f: writes.append(f), publish=lambda ch, m: pubs.append((ch, m)), min_interval=60)
    rep.stage("transcribing", 0.1, "Transcribing 10%")
    rep.stage("transcribing", 0.2, "Transcribing 20%")  # throttled (same status, < min_interval)
    rep.stage("transcribing", 0.3, "Transcribing 30%", force=True)
    rep.stage("finding_highlights", 0.0, "Asking Gemini")  # status change always goes through
    assert [w["progress"] for w in writes] == [25, 35, 70]
    channel, msg = pubs[-1]
    assert channel.endswith(str(pid))
    assert json.loads(msg) == {
        "id": str(pid), "status": "finding_highlights", "progress": 70, "status_message": "Asking Gemini", "error": None,
    }  # fmt: skip


def test_reporter_survives_publish_failure():
    def boom(*_):
        raise ConnectionError("redis down")

    writes = []
    ProgressReporter(uuid.uuid4(), write=lambda p, f: writes.append(f), publish=boom).stage("downloading", 0.5)
    assert len(writes) == 1
