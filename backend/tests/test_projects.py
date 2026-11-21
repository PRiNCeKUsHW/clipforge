import json
import uuid

import pytest

from app.core.db import SessionLocal
from app.models import Clip, ClipStatus, ProjectStatus, VideoProject
from tests.conftest import register_and_login

YT = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


async def test_create_youtube_project_enqueues_pipeline(client, auth, enqueued):
    r = await client.post(
        "/api/projects", headers=auth, json={"source_type": "youtube", "source_url": YT, "instruction": "  funny bits  "}
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert body["progress"] == 0
    assert body["instruction"] == "funny bits"
    assert enqueued == [uuid.UUID(body["id"])]


@pytest.mark.parametrize("url", ["https://vimeo.com/123", "not a url", "https://youtube.com/watch?v=short"])
async def test_invalid_youtube_link_rejected(client, auth, url):
    r = await client.post("/api/projects", headers=auth, json={"source_type": "youtube", "source_url": url})
    assert r.status_code == 422
    assert "valid YouTube" in r.text


async def test_upload_flow(client, auth, s3, enqueued):
    r = await client.post(
        "/api/uploads/presign", headers=auth, json={"filename": "My Talk (final).mp4", "content_type": "video/mp4", "size": 1234}
    )
    assert r.status_code == 200, r.text
    presign = r.json()
    key = presign["storage_key"]
    assert key.startswith("uploads/") and key.endswith("/My-Talk-final.mp4")
    assert "X-Amz-Signature" in presign["upload_url"]

    # not uploaded yet
    r = await client.post("/api/projects", headers=auth, json={"source_type": "upload", "storage_key": key})
    assert r.status_code == 400

    s3.client.put_object(Bucket=s3.bucket, Key=key, Body=b"fake video")  # what the browser's PUT does
    r = await client.post("/api/projects", headers=auth, json={"source_type": "upload", "storage_key": key})
    assert r.status_code == 201, r.text
    assert r.json()["title"] == "My-Talk-final"
    assert len(enqueued) == 1


@pytest.mark.parametrize(
    "payload,status",
    [
        ({"filename": "evil.exe", "content_type": "video/mp4", "size": 10}, 400),
        ({"filename": "a.mp4", "content_type": "application/pdf", "size": 10}, 400),
        ({"filename": "a.mp4", "content_type": "video/mp4", "size": 10**13}, 413),
    ],
)
async def test_presign_validation(client, auth, payload, status):
    assert (await client.post("/api/uploads/presign", headers=auth, json=payload)).status_code == status


async def test_cannot_use_someone_elses_upload(client, auth, s3):
    key = f"uploads/{uuid.uuid4()}/x/video.mp4"
    s3.client.put_object(Bucket=s3.bucket, Key=key, Body=b"x")
    r = await client.post("/api/projects", headers=auth, json={"source_type": "upload", "storage_key": key})
    assert r.status_code == 400


async def test_projects_are_private(client, auth):
    r = await client.post("/api/projects", headers=auth, json={"source_type": "youtube", "source_url": YT})
    pid = r.json()["id"]
    other = await register_and_login(client, "mallory@example.com")
    assert (await client.get(f"/api/projects/{pid}", headers=other)).status_code == 404
    assert (await client.get(f"/api/projects/{pid}/clips", headers=other)).status_code == 404
    assert (await client.get("/api/projects", headers=other)).json() == []
    assert len((await client.get("/api/projects", headers=auth)).json()) == 1


async def _make_project_with_clips(client, auth, status=ProjectStatus.ready) -> uuid.UUID:
    r = await client.post("/api/projects", headers=auth, json={"source_type": "youtube", "source_url": YT})
    pid = uuid.UUID(r.json()["id"])
    async with SessionLocal() as s:
        p = await s.get(VideoProject, pid)
        p.status = status
        for score, start in [(55, 100.0), (92, 10.0), (71, 50.0)]:
            s.add(
                Clip(
                    project_id=pid, start=start, end=start + 30, hook_title=f"Clip {score}", virality_score=score,
                    score_breakdown={"hook": score, "payoff": 1, "emotion": 2, "standalone": 3}, reason="r",
                    transcript_words=[{"word": "Hello", "start": start, "end": start + 0.4}, {"word": "world.", "start": start + 0.5, "end": start + 0.9}],
                    status=ClipStatus.ready, output_key=f"clips/{pid}/{score}.mp4", thumbnail_key=f"clips/{pid}/{score}.jpg",
                )
            )  # fmt: skip
        await s.commit()
    return pid


async def test_clips_sorted_by_score_with_urls(client, auth):
    pid = await _make_project_with_clips(client, auth)
    r = await client.get(f"/api/projects/{pid}/clips", headers=auth)
    assert r.status_code == 200
    clips = r.json()
    assert [c["virality_score"] for c in clips] == [92, 71, 55]
    assert clips[0]["transcript_text"] == "Hello world."
    assert clips[0]["duration"] == 30
    assert "X-Amz-Signature" in clips[0]["video_url"]
    assert clips[0]["thumbnail_url"]
    assert (await client.get(f"/api/projects/{pid}", headers=auth)).json()["clip_count"] == 3


async def test_clip_detail_and_download(client, auth):
    pid = await _make_project_with_clips(client, auth)
    clip = (await client.get(f"/api/projects/{pid}/clips", headers=auth)).json()[0]
    detail = (await client.get(f"/api/clips/{clip['id']}", headers=auth)).json()
    assert len(detail["transcript_words"]) == 2
    dl = (await client.get(f"/api/clips/{clip['id']}/download", headers=auth)).json()
    assert dl["filename"] == "Clip-92.mp4"
    assert "attachment" in dl["url"]
    other = await register_and_login(client, "eve@example.com")
    assert (await client.get(f"/api/clips/{clip['id']}/download", headers=other)).status_code == 404


async def test_retry_only_failed_projects(client, auth, enqueued):
    pid = await _make_project_with_clips(client, auth, status=ProjectStatus.ready)
    assert (await client.post(f"/api/projects/{pid}/retry", headers=auth)).status_code == 409
    async with SessionLocal() as s:
        p = await s.get(VideoProject, pid)
        p.status, p.error = ProjectStatus.failed, "boom"
        await s.commit()
    r = await client.post(f"/api/projects/{pid}/retry", headers=auth)
    assert r.status_code == 200
    assert r.json()["status"] == "queued" and r.json()["error"] is None
    assert enqueued[-1] == pid


async def test_stalled_project_can_be_retried(client, auth, enqueued):
    from sqlalchemy import text

    r = await client.post("/api/projects", headers=auth, json={"source_type": "youtube", "source_url": YT})
    pid = r.json()["id"]
    async with SessionLocal() as s:
        await s.execute(text("UPDATE video_projects SET status='transcribing', progress=15 WHERE id=:id"), {"id": pid})
        await s.commit()
    # recently active: not stalled, not retryable
    body = (await client.get(f"/api/projects/{pid}", headers=auth)).json()
    assert body["stalled"] is False
    assert (await client.post(f"/api/projects/{pid}/retry", headers=auth)).status_code == 409

    async with SessionLocal() as s:
        await s.execute(
            text("UPDATE video_projects SET updated_at = now() - interval '30 minutes' WHERE id=:id"), {"id": pid}
        )
        await s.commit()
    body = (await client.get(f"/api/projects/{pid}", headers=auth)).json()
    assert body["stalled"] is True
    r = await client.post(f"/api/projects/{pid}/retry", headers=auth)
    assert r.status_code == 200
    assert r.json()["status"] == "queued" and r.json()["stalled"] is False
    assert enqueued[-1] == uuid.UUID(pid)


async def test_delete_project(client, auth, enqueued_tasks):
    pid = await _make_project_with_clips(client, auth)
    assert (await client.delete(f"/api/projects/{pid}", headers=auth)).status_code == 204
    assert (await client.get(f"/api/projects/{pid}", headers=auth)).status_code == 404
    # the worker is asked to remove the project's scratch files
    assert [str(p) for p in enqueued_tasks["cleanup"]] == [str(pid)]


# ---------------------------------------------------------------- SSE
class FakePubSub:
    def __init__(self, messages):
        self.messages = list(messages)
        self.channels = []

    async def subscribe(self, channel):
        self.channels.append(channel)

    async def get_message(self, ignore_subscribe_messages=True, timeout=0):
        if self.messages:
            return {"type": "message", "data": self.messages.pop(0).encode()}
        return None

    async def aclose(self):
        pass


class FakeRedis:
    messages: list[str] = []

    @classmethod
    def from_url(cls, url):
        return cls()

    def pubsub(self):
        return FakePubSub(FakeRedis.messages)

    async def aclose(self):
        pass


def parse_sse(body: str) -> list[dict]:
    return [json.loads(line[5:].strip()) for line in body.splitlines() if line.startswith("data:")]


async def test_sse_terminal_project_sends_snapshot_and_closes(client, auth, monkeypatch):
    monkeypatch.setattr("app.api.projects.Redis", FakeRedis)
    FakeRedis.messages = []
    pid = await _make_project_with_clips(client, auth, status=ProjectStatus.ready)
    r = await client.get(f"/api/projects/{pid}/events", headers=auth)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    assert len(events) == 1 and events[0]["status"] == "ready"


async def test_sse_streams_worker_updates_until_done(client, auth, monkeypatch):
    monkeypatch.setattr("app.api.projects.Redis", FakeRedis)
    r = await client.post("/api/projects", headers=auth, json={"source_type": "youtube", "source_url": YT})
    pid = r.json()["id"]
    FakeRedis.messages = [
        json.dumps({"id": pid, "status": "transcribing", "progress": 40, "status_message": "Transcribing 40%", "error": None}),
        json.dumps({"id": pid, "status": "failed", "progress": 40, "status_message": None, "error": "No speech"}),
        json.dumps({"id": pid, "status": "ready", "progress": 100}),  # never sent: stream closed at 'failed'
    ]
    r = await client.get(f"/api/projects/{pid}/events", headers=auth)
    statuses = [e["status"] for e in parse_sse(r.text)]
    assert statuses == ["queued", "transcribing", "failed"]
    assert parse_sse(r.text)[-1]["error"] == "No speech"


async def test_project_layout_and_caption_defaults(client, auth):
    r = await client.post(
        "/api/projects", headers=auth,
        json={"source_type": "youtube", "source_url": YT, "layout": "centered_title", "caption_style": "none"},
    )  # fmt: skip
    assert r.status_code == 201
    assert (r.json()["layout"], r.json()["caption_style"]) == ("centered_title", "none")
    default = (await client.post("/api/projects", headers=auth, json={"source_type": "youtube", "source_url": YT})).json()
    assert (default["layout"], default["caption_style"]) == ("auto", "bold")
    bad = await client.post("/api/projects", headers=auth, json={"source_type": "youtube", "source_url": YT, "layout": "x"})
    assert bad.status_code == 422


async def test_project_clip_length_and_count(client, auth):
    r = await client.post(
        "/api/projects", headers=auth,
        json={"source_type": "youtube", "source_url": YT, "clip_length": "2m", "target_clips": 3},
    )  # fmt: skip
    assert r.status_code == 201
    assert (r.json()["clip_length"], r.json()["target_clips"]) == ("2m", 3)
    default = (await client.post("/api/projects", headers=auth, json={"source_type": "youtube", "source_url": YT})).json()
    assert (default["clip_length"], default["target_clips"]) == ("auto", None)
    for bad in ({"clip_length": "5m"}, {"target_clips": 0}, {"target_clips": 11}):
        r = await client.post("/api/projects", headers=auth, json={"source_type": "youtube", "source_url": YT, **bad})
        assert r.status_code == 422, bad
