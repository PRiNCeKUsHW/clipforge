from tests.conftest import register_and_login


async def test_register_login_and_me(client):
    headers = await register_and_login(client, "bob@example.com")
    r = await client.get("/api/users/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == "bob@example.com"


async def test_short_password_rejected(client):
    r = await client.post("/api/auth/register", json={"email": "c@example.com", "password": "short"})
    assert r.status_code == 400
    assert "8 characters" in r.text


async def test_duplicate_email_rejected(client):
    await register_and_login(client, "dup@example.com")
    r = await client.post("/api/auth/register", json={"email": "dup@example.com", "password": "another-pass"})
    assert r.status_code == 400


async def test_cookie_login_sets_httponly_cookie(client):
    await client.post("/api/auth/register", json={"email": "k@example.com", "password": "s3cret-pass!"})
    r = await client.post("/api/auth/cookie/login", data={"username": "k@example.com", "password": "s3cret-pass!"})
    assert r.status_code == 204
    cookie = r.headers["set-cookie"]
    assert cookie.startswith("clipforge_auth=")
    assert "HttpOnly" in cookie


async def test_wrong_password(client):
    await client.post("/api/auth/register", json={"email": "w@example.com", "password": "s3cret-pass!"})
    r = await client.post("/api/auth/jwt/login", data={"username": "w@example.com", "password": "nope-nope"})
    assert r.status_code == 400


async def test_protected_routes_require_auth(client):
    assert (await client.get("/api/projects")).status_code == 401
    assert (await client.get("/api/users/me")).status_code == 401
