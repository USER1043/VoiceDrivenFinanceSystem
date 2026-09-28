import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app import auth
from app.config import get_settings
from tests.conftest import OWNER, make_settings

TEAM = "example.cloudflareaccess.com"
AUD = "test-aud"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _FakeJWKClient:
    def get_signing_key_from_jwt(self, token):
        return jwt.PyJWK.from_dict(
            {**jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key(), as_dict=True), "alg": "RS256"}
        )


def _token(email=OWNER, aud=AUD, iss=f"https://{TEAM}", exp_in=300, key=KEY):
    now = int(time.time())
    return jwt.encode(
        {"email": email, "aud": aud, "iss": iss, "iat": now, "exp": now + exp_in},
        key,
        algorithm="RS256",
    )


@pytest.fixture
def cf_client(client, monkeypatch):
    settings = make_settings(auth_mode="cloudflare", cf_access_team_domain=TEAM, cf_access_aud=AUD)
    client.app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr(auth, "_jwk_client", lambda team: _FakeJWKClient())
    return client


def _me(c, token=None):
    headers = {auth.CF_JWT_HEADER: token} if token else {}
    return c.get("/api/me", headers=headers)


def test_dev_mode_trusts_the_owner(client, seeded):
    response = _me(client)
    assert response.status_code == 200
    assert response.json() == {"email": OWNER, "timezone": "Asia/Kolkata"}


def test_owner_must_be_seeded(client):
    assert _me(client).status_code == 503


def test_valid_cloudflare_token(cf_client, seeded):
    assert _me(cf_client, _token()).status_code == 200


def test_email_is_case_insensitive(cf_client, seeded):
    assert _me(cf_client, _token(email=OWNER.upper())).status_code == 200


@pytest.mark.parametrize(
    ("token_kwargs", "status"),
    [
        (None, 401),
        ({"aud": "someone-else"}, 401),
        ({"iss": "https://evil.example.com"}, 401),
        ({"exp_in": -60}, 401),
        ({"key": rsa.generate_private_key(public_exponent=65537, key_size=2048)}, 401),
        ({"email": "intruder@example.com"}, 403),
    ],
    ids=["missing", "wrong-aud", "wrong-iss", "expired", "wrong-key", "not-owner"],
)
def test_rejected_tokens(cf_client, seeded, token_kwargs, status):
    token = None if token_kwargs is None else _token(**token_kwargs)
    assert _me(cf_client, token).status_code == status


def test_production_requires_cloudflare_mode():
    with pytest.raises(ValueError, match="AUTH_MODE"):
        make_settings(environment="production")


def test_cloudflare_mode_requires_team_and_aud():
    with pytest.raises(ValueError, match="CF_ACCESS"):
        make_settings(auth_mode="cloudflare")
