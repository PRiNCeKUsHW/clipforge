"""Unexpected server errors must still reach the browser as a readable 500 with CORS headers."""

from httpx import ASGITransport, AsyncClient

from app.main import create_app

ORIGIN = "http://localhost:3000"


async def test_crash_returns_json_500_with_cors_headers():
    app = create_app()

    @app.get("/api/boom")
    async def boom() -> None:
        raise RuntimeError("database column missing")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/boom", headers={"Origin": ORIGIN})

    assert r.status_code == 500
    assert r.json() == {"detail": "Something went wrong on the server. Please try again."}
    # without this header the browser hides the response and the app says the API is unreachable
    assert r.headers["access-control-allow-origin"] == ORIGIN
    assert "database column" not in r.text  # internals are logged, not sent
