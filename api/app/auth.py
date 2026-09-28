"""Owner authentication.

In production the app sits behind Cloudflare Access, which logs the owner in and forwards a
signed JWT in the `Cf-Access-Jwt-Assertion` header. We verify that JWT here as well, so the
API stays locked even if someone reaches it without going through the tunnel.
"""

from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.models import User

CF_JWT_HEADER = "Cf-Access-Jwt-Assertion"


@lru_cache
def _jwk_client(team_domain: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"https://{team_domain}/cdn-cgi/access/certs", cache_keys=True)


def verify_cf_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """Return the verified claims, or raise jwt.PyJWTError."""
    signing_key = _jwk_client(settings.cf_access_team_domain).get_signing_key_from_jwt(token)
    claims: dict[str, Any] = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.cf_access_aud,
        issuer=f"https://{settings.cf_access_team_domain}",
        options={"require": ["exp", "iat", "aud", "iss"]},
    )
    return claims


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def current_user(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if settings.auth_mode == "cloudflare":
        token = request.headers.get(CF_JWT_HEADER)
        if not token:
            raise _unauthorized("Missing Cloudflare Access token")
        try:
            claims = verify_cf_access_token(token, settings)
        except jwt.PyJWTError as exc:
            raise _unauthorized("Invalid Cloudflare Access token") from exc
        email = str(claims.get("email", "")).lower()
        if email != settings.owner_email.lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the owner")

    user = session.scalar(select(User).where(User.email == settings.owner_email))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Owner not seeded; run `python -m app.seed`",
        )
    return user


CurrentUser = Annotated[User, Depends(current_user)]
