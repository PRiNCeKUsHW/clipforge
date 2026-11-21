import re
from urllib.parse import parse_qs, urlparse

_YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def youtube_video_id(url: str) -> str | None:
    """Return the 11-char video id for watch / youtu.be / shorts / live / embed links, else None."""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    host = (parsed.hostname or "").lower()
    path_parts = [p for p in parsed.path.split("/") if p]

    candidate: str | None = None
    if host == "youtu.be":
        candidate = path_parts[0] if path_parts else None
    elif host in _YT_HOSTS:
        if parsed.path == "/watch":
            candidate = (parse_qs(parsed.query).get("v") or [None])[0]
        elif len(path_parts) >= 2 and path_parts[0] in ("shorts", "live", "embed", "v"):
            candidate = path_parts[1]
    if candidate and _ID_RE.match(candidate):
        return candidate
    return None


def is_youtube_url(url: str) -> bool:
    return youtube_video_id(url) is not None
