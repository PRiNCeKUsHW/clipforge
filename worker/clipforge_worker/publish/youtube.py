"""YouTube Shorts upload via the YouTube Data API v3 (resumable upload)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from clipforge_worker.errors import PipelineError, TransientError

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


def _raise_for(r: httpx.Response, what: str) -> None:
    if r.status_code < 400:
        return
    try:
        err = r.json().get("error", {})
        msg = err.get("message") if isinstance(err, dict) else str(err)
        reason = (err.get("errors") or [{}])[0].get("reason", "") if isinstance(err, dict) else ""
    except ValueError:
        msg, reason = r.text[:300], ""
    if r.status_code in (429, 500, 502, 503, 504):
        raise TransientError(f"{what}: YouTube temporarily unavailable ({r.status_code}) {msg}")
    if reason in ("quotaExceeded", "uploadLimitExceeded"):
        raise PipelineError("YouTube API quota exceeded for today. Try again tomorrow (quota resets at midnight PT).")
    if r.status_code == 401:
        raise PipelineError("YouTube access was revoked or expired. Reconnect the account on Connected accounts.")
    raise PipelineError(f"{what} failed ({r.status_code}): {msg}")


def refresh_access_token(
    http: httpx.Client, client_id: str, client_secret: str, refresh_token: str
) -> tuple[str, datetime]:
    if not (client_id and client_secret):
        raise PipelineError("GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are not configured on the worker.")
    r = http.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    _raise_for(r, "Refreshing the YouTube token")
    data = r.json()
    return data["access_token"], datetime.now(UTC) + timedelta(seconds=int(data.get("expires_in", 3600)) - 60)


def shorts_title(title: str) -> str:
    """YouTube titles max out at 100 chars; '#Shorts' helps classification."""
    title = " ".join(title.split()) or "Short"
    if "#shorts" not in title.lower():
        title = f"{title[:91].rstrip()} #Shorts"
    return title[:100]


def upload_video(
    http: httpx.Client,
    access_token: str,
    path: Path,
    *,
    title: str,
    description: str,
    tags: list[str],
    privacy_status: str = "private",
) -> str:
    """Resumable upload: create a session with the metadata, then PUT the bytes. Returns the video id."""
    size = path.stat().st_size
    metadata = {
        "snippet": {"title": shorts_title(title), "description": description[:5000], "tags": tags[:30], "categoryId": "22"},
        "status": {"privacyStatus": privacy_status, "selfDeclaredMadeForKids": False},
    }
    r = http.post(
        UPLOAD_URL,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(size),
        },
        json=metadata,
    )
    _raise_for(r, "Starting the YouTube upload")
    session_url = r.headers.get("Location")
    if not session_url:
        raise PipelineError("YouTube didn't return an upload session URL.")
    with path.open("rb") as f:
        r = http.put(
            session_url,
            content=f.read(),
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "video/mp4"},
            timeout=600,
        )
    _raise_for(r, "Uploading the video to YouTube")
    return r.json()["id"]
