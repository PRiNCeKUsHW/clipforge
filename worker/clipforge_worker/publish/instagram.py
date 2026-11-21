"""Instagram Reels publishing via the Meta Graph API (Business/Creator accounts linked to a Page).

Flow: create a REELS media container from a *public* video URL -> poll until Instagram has
fetched and processed it -> publish the container.
"""

from __future__ import annotations

import time
from urllib.parse import urlparse

import httpx

from clipforge_worker.errors import PipelineError, TransientError

GRAPH = "https://graph.facebook.com"


def _check(r: httpx.Response, what: str) -> dict:
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code < 400 and "error" not in data:
        return data
    err = data.get("error", {}) if isinstance(data, dict) else {}
    msg = err.get("error_user_msg") or err.get("message") or r.text[:300]
    if r.status_code in (429, 500, 502, 503) or err.get("is_transient"):
        raise TransientError(f"{what}: Instagram temporarily unavailable: {msg}")
    if err.get("code") == 190:
        raise PipelineError("Instagram access expired or was revoked. Reconnect the account on Connected accounts.")
    raise PipelineError(f"{what} failed: {msg}")


def ensure_public_url(url: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1") or host.endswith(".local") or host in ("s3", "minio"):
        raise PipelineError(
            "Instagram downloads the video itself, so it needs a public URL, and "
            f"'{host}' isn't reachable from the internet. Use Cloudflare R2 (see docs/DEPLOYMENT.md) or set "
            "PUBLIC_MEDIA_BASE_URL to a public address for your storage."
        )


def publish_reel(
    http: httpx.Client,
    access_token: str,
    ig_user_id: str,
    video_url: str,
    caption: str,
    *,
    graph_version: str = "v21.0",
    poll_interval: float = 5.0,
    timeout: float = 900.0,
) -> tuple[str, str | None]:
    """Returns (media id, permalink)."""
    ensure_public_url(video_url)
    base = f"{GRAPH}/{graph_version}"
    container = _check(
        http.post(
            f"{base}/{ig_user_id}/media",
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption[:2200],
                "share_to_feed": "true",
                "access_token": access_token,
            },
        ),
        "Creating the Instagram upload",
    )["id"]

    deadline = time.monotonic() + timeout
    while True:
        st = _check(
            http.get(f"{base}/{container}", params={"fields": "status_code,status", "access_token": access_token}),
            "Checking Instagram processing",
        )
        code = st.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise PipelineError(f"Instagram couldn't process the video: {st.get('status') or code}")
        if time.monotonic() > deadline:
            raise PipelineError("Instagram took too long to process the video.")
        time.sleep(poll_interval)

    media_id = _check(
        http.post(f"{base}/{ig_user_id}/media_publish", data={"creation_id": container, "access_token": access_token}),
        "Publishing the reel",
    )["id"]
    permalink = None
    try:
        permalink = _check(
            http.get(f"{base}/{media_id}", params={"fields": "permalink", "access_token": access_token}), "Permalink"
        ).get("permalink")
    except PipelineError:
        pass
    return media_id, permalink
