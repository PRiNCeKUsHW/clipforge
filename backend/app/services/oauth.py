"""OAuth for publishing: Google (YouTube Data API) and Meta (Instagram Graph API).

The `state` parameter is a short-lived signed JWT carrying the user id, so the callback (a plain
browser redirect from Google/Meta) knows whose account is being connected and can't be forged.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
import jwt

from app.core.config import Settings

STATE_AUDIENCE = "clipforge:oauth"

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
INSTAGRAM_SCOPES = [
    "instagram_basic",
    "instagram_content_publish",
    "pages_show_list",
    "pages_read_engagement",
    "business_management",
]


class OAuthError(Exception):
    """Shown to the user on the Connected accounts page."""


@dataclass
class ConnectedAccount:
    external_id: str
    display_name: str
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scopes: str


def make_state(secret: str, user_id: uuid.UUID, platform: str) -> str:
    payload = {"sub": str(user_id), "p": platform, "aud": STATE_AUDIENCE, "exp": datetime.now(UTC) + timedelta(minutes=10)}
    return jwt.encode(payload, secret, algorithm="HS256")


def read_state(secret: str, state: str, platform: str) -> uuid.UUID:
    try:
        payload = jwt.decode(state, secret, algorithms=["HS256"], audience=STATE_AUDIENCE)
    except jwt.PyJWTError as exc:
        raise OAuthError("The connect link expired or is invalid. Please try again.") from exc
    if payload.get("p") != platform:
        raise OAuthError("OAuth state doesn't match this platform.")
    return uuid.UUID(payload["sub"])


def redirect_uri(settings: Settings, platform: str) -> str:
    return f"{settings.api_public_url.rstrip('/')}/api/oauth/{platform}/callback"


def configured(settings: Settings) -> dict[str, bool]:
    return {
        "youtube": bool(settings.google_client_id and settings.google_client_secret),
        "instagram": bool(settings.meta_app_id and settings.meta_app_secret),
    }


def authorize_url(settings: Settings, platform: str, state: str) -> str:
    if platform == "youtube":
        return GOOGLE_AUTH + "?" + urlencode(
            {
                "client_id": settings.google_client_id,
                "redirect_uri": redirect_uri(settings, "youtube"),
                "response_type": "code",
                "scope": " ".join(YOUTUBE_SCOPES),
                "access_type": "offline",  # we need a refresh token for background uploads
                "prompt": "consent",
                "include_granted_scopes": "true",
                "state": state,
            }
        )
    if platform == "instagram":
        return f"https://www.facebook.com/{settings.meta_graph_version}/dialog/oauth?" + urlencode(
            {
                "client_id": settings.meta_app_id,
                "redirect_uri": redirect_uri(settings, "instagram"),
                "response_type": "code",
                "scope": ",".join(INSTAGRAM_SCOPES),
                "state": state,
            }
        )
    raise OAuthError(f"Unknown platform {platform}")


def _json(r: httpx.Response, what: str) -> dict:
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code >= 400 or (isinstance(data, dict) and "error" in data and r.status_code != 200):
        err = data.get("error") if isinstance(data, dict) else None
        msg = (err.get("message") if isinstance(err, dict) else err) or data.get("error_description") or r.text[:200]
        raise OAuthError(f"{what} failed: {msg}")
    return data


async def connect_youtube(settings: Settings, code: str, http: httpx.AsyncClient) -> ConnectedAccount:
    tokens = _json(
        await http.post(
            GOOGLE_TOKEN,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri(settings, "youtube"),
                "grant_type": "authorization_code",
            },
        ),
        "Google sign-in",
    )
    access = tokens["access_token"]
    channels = _json(
        await http.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {access}"},
        ),
        "Reading your YouTube channel",
    )
    items = channels.get("items") or []
    if not items:
        raise OAuthError("This Google account has no YouTube channel. Create one first, then connect again.")
    return ConnectedAccount(
        external_id=items[0]["id"],
        display_name=items[0]["snippet"]["title"],
        access_token=access,
        refresh_token=tokens.get("refresh_token"),
        expires_at=datetime.now(UTC) + timedelta(seconds=int(tokens.get("expires_in", 3600)) - 60),
        scopes=tokens.get("scope", " ".join(YOUTUBE_SCOPES)),
    )


async def connect_instagram(settings: Settings, code: str, http: httpx.AsyncClient) -> ConnectedAccount:
    base = f"https://graph.facebook.com/{settings.meta_graph_version}"
    short = _json(
        await http.get(
            f"{base}/oauth/access_token",
            params={
                "client_id": settings.meta_app_id,
                "client_secret": settings.meta_app_secret,
                "redirect_uri": redirect_uri(settings, "instagram"),
                "code": code,
            },
        ),
        "Facebook sign-in",
    )
    # Exchange for a long-lived (~60 day) token so publishing works in the background.
    long = _json(
        await http.get(
            f"{base}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": settings.meta_app_id,
                "client_secret": settings.meta_app_secret,
                "fb_exchange_token": short["access_token"],
            },
        ),
        "Getting a long-lived Instagram token",
    )
    token = long["access_token"]
    pages = _json(
        await http.get(
            f"{base}/me/accounts",
            params={"fields": "name,instagram_business_account{id,username}", "access_token": token},
        ),
        "Reading your Facebook Pages",
    )
    for page in pages.get("data", []):
        ig = page.get("instagram_business_account")
        if ig:
            expires = long.get("expires_in")
            return ConnectedAccount(
                external_id=ig["id"],
                display_name=ig.get("username") or page.get("name", "Instagram"),
                access_token=token,
                refresh_token=None,
                expires_at=datetime.now(UTC) + timedelta(seconds=int(expires)) if expires else None,
                scopes=",".join(INSTAGRAM_SCOPES),
            )
    raise OAuthError(
        "No Instagram Business/Creator account found. Switch your Instagram to a Professional account "
        "and link it to a Facebook Page you manage, then connect again."
    )
