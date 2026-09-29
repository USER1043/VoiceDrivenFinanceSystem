"""Owner authentication: one password, long-lived cookie sessions stored in the database.

The cookie holds a random token; the database stores only its SHA-256, so a leaked database
dump can't be used to log in. Sessions can be revoked by deleting their rows.

Generate the password hash for OWNER_PASSWORD_HASH with:

    uv run python -m app.auth hash-password
"""

import hashlib
import secrets
import sys
import threading
import time
from collections import deque
from datetime import UTC, datetime, timedelta
from getpass import getpass
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.models import LoginSession, User

SESSION_COOKIE = "voxfin_session"
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class LoginRateLimiter:
    """Allows at most `max_failures` wrong passwords per `window` seconds, globally.

    There is one account, so the limit is global rather than per IP (client IPs behind a
    proxy are spoofable). Existing sessions keep working while the limiter is tripped.
    """

    def __init__(self, max_failures: int = 5, window: float = 300.0) -> None:
        self.max_failures = max_failures
        self.window = window
        self._failures: deque[float] = deque()
        self._lock = threading.Lock()

    def retry_after(self) -> int:
        """Seconds until another attempt is allowed; 0 if allowed now."""
        with self._lock:
            now = time.monotonic()
            while self._failures and now - self._failures[0] > self.window:
                self._failures.popleft()
            if len(self._failures) < self.max_failures:
                return 0
            return int(self.window - (now - self._failures[0])) + 1

    def record_failure(self) -> None:
        with self._lock:
            self._failures.append(time.monotonic())

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()


login_limiter = LoginRateLimiter()


def _owner(session: Session, settings: Settings) -> User:
    user = session.scalar(select(User).where(User.email == settings.owner_email))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Owner not seeded; run `python -m app.seed`",
        )
    return user


def log_in(
    password: str,
    request: Request,
    response: Response,
    session: Session,
    settings: Settings,
) -> None:
    retry_after = login_limiter.retry_after()
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts; try again later",
            headers={"Retry-After": str(retry_after)},
        )
    if not verify_password(password, settings.owner_password_hash):
        login_limiter.record_failure()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong password")

    user = _owner(session, settings)
    now = datetime.now(UTC)
    session.execute(delete(LoginSession).where(LoginSession.expires_at < now))
    token = secrets.token_urlsafe(32)
    session.add(
        LoginSession(
            user_id=user.id,
            token_hash=_token_hash(token),
            user_agent=(request.headers.get("user-agent") or "")[:200] or None,
            expires_at=now + timedelta(days=settings.session_days),
        )
    )
    session.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


def log_out(request: Request, response: Response, session: Session) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        session.execute(delete(LoginSession).where(LoginSession.token_hash == _token_hash(token)))
        session.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


def current_user(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if settings.auth_mode == "password":
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
        login = session.scalar(
            select(LoginSession).where(
                LoginSession.token_hash == _token_hash(token),
                LoginSession.expires_at > datetime.now(UTC),
            )
        )
        if login is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
        user = session.get(User, login.user_id)
        if user is None:  # pragma: no cover - cascade deletes sessions with the user
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return user
    return _owner(session, settings)


CurrentUser = Annotated[User, Depends(current_user)]


def main(argv: list[str]) -> int:
    if argv != ["hash-password"]:
        print("usage: python -m app.auth hash-password", file=sys.stderr)
        return 2
    password = getpass("New password: ")
    if len(password) < 12:
        print("Use at least 12 characters.", file=sys.stderr)
        return 1
    if getpass("Repeat: ") != password:
        print("Passwords do not match.", file=sys.stderr)
        return 1
    print(hash_password(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
