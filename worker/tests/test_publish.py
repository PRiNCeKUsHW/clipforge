import json
from pathlib import Path

import httpx
import pytest

from clipforge_worker.errors import PipelineError, TransientError
from clipforge_worker.publish import instagram, youtube


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------- YouTube
def test_shorts_title():
    assert youtube.shorts_title("My clip") == "My clip #Shorts"
    assert youtube.shorts_title("Already #shorts") == "Already #shorts"
    long = youtube.shorts_title("x" * 200)
    assert len(long) <= 100 and long.endswith("#Shorts")


def test_resumable_upload(tmp_path: Path):
    video = tmp_path / "c.mp4"
    video.write_bytes(b"0123456789")
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.method == "POST":
            assert request.url.params["uploadType"] == "resumable"
            assert request.headers["X-Upload-Content-Length"] == "10"
            meta = json.loads(request.content)
            assert meta["status"]["privacyStatus"] == "unlisted"
            assert meta["snippet"]["title"].endswith("#Shorts")
            return httpx.Response(200, headers={"Location": "https://upload.example/session/1"})
        assert str(request.url) == "https://upload.example/session/1"
        assert request.content == b"0123456789"
        return httpx.Response(201, json={"id": "vid123"})

    vid = youtube.upload_video(
        client(handler), "tok", video, title="Hook", description="d", tags=["a"], privacy_status="unlisted"
    )
    assert vid == "vid123" and len(calls) == 2


def test_quota_and_auth_errors_are_readable(tmp_path: Path):
    video = tmp_path / "c.mp4"
    video.write_bytes(b"x")
    quota = {"error": {"message": "quota", "errors": [{"reason": "quotaExceeded"}]}}
    with pytest.raises(PipelineError, match="quota exceeded"):
        youtube.upload_video(client(lambda r: httpx.Response(403, json=quota)), "t", video, title="a", description="", tags=[])
    with pytest.raises(PipelineError, match="Reconnect"):
        youtube.upload_video(client(lambda r: httpx.Response(401, json={"error": {"message": "x"}})), "t", video, title="a", description="", tags=[])
    with pytest.raises(TransientError):
        youtube.upload_video(client(lambda r: httpx.Response(503, json={})), "t", video, title="a", description="", tags=[])


def test_refresh_token():
    def handler(request):
        assert b"grant_type=refresh_token" in request.content
        return httpx.Response(200, json={"access_token": "new", "expires_in": 3600})

    token, _expiry = youtube.refresh_access_token(client(handler), "id", "secret", "refresh")
    assert token == "new"
    with pytest.raises(PipelineError, match="GOOGLE_CLIENT_ID"):
        youtube.refresh_access_token(client(handler), "", "", "refresh")


# ---------------------------------------------------------------- Instagram
def test_reel_publish_flow():
    statuses = iter(["IN_PROGRESS", "FINISHED"])

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path.endswith("/ig1/media"):
            body = dict(x.split("=", 1) for x in request.content.decode().split("&"))
            assert body["media_type"] == "REELS"
            return httpx.Response(200, json={"id": "container1"})
        if request.method == "GET" and path.endswith("/container1"):
            return httpx.Response(200, json={"status_code": next(statuses)})
        if request.method == "POST" and path.endswith("/ig1/media_publish"):
            return httpx.Response(200, json={"id": "media9"})
        if request.method == "GET" and path.endswith("/media9"):
            return httpx.Response(200, json={"permalink": "https://instagram.com/reel/abc"})
        raise AssertionError(f"unexpected {request.method} {path}")

    media_id, link = instagram.publish_reel(
        client(handler), "tok", "ig1", "https://cdn.example.com/c.mp4", "caption", poll_interval=0
    )
    assert (media_id, link) == ("media9", "https://instagram.com/reel/abc")


def test_reel_processing_error_and_expired_token():
    def failing(request):
        if request.method == "POST":
            return httpx.Response(200, json={"id": "c"})
        return httpx.Response(200, json={"status_code": "ERROR", "status": "Unsupported codec"})

    with pytest.raises(PipelineError, match="Unsupported codec"):
        instagram.publish_reel(client(failing), "t", "ig", "https://cdn.example.com/a.mp4", "", poll_interval=0)

    expired = lambda r: httpx.Response(400, json={"error": {"message": "Session expired", "code": 190}})  # noqa: E731
    with pytest.raises(PipelineError, match="Reconnect"):
        instagram.publish_reel(client(expired), "t", "ig", "https://cdn.example.com/a.mp4", "", poll_interval=0)


@pytest.mark.parametrize("url", ["http://localhost:9000/x.mp4", "http://127.0.0.1/x.mp4", "http://s3:8333/x.mp4"])
def test_local_urls_are_rejected_before_calling_instagram(url):
    with pytest.raises(PipelineError, match="public URL"):
        instagram.publish_reel(client(lambda r: httpx.Response(500)), "t", "ig", url, "")
