import base64
import json
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app import auth, google
from app.models import Account, Category, LoginSession, PasswordReset, User
from app.seed import seed
from tests.conftest import OWNER, make_settings

PASSWORD = "correct horse battery"


def _signup(client, email="friend@example.com", password=PASSWORD, name="Friend"):
    return client.post(
        "/api/auth/signup", json={"email": email, "password": password, "name": name}
    )


def _login(client, email=OWNER, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _set_password(session, email, password=PASSWORD):
    user = session.scalar(select(User).where(User.email == email))
    user.password_hash = auth.hash_password(password)
    session.flush()
    return user


def _new_client(client):
    """A second browser talking to the same app and database."""
    return TestClient(client.app)


# ---------- Sign-up and login ----------


def test_signup_creates_account_with_defaults_and_logs_in(client, seeded, accounts_mode):
    response = _signup(client, email="  Friend@Example.com ")
    assert response.status_code == 204
    assert "HttpOnly" in response.headers["set-cookie"]
    me = client.get("/api/me").json()
    assert me["email"] == "friend@example.com"
    assert me["name"] == "Friend"
    assert me["is_admin"] is False
    user = seeded.scalar(select(User).where(User.email == "friend@example.com"))
    assert seeded.scalar(select(func.count()).where(Account.user_id == user.id)) == 3
    assert seeded.scalar(select(func.count()).where(Category.user_id == user.id)) > 10


def test_signup_rules(client, seeded, accounts_mode):
    assert _signup(client, password="short").status_code == 422
    assert _signup(client, email="not-an-email").status_code == 422
    assert _signup(client).status_code == 204
    assert _signup(_new_client(client), email="FRIEND@example.com").status_code == 409


def test_signup_can_be_closed(client, seeded, accounts_mode):
    accounts_mode(signup_enabled=False)
    assert _signup(client).status_code == 403
    assert client.get("/api/auth/options").json() == {"signup": False, "google": False}


def test_signups_are_rate_limited(client, seeded, accounts_mode):
    for i in range(auth.signups.limit):
        assert _signup(_new_client(client), email=f"f{i}@example.com").status_code == 204
    assert _signup(_new_client(client), email="late@example.com").status_code == 429


def test_login_and_wrong_password(client, seeded, accounts_mode):
    _set_password(seeded, OWNER)
    assert client.get("/api/me").status_code == 401
    assert _login(client, password="nope nope nope").status_code == 401
    assert _login(client, email="nobody@example.com").status_code == 401
    assert _login(client, email=OWNER.upper()).status_code == 204
    assert client.get("/api/me").json()["is_admin"] is True


def test_failed_logins_are_limited_per_email(client, seeded, accounts_mode):
    _set_password(seeded, OWNER)
    _signup(_new_client(client))
    for _ in range(auth.login_failures_per_email.limit):
        assert _login(client, password="wrong password!").status_code == 401
    assert _login(client).status_code == 429  # this account is cooling down
    assert _login(client, email="friend@example.com").status_code == 204  # others aren't


def test_google_only_account_hint(client, seeded, accounts_mode):
    seeded.add(User(email="g@example.com", google_sub="g-1"))
    seeded.flush()
    response = _login(client, email="g@example.com")
    assert response.status_code == 401
    assert "Google" in response.json()["detail"]


def test_disabled_user_cannot_log_in(client, seeded, accounts_mode):
    _signup(client)
    seeded.execute(update(User).where(User.email == "friend@example.com").values(disabled=True))
    assert client.get("/api/me").status_code == 401  # existing session stops working too
    assert _login(client, email="friend@example.com").status_code == 403


def test_change_password_signs_out_other_devices(client, seeded, accounts_mode):
    _signup(client)
    other = _new_client(client)
    assert _login(other, email="friend@example.com").status_code == 204
    bad = client.post(
        "/api/auth/password",
        json={"current_password": "wrong", "new_password": "a new long password"},
    )
    assert bad.status_code == 403
    ok = client.post(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": "a new long password"},
    )
    assert ok.status_code == 204
    assert client.get("/api/me").status_code == 200  # this device stays signed in
    assert other.get("/api/me").status_code == 401
    assert (
        _login(other, email="friend@example.com", password="a new long password").status_code == 204
    )


def test_google_user_can_set_a_first_password(client, seeded, accounts_mode):
    _signup(client)
    seeded.execute(
        update(User)
        .where(User.email == "friend@example.com")
        .values(password_hash=None, google_sub="g-friend")
    )
    # No current password to give: Google-only accounts may set one directly.
    response = client.post("/api/auth/password", json={"new_password": "first password here"})
    assert response.status_code == 204
    login = _login(_new_client(client), email="friend@example.com", password="first password here")
    assert login.status_code == 204


# ---------- Isolation between people ----------


def test_people_only_see_their_own_data(client, seeded, accounts_mode):
    _set_password(seeded, OWNER)
    alice, bob = client, _new_client(client)
    assert _login(alice).status_code == 204
    assert _signup(bob, email="bob@example.com").status_code == 204

    alice_account = alice.get("/api/accounts").json()[0]["id"]
    alice_cat = next(
        c["id"] for c in alice.get("/api/categories").json() if c["name"] == "Groceries"
    )
    txn = alice.post(
        "/api/transactions",
        json={
            "amount_paise": 50000,
            "occurred_at": "2026-09-15T12:00:00+05:30",
            "account_id": alice_account,
            "category_id": alice_cat,
            "merchant": "Secret shop",
        },
    ).json()
    alice.put(f"/api/budgets/{alice_cat}", json={"amount_paise": 100000})
    proposal = alice.post("/api/commands", json={"text": "chai 20"}).json()["action"]

    # Bob sees none of it...
    assert bob.get("/api/transactions").json()["total"] == 0
    assert bob.get("/api/budgets").json() == []
    assert bob.get("/api/summary?month=2026-09").json()["expense_paise"] == 0
    assert "Secret shop" not in bob.get("/api/export/transactions.csv").text
    bob_accounts = {a["id"] for a in bob.get("/api/accounts").json()}
    assert alice_account not in bob_accounts
    # ...and can't touch it by guessing ids.
    assert bob.get(f"/api/transactions/{txn['id']}").status_code == 404
    assert bob.patch(f"/api/transactions/{txn['id']}", json={"amount_paise": 1}).status_code == 404
    assert bob.delete(f"/api/transactions/{txn['id']}").status_code == 404
    assert bob.patch(f"/api/accounts/{alice_account}", json={"name": "mine"}).status_code == 404
    assert bob.patch(f"/api/categories/{alice_cat}", json={"name": "mine"}).status_code == 404
    assert bob.put(f"/api/budgets/{alice_cat}", json={"amount_paise": 1}).status_code == 404
    assert bob.post(f"/api/pending-actions/{proposal['id']}/confirm").status_code == 404
    bob_account = next(iter(bob_accounts))
    smuggle = bob.post(
        "/api/transactions",
        json={
            "amount_paise": 100,
            "occurred_at": "2026-09-15T12:00:00+05:30",
            "account_id": bob_account,
            "category_id": alice_cat,
        },
    )
    assert smuggle.status_code == 404
    assert alice.get(f"/api/transactions/{txn['id']}").json()["amount_paise"] == 50000


def test_each_person_has_their_own_category_names(client, seeded, accounts_mode):
    _set_password(seeded, OWNER)
    _login(client)
    bob = _new_client(client)
    _signup(bob, email="bob@example.com")
    # Same name and alias as the admin's custom category: fine, they're per person.
    body = {"name": "Biryani club", "kind": "expense", "aliases": ["biryani club"]}
    assert client.post("/api/categories", json=body).status_code == 201
    assert bob.post("/api/categories", json=body).status_code == 201


# ---------- Admin ----------


def test_admin_sees_accounts_and_counts_only(client, seeded, accounts_mode):
    _set_password(seeded, OWNER)
    friend = _new_client(client)
    _signup(friend)
    account = friend.get("/api/accounts").json()[0]["id"]
    friend.post(
        "/api/transactions",
        json={
            "amount_paise": 999900,
            "occurred_at": "2026-09-15T12:00:00+05:30",
            "account_id": account,
        },
    )
    assert friend.get("/api/admin/users").status_code == 403

    _login(client)
    rows = {r["email"]: r for r in client.get("/api/admin/users").json()}
    assert rows[OWNER]["is_admin"] is True
    friend_row = rows["friend@example.com"]
    assert friend_row["transactions"] == 1
    assert friend_row["has_password"] is True
    assert "999900" not in json.dumps(friend_row)  # no amounts in the admin view


def test_reset_link_flow(client, seeded, accounts_mode):
    _set_password(seeded, OWNER)
    friend = _new_client(client)
    _signup(friend)
    friend_id = seeded.scalar(select(User.id).where(User.email == "friend@example.com"))
    _login(client)

    first = client.post(f"/api/admin/users/{friend_id}/reset-link").json()
    link = client.post(f"/api/admin/users/{friend_id}/reset-link").json()
    assert "/reset#" in link["url"]
    token = link["url"].split("#", 1)[1]
    stale = first["url"].split("#", 1)[1]
    assert (
        seeded.scalar(select(PasswordReset.token_hash).where(PasswordReset.used_at.is_(None)))
        != token
    )

    assert friend.get("/api/me").status_code == 200
    stranger = _new_client(client)
    assert (
        stranger.post(
            "/api/auth/reset", json={"token": stale, "new_password": "brand new password"}
        ).status_code
        == 400
    )
    assert (
        stranger.post("/api/auth/reset", json={"token": token, "new_password": "short"}).status_code
        == 422
    )
    used = stranger.post(
        "/api/auth/reset", json={"token": token, "new_password": "brand new password"}
    )
    assert used.status_code == 204
    assert stranger.get("/api/me").json()["email"] == "friend@example.com"
    assert friend.get("/api/me").status_code == 401  # old sessions are signed out
    again = _new_client(client).post(
        "/api/auth/reset", json={"token": token, "new_password": "another password"}
    )
    assert again.status_code == 400  # one-time
    assert (
        _login(
            _new_client(client), email="friend@example.com", password="brand new password"
        ).status_code
        == 204
    )


def test_reset_links_expire(client, seeded, accounts_mode):
    _set_password(seeded, OWNER)
    _login(client)
    friend_id = seeded.scalar(select(User.id).where(User.email == OWNER))
    token = client.post(f"/api/admin/users/{friend_id}/reset-link").json()["url"].split("#")[1]
    seeded.execute(
        update(PasswordReset).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    response = _new_client(client).post(
        "/api/auth/reset", json={"token": token, "new_password": "brand new password"}
    )
    assert response.status_code == 400


def test_admin_can_disable_and_enable(client, seeded, accounts_mode):
    _set_password(seeded, OWNER)
    friend = _new_client(client)
    _signup(friend)
    friend_id = seeded.scalar(select(User.id).where(User.email == "friend@example.com"))
    admin_id = seeded.scalar(select(User.id).where(User.email == OWNER))
    _login(client)
    assert client.patch(f"/api/admin/users/{admin_id}", json={"disabled": True}).status_code == 422
    assert client.patch(f"/api/admin/users/{friend_id}", json={"disabled": True}).status_code == 204
    assert friend.get("/api/me").status_code == 401
    assert seeded.scalar(select(func.count()).where(LoginSession.user_id == friend_id)) == 0
    assert (
        client.patch(f"/api/admin/users/{friend_id}", json={"disabled": False}).status_code == 204
    )
    assert _login(friend, email="friend@example.com").status_code == 204


# ---------- Admin bootstrap ----------


def test_seed_makes_the_admin_and_only_fills_a_missing_password(session):
    first_hash = auth.hash_password("the first password")
    admin = seed(session, "  Admin@Example.com ", "Asia/Kolkata", first_hash)
    assert (admin.email, admin.is_admin, admin.password_hash) == (
        "admin@example.com",
        True,
        first_hash,
    )
    admin.password_hash = auth.hash_password("changed in the app")
    changed = admin.password_hash
    seed(session, "admin@example.com", "Asia/Kolkata", first_hash)  # redeploy
    assert admin.password_hash == changed


def test_google_settings_need_public_url():
    with pytest.raises(ValueError, match="PUBLIC_URL"):
        make_settings(google_client_id="id", google_client_secret="secret")


# ---------- Google sign-in (Google's token endpoint mocked) ----------


def _id_token(**claims):
    body = {
        "iss": "https://accounts.google.com",
        "aud": "client-id",
        "sub": "google-123",
        "email": "friend@gmail.com",
        "email_verified": True,
        "name": "Friend G",
        "exp": time.time() + 300,
    } | claims
    encode = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()  # noqa: E731
    return f"{encode({'alg': 'RS256'})}.{encode(body)}.signature"


@pytest.fixture
def google_on(client, accounts_mode, monkeypatch):
    seen = {}

    def install(signup_enabled=True, **claims):
        accounts_mode(
            google_client_id="client-id",
            google_client_secret="client-secret",
            public_url="https://voxfin.example.com",
            signup_enabled=signup_enabled,
        )

        def handler(request):
            seen["form"] = parse_qs(request.content.decode())
            return httpx.Response(200, json={"id_token": _id_token(**claims)})

        monkeypatch.setattr(google, "transport", httpx.MockTransport(handler))

    install()
    return install, seen


def _google_round_trip(client):
    start = client.get("/api/auth/google/start", follow_redirects=False)
    assert start.status_code == 303
    query = parse_qs(urlsplit(start.headers["location"]).query)
    return client.get(
        "/api/auth/google/callback",
        params={"code": "auth-code", "state": query["state"][0]},
        follow_redirects=False,
    ), query


def test_google_start_uses_pkce_and_state(client, seeded, google_on):
    start = client.get("/api/auth/google/start", follow_redirects=False)
    url = urlsplit(start.headers["location"])
    query = parse_qs(url.query)
    assert url.netloc == "accounts.google.com"
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == ["https://voxfin.example.com/api/auth/google/callback"]
    assert query["code_challenge_method"] == ["S256"]
    assert google.STATE_COOKIE in start.headers["set-cookie"]


def test_google_sign_up(client, seeded, google_on):
    _, seen = google_on
    callback, _ = _google_round_trip(client)
    assert callback.status_code == 303
    assert callback.headers["location"] == "/"
    me = client.get("/api/me").json()
    assert (me["email"], me["name"], me["has_google"], me["has_password"]) == (
        "friend@gmail.com", "Friend G", True, False,
    )  # fmt: skip
    assert seen["form"]["client_secret"] == ["client-secret"]
    assert seen["form"]["code_verifier"][0]  # PKCE verifier sent back to Google
    user = seeded.scalar(select(User).where(User.email == "friend@gmail.com"))
    assert seeded.scalar(select(func.count()).where(Account.user_id == user.id)) == 3


def test_google_links_to_existing_email(client, seeded, google_on):
    install, _ = google_on
    install(email=OWNER)
    callback, _ = _google_round_trip(client)
    assert callback.headers["location"] == "/"
    owner = seeded.scalar(select(User).where(User.email == OWNER))
    assert owner.google_sub == "google-123"
    assert client.get("/api/me").json()["is_admin"] is True


@pytest.mark.parametrize(
    ("claims", "message"),
    [
        ({"aud": "someone-else"}, "failed"),
        ({"iss": "https://evil.example"}, "failed"),
        ({"email_verified": False}, "verified"),
        ({"exp": time.time() - 10}, "expired"),
    ],
)
def test_google_rejects_bad_tokens(client, seeded, google_on, claims, message):
    install, _ = google_on
    install(**claims)
    callback, _ = _google_round_trip(client)
    assert "auth_error" in callback.headers["location"]
    assert message in callback.headers["location"]
    assert client.get("/api/me").status_code == 401


def test_google_rejects_forged_state(client, seeded, google_on):
    client.get("/api/auth/google/start", follow_redirects=False)
    callback = client.get(
        "/api/auth/google/callback", params={"code": "x", "state": "forged"}, follow_redirects=False
    )
    assert "auth_error" in callback.headers["location"]
    assert seeded.scalar(select(func.count()).select_from(User)) == 1


def test_google_respects_closed_signup(client, seeded, google_on):
    install, _ = google_on
    install(signup_enabled=False)
    callback, _ = _google_round_trip(client)
    assert "Sign-up%20is%20closed" in callback.headers["location"]


def test_google_disabled_account(client, seeded, google_on):
    seeded.add(User(email="friend@gmail.com", google_sub="google-123", disabled=True))
    seeded.flush()
    callback, _ = _google_round_trip(client)
    assert "disabled" in callback.headers["location"]


# ---------- Shared AI quota ----------


def test_commands_are_rate_limited_per_person(client, seeded, accounts_mode):
    accounts_mode(commands_per_10_minutes=3)
    _signup(client)
    for _ in range(3):
        assert client.post("/api/commands", json={"text": "chai 20"}).status_code == 200
    assert client.post("/api/commands", json={"text": "chai 20"}).status_code == 429
    other = _new_client(client)
    _signup(other, email="bob@example.com")
    assert other.post("/api/commands", json={"text": "chai 20"}).status_code == 200
