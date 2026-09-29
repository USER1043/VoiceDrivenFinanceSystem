from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app import auth
from app.config import get_settings
from app.models import LoginSession
from tests.conftest import OWNER, make_settings

PASSWORD = "correct horse battery staple"
PASSWORD_HASH = auth.hash_password(PASSWORD)


@pytest.fixture(autouse=True)
def _reset_limiter():
    auth.login_limiter.reset()
    yield
    auth.login_limiter.reset()


@pytest.fixture
def pw_client(client):
    settings = make_settings(auth_mode="password", owner_password_hash=PASSWORD_HASH)
    client.app.dependency_overrides[get_settings] = lambda: settings
    return client


def _login(c, password=PASSWORD):
    return c.post("/api/auth/login", json={"password": password})


def test_dev_mode_trusts_the_owner(client, seeded):
    response = client.get("/api/me")
    assert response.status_code == 200
    assert response.json() == {"email": OWNER, "timezone": "Asia/Kolkata", "can_log_out": False}


def test_owner_must_be_seeded(client):
    assert client.get("/api/me").status_code == 503


def test_password_mode_requires_login(pw_client, seeded):
    assert pw_client.get("/api/me").status_code == 401


def test_login_sets_http_only_cookie_and_stores_only_a_hash(pw_client, seeded):
    response = _login(pw_client)
    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    token = pw_client.cookies[auth.SESSION_COOKIE]
    stored = seeded.scalars(select(LoginSession.token_hash)).all()
    assert token not in stored
    assert len(stored) == 1

    me = pw_client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["can_log_out"] is True


def test_wrong_password(pw_client, seeded):
    assert _login(pw_client, "nope").status_code == 401
    assert auth.SESSION_COOKIE not in pw_client.cookies


def test_logout_revokes_the_session(pw_client, seeded):
    _login(pw_client)
    token = pw_client.cookies[auth.SESSION_COOKIE]
    assert pw_client.post("/api/auth/logout").status_code == 204
    assert seeded.scalars(select(LoginSession)).all() == []
    pw_client.cookies.set(auth.SESSION_COOKIE, token)  # replaying the old cookie fails
    assert pw_client.get("/api/me").status_code == 401


def test_expired_session_is_rejected(pw_client, seeded):
    _login(pw_client)
    seeded.execute(update(LoginSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    assert pw_client.get("/api/me").status_code == 401


def test_forged_cookie_is_rejected(pw_client, seeded):
    pw_client.cookies.set(auth.SESSION_COOKIE, "made-up")
    assert pw_client.get("/api/me").status_code == 401


def test_repeated_failures_are_rate_limited(pw_client, seeded):
    for _ in range(auth.login_limiter.max_failures):
        assert _login(pw_client, "wrong").status_code == 401
    blocked = _login(pw_client)  # even the right password waits
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0


def test_existing_session_survives_rate_limit(pw_client, seeded):
    _login(pw_client)
    for _ in range(auth.login_limiter.max_failures):
        auth.login_limiter.record_failure()
    assert pw_client.get("/api/me").status_code == 200


def test_cross_origin_writes_are_blocked(pw_client, seeded):
    response = pw_client.post(
        "/api/auth/login", json={"password": PASSWORD}, headers={"Origin": "https://evil.example"}
    )
    assert response.status_code == 403
    same_origin = pw_client.post(
        "/api/auth/login", json={"password": PASSWORD}, headers={"Origin": "http://testserver"}
    )
    assert same_origin.status_code == 204


def test_secure_cookie_in_production(client, seeded):
    settings = make_settings(
        environment="production", auth_mode="password", owner_password_hash=PASSWORD_HASH
    )
    client.app.dependency_overrides[get_settings] = lambda: settings
    assert "Secure" in _login(client).headers["set-cookie"]


def test_production_requires_password_mode():
    with pytest.raises(ValueError, match="AUTH_MODE"):
        make_settings(environment="production")


def test_password_mode_requires_a_hash():
    with pytest.raises(ValueError, match="OWNER_PASSWORD_HASH"):
        make_settings(auth_mode="password", owner_password_hash="plaintext")


@pytest.mark.parametrize(
    "url",
    ["postgres://u:p@host/db?sslmode=require", "postgresql://u:p@host/db?sslmode=require"],
)
def test_hosted_database_urls_get_the_psycopg_driver(url):
    settings = make_settings(database_url=url)
    assert settings.database_url == "postgresql+psycopg://u:p@host/db?sslmode=require"
