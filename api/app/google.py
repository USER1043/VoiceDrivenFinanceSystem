"""Sign in with Google (OpenID Connect authorization-code flow with PKCE).

The ID token is received directly from Google's token endpoint over TLS in exchange for the
one-time code, so (per OpenID Connect Core 3.1.3.7) its claims are trusted without checking
the JWT signature; issuer, audience, expiry and email verification are still validated.
"""

import base64
import binascii
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUERS = {"https://accounts.google.com", "accounts.google.com"}
STATE_COOKIE = "voxfin_oauth"
STATE_MAX_AGE = 600

# Tests swap this for an httpx.MockTransport.
transport: httpx.BaseTransport | None = None


class GoogleAuthError(Exception):
    """Shown to the user after the redirect back, so messages stay short and plain."""


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    name: str | None


def redirect_uri(settings: Settings) -> str:
    return f"{settings.public_url.rstrip('/')}/api/auth/google/callback"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def start(settings: Settings) -> tuple[str, str]:
    """Returns (Google URL to redirect to, value for the short-lived state cookie)."""
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    query = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri(settings),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
    )
    return f"{AUTHORIZE_URL}?{query}", f"{state}.{verifier}"


def _claims(id_token: str) -> dict[str, Any]:
    try:
        payload = id_token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError, binascii.Error) as exc:
        raise GoogleAuthError("Google sent an unreadable response") from exc
    if not isinstance(claims, dict):
        raise GoogleAuthError("Google sent an unreadable response")
    return claims


def finish(settings: Settings, code: str, state: str, cookie: str | None) -> GoogleIdentity:
    """Check the state, exchange the code and return who signed in."""
    expected_state, _, verifier = (cookie or "").partition(".")
    if not expected_state or not verifier or not secrets.compare_digest(expected_state, state):
        raise GoogleAuthError("The sign-in link expired; please try again")
    try:
        with httpx.Client(timeout=10, transport=transport) as client:
            response = client.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": redirect_uri(settings),
                    "grant_type": "authorization_code",
                    "code_verifier": verifier,
                },
            )
        response.raise_for_status()
        id_token = response.json()["id_token"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise GoogleAuthError("Google sign-in failed; please try again") from exc

    claims = _claims(str(id_token))
    if claims.get("iss") not in ISSUERS or claims.get("aud") != settings.google_client_id:
        raise GoogleAuthError("Google sign-in failed; please try again")
    if float(claims.get("exp", 0)) < time.time():
        raise GoogleAuthError("Google sign-in expired; please try again")
    if claims.get("email_verified") is not True or not claims.get("email") or not claims.get("sub"):
        raise GoogleAuthError("Your Google email address isn't verified")
    name = claims.get("name")
    return GoogleIdentity(
        sub=str(claims["sub"]),
        email=str(claims["email"]).strip().lower(),
        name=str(name)[:80] if name else None,
    )
