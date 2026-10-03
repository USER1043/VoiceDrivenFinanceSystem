"""Authentication: per-user passwords (argon2) and Google sign-in, with cookie sessions.

The session cookie holds a random token; the database stores only its SHA-256, so a leaked
database dump can't be used to log in. Sessions can be revoked by deleting their rows.

Generate a password hash for OWNER_PASSWORD_HASH (the admin's first password) with:

    uv run python -m app.auth hash-password
"""

import hashlib
import secrets
import sys
import threading
import time
from collections import defaultdict, deque
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
MIN_PASSWORD_LENGTH = 10
LAST_SEEN_EVERY = timedelta(minutes=10)
_hasher = PasswordHasher()
# Verified against when the email is unknown, so response time doesn't reveal which
# emails have accounts.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and bool(password_hash)
    except (VerificationError, InvalidHashError):
        return False


def check_password_strength(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Use at least {MIN_PASSWORD_LENGTH} characters (a few random words works well)",
        )


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def normalise_email(email: str) -> str:
    return email.strip().lower()


class RateLimiter:
    """At most `limit` events per `window` seconds for each key (an email, a user id...)."""

    def __init__(self, limit: int, window: float) -> None:
        self.limit = limit
        self.window = window
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def retry_after(self, key: str) -> int:
        """Seconds until another event is allowed for `key`; 0 if allowed now."""
        with self._lock:
            events = self._events[key]
            now = time.monotonic()
            while events and now - events[0] > self.window:
                events.popleft()
            if len(events) < self.limit:
                return 0
            return int(self.window - (now - events[0])) + 1

    def hit(self, key: str) -> None:
        with self._lock:
            self._events[key].append(time.monotonic())

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


# Wrong passwords: per email (protects each account) and overall (slows broad guessing).
login_failures_per_email = RateLimiter(limit=5, window=300)
login_failures_overall = RateLimiter(limit=50, window=300)
signups = RateLimiter(limit=20, window=3600)


def too_many(retry_after: int, detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=detail,
        headers={"Retry-After": str(retry_after)},
    )


def start_session(
    user: User, request: Request, response: Response, session: Session, settings: Settings
) -> None:
    now = datetime.now(UTC)
    session.execute(delete(LoginSession).where(LoginSession.expires_at < now))
    token = secrets.token_urlsafe(32)
    session.add(
        LoginSession(
            user_id=user.id,
            token_hash=token_hash(token),
            user_agent=(request.headers.get("user-agent") or "")[:200] or None,
            expires_at=now + timedelta(days=settings.session_days),
        )
    )
    user.last_seen_at = now
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


def end_all_sessions(session: Session, user_id: int) -> None:
    session.execute(delete(LoginSession).where(LoginSession.user_id == user_id))


def log_in(
    email: str,
    password: str,
    request: Request,
    response: Response,
    session: Session,
    settings: Settings,
) -> User:
    email = normalise_email(email)
    wait = max(
        login_failures_per_email.retry_after(email), login_failures_overall.retry_after("all")
    )
    if wait:
        raise too_many(wait, "Too many failed attempts; try again in a few minutes")
    user = session.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        login_failures_per_email.hit(email)
        login_failures_overall.hit("all")
        detail = "Wrong email or password"
        if user is not None and user.password_hash is None and user.google_sub:
            detail = "This account uses Google sign-in"
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
    if user.disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This account is disabled"
        )
    start_session(user, request, response, session, settings)
    return user


def log_out(request: Request, response: Response, session: Session) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        session.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(token)))
        session.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


def current_user(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if settings.auth_mode == "dev":
        user = session.scalar(select(User).where(User.email == settings.admin_email))
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Admin not seeded; run `python -m app.seed`",
            )
        return user

    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    now = datetime.now(UTC)
    login = session.scalar(
        select(LoginSession).where(
            LoginSession.token_hash == token_hash(token), LoginSession.expires_at > now
        )
    )
    user = session.get(User, login.user_id) if login else None
    if user is None or user.disabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    if user.last_seen_at is None or now - user.last_seen_at > LAST_SEEN_EVERY:
        user.last_seen_at = now  # throttled, so most requests stay read-only
        session.commit()
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def admin_user(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    return user


AdminUser = Annotated[User, Depends(admin_user)]


def main(argv: list[str]) -> int:
    if argv != ["hash-password"]:
        print("usage: python -m app.auth hash-password", file=sys.stderr)
        return 2
    password = getpass("Choose your VoxFin login password (typing is hidden): ")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"Use at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
        return 1
    if getpass("Type it again: ") != password:
        print("Passwords do not match.", file=sys.stderr)
        return 1
    print(hash_password(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
