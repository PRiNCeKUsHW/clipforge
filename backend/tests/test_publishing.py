import uuid
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet

from app.core.db import SessionLocal
from app.models import ClipStatus, Platform, SocialAccount, User
from app.services import oauth
from tests.conftest import register_and_login
from tests.test_editing import make_clip


@pytest.fixture
def oauth_settings(settings, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "gid")
    monkeypatch.setattr(settings, "google_client_secret", "gsecret")
    monkeypatch.setattr(settings, "meta_app_id", "")
    monkeypatch.setattr(settings, "token_encryption_key", Fernet.generate_key().decode())
    return settings


def test_state_roundtrip_and_tampering():
    uid = uuid.uuid4()
    state = oauth.make_state("s" * 40, uid, "youtube")
    assert oauth.read_state("s" * 40, state, "youtube") == uid
    with pytest.raises(oauth.OAuthError):
        oauth.read_state("s" * 40, state, "instagram")
    with pytest.raises(oauth.OAuthError):
        oauth.read_state("other-secret" * 4, state, "youtube")


async def test_providers_reflect_config(client, oauth_settings):
    assert (await client.get("/api/oauth/providers")).json() == {"youtube": True, "instagram": False}


async def test_start_redirects_to_google_with_offline_access(client, auth, oauth_settings):
    r = await client.get("/api/oauth/youtube/start", headers=auth, follow_redirects=False)
    assert r.status_code == 302
    url = urlparse(r.headers["location"])
    q = parse_qs(url.query)
    assert url.netloc == "accounts.google.com"
    assert q["access_type"] == ["offline"] and q["client_id"] == ["gid"]
    assert q["redirect_uri"] == ["http://localhost:8000/api/oauth/youtube/callback"]
    assert "youtube.upload" in q["scope"][0]
    # Instagram isn't configured
    assert (await client.get("/api/oauth/instagram/start", headers=auth, follow_redirects=False)).status_code == 503


async def test_callback_stores_encrypted_tokens(client, auth, oauth_settings, monkeypatch):
    me = (await client.get("/api/users/me", headers=auth)).json()
    state = oauth.make_state(oauth_settings.jwt_secret, uuid.UUID(me["id"]), "youtube")

    async def fake_connect(settings, code, http):
        assert code == "the-code"
        return oauth.ConnectedAccount("UC123", "My Channel", "access-tok", "refresh-tok", datetime.now(UTC), "scope")

    monkeypatch.setattr(oauth, "connect_youtube", fake_connect)
    r = await client.get(f"/api/oauth/youtube/callback?code=the-code&state={state}", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].endswith("/accounts?connected=youtube")

    accounts = (await client.get("/api/accounts", headers=auth)).json()
    assert len(accounts) == 1 and accounts[0]["display_name"] == "My Channel"
    assert "access_token_encrypted" not in accounts[0]
    async with SessionLocal() as s:
        row = await s.get(SocialAccount, uuid.UUID(accounts[0]["id"]))
        assert row.access_token_encrypted != "access-tok"  # encrypted at rest


async def test_callback_errors_go_back_to_accounts_page(client, oauth_settings):
    r = await client.get("/api/oauth/youtube/callback?error=access_denied", follow_redirects=False)
    assert "error=access_denied" in r.headers["location"]
    r = await client.get("/api/oauth/youtube/callback?code=x&state=forged", follow_redirects=False)
    assert "error=" in r.headers["location"] and "expired" in r.headers["location"]


async def add_account(email: str, platform=Platform.youtube) -> uuid.UUID:
    async with SessionLocal() as s:
        from sqlalchemy import select

        user = (await s.execute(select(User).where(User.email == email))).scalar_one()
        acc = SocialAccount(user_id=user.id, platform=platform, external_account_id="ext", display_name="Chan", access_token_encrypted="x")
        s.add(acc)
        await s.commit()
        return acc.id


async def test_publish_creates_job_and_enqueues(client, auth, s3, enqueued_tasks):
    _, cid = await make_clip(client, auth, s3)
    acc_id = await add_account("alice@example.com")
    r = await client.post(
        f"/api/clips/{cid}/publish",
        headers=auth,
        json={"social_account_id": str(acc_id), "title": "Hook", "description": "d #a", "privacy_status": "unlisted"},
    )
    assert r.status_code == 202, r.text
    job = r.json()
    assert job["platform"] == "youtube" and job["status"] == "queued" and job["privacy_status"] == "unlisted"
    assert enqueued_tasks["publish"] == [uuid.UUID(job["id"])]
    jobs = (await client.get(f"/api/clips/{cid}/publish-jobs", headers=auth)).json()
    assert [j["id"] for j in jobs] == [job["id"]]


async def test_publish_requires_rendered_clip_and_own_account(client, auth, s3):
    _, cid = await make_clip(client, auth, s3, status=ClipStatus.pending)
    acc_id = await add_account("alice@example.com")
    body = {"social_account_id": str(acc_id), "title": "t"}
    assert (await client.post(f"/api/clips/{cid}/publish", headers=auth, json=body)).status_code == 409

    _, ready_cid = await make_clip(client, auth, s3)
    await register_and_login(client, "bob@example.com")
    bobs_account = await add_account("bob@example.com")
    r = await client.post(f"/api/clips/{ready_cid}/publish", headers=auth, json={"social_account_id": str(bobs_account), "title": "t"})
    assert r.status_code == 404


async def test_disconnect_account(client, auth):
    acc_id = await add_account("alice@example.com")
    assert (await client.delete(f"/api/accounts/{acc_id}", headers=auth)).status_code == 204
    assert (await client.get("/api/accounts", headers=auth)).json() == []
