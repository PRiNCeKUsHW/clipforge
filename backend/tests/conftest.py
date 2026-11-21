"""Backend test setup.

Uses a real PostgreSQL: TEST_DATABASE_URL if set (e.g. the docker compose Postgres), otherwise an
embedded server from the `pgserver` package. S3 is faked with moto, Celery and Redis are stubbed.
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]

# ---- configure env BEFORE importing the app (the engine is created at import time) ----
_pg = None
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
else:
    import pgserver

    _pg = pgserver.get_server(tempfile.mkdtemp(prefix="clipforge-pg-"), cleanup_mode="delete")
    os.environ["DATABASE_URL"] = _pg.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)

os.environ.update(
    {
        "APP_ENV": "test",
        "JWT_SECRET": "test-secret-" + "x" * 32,
        "REDIS_URL": "redis://localhost:6399/0",
        "S3_ENDPOINT_URL": "",
        "S3_PUBLIC_ENDPOINT_URL": "",
        "S3_BUCKET": "clipforge-test",
        "S3_ACCESS_KEY": "testing",
        "S3_SECRET_KEY": "testing",
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
    }
)

if sys.platform == "win32":
    # psycopg's async mode needs the selector event loop on Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from moto import mock_aws  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.core import deps  # noqa: E402
from app.core.db import engine  # noqa: E402
from app.main import app  # noqa: E402


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    command.upgrade(alembic_config(), "head")
    yield
    if _pg is not None:
        _pg.cleanup()


@pytest.fixture(autouse=True)
async def clean_tables():
    yield
    sync = create_engine(os.environ["DATABASE_URL"])
    with sync.begin() as conn:
        conn.execute(text("TRUNCATE users, video_projects, clips, social_accounts, publish_jobs CASCADE"))
    sync.dispose()
    # connections are bound to this test's event loop
    await engine.dispose()


@pytest.fixture(autouse=True)
def s3():
    with mock_aws():
        deps.get_storage.cache_clear()
        storage = deps.get_storage()
        storage.client.create_bucket(Bucket=storage.bucket)
        yield storage
    deps.get_storage.cache_clear()


@pytest.fixture(autouse=True)
def enqueued(monkeypatch):
    calls: list = []
    monkeypatch.setattr("app.api.projects.enqueue_pipeline", lambda pid: calls.append(pid))
    return calls


@pytest.fixture(autouse=True)
def enqueued_tasks(monkeypatch):
    calls: dict[str, list] = {"render": [], "publish": []}
    monkeypatch.setattr("app.api.clips.enqueue_render", lambda cid: calls["render"].append(cid))
    monkeypatch.setattr("app.api.clips.enqueue_publish", lambda jid: calls["publish"].append(jid))
    return calls


@pytest.fixture
def settings(monkeypatch):
    """The live settings object; tests may monkeypatch attributes on it."""
    from app.core.config import get_settings

    return get_settings()


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def register_and_login(client: AsyncClient, email: str = "alice@example.com", password: str = "s3cret-pass!") -> dict:
    r = await client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    r = await client.post("/api/auth/jwt/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def auth(client) -> dict:
    return await register_and_login(client)
