from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import auth, google
from app.auth import CurrentUser
from app.config import Settings, get_settings
from app.db import get_session
from app.models import PasswordReset, User
from app.seed import add_defaults

router = APIRouter(prefix="/auth", tags=["auth"])
DB = Annotated[Session, Depends(get_session)]
Config = Annotated[Settings, Depends(get_settings)]

Password = Annotated[str, Field(min_length=1, max_length=256)]


class AuthOptions(BaseModel):
    signup: bool
    google: bool


class LoginIn(BaseModel):
    email: EmailStr
    password: Password


class SignupIn(BaseModel):
    email: EmailStr
    password: Password
    name: Annotated[str, Field(max_length=80)] | None = None


class PasswordChangeIn(BaseModel):
    current_password: Password | None = None
    new_password: Password


class ResetIn(BaseModel):
    token: Annotated[str, Field(min_length=10, max_length=200)]
    new_password: Password


@router.get("/options", response_model=AuthOptions)
def options(settings: Config) -> AuthOptions:
    """Which sign-in buttons the login screen should show."""
    return AuthOptions(signup=settings.signup_enabled, google=settings.google_enabled)


@router.post("/signup", status_code=status.HTTP_204_NO_CONTENT)
def signup(
    body: SignupIn, request: Request, response: Response, session: DB, settings: Config
) -> None:
    if not settings.signup_enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sign-up is closed")
    wait = auth.signups.retry_after("all")
    if wait:
        raise auth.too_many(wait, "Too many sign-ups right now; try again later")
    auth.check_password_strength(body.password)
    email = auth.normalise_email(body.email)
    if session.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(
        email=email,
        name=(body.name or "").strip() or None,
        timezone=settings.timezone,
        password_hash=auth.hash_password(body.password),
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError as exc:  # a simultaneous sign-up with the same email
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An account with this email already exists"
        ) from exc
    add_defaults(session, user)
    auth.signups.hit("all")
    auth.start_session(user, request, response, session, settings)


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
def login(
    body: LoginIn, request: Request, response: Response, session: DB, settings: Config
) -> None:
    auth.log_in(body.email, body.password, request, response, session, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, session: DB) -> None:
    auth.log_out(request, response, session)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: PasswordChangeIn,
    user: CurrentUser,
    request: Request,
    response: Response,
    session: DB,
    settings: Config,
) -> None:
    """Set or change your password. Signs out every other device."""
    if user.password_hash and not auth.verify_password(
        body.current_password or "", user.password_hash
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your current password is wrong")
    auth.check_password_strength(body.new_password)
    user.password_hash = auth.hash_password(body.new_password)
    auth.end_all_sessions(session, user.id)
    auth.start_session(user, request, response, session, settings)


@router.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    body: ResetIn, request: Request, response: Response, session: DB, settings: Config
) -> None:
    """Use a one-time reset link from the admin to choose a new password."""
    now = datetime.now(UTC)
    reset = session.scalar(
        select(PasswordReset).where(
            PasswordReset.token_hash == auth.token_hash(body.token),
            PasswordReset.used_at.is_(None),
            PasswordReset.expires_at > now,
        )
    )
    user = session.get(User, reset.user_id) if reset else None
    if reset is None or user is None or user.disabled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "This reset link is invalid or has expired"
        )
    auth.check_password_strength(body.new_password)
    user.password_hash = auth.hash_password(body.new_password)
    reset.used_at = now
    auth.end_all_sessions(session, user.id)
    auth.start_session(user, request, response, session, settings)


# ---------- Google ----------


def _back_to_app(error: str | None = None) -> RedirectResponse:
    target = f"/?auth_error={quote(error)}" if error else "/"
    response = RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(google.STATE_COOKIE, path="/api/auth/google")
    return response


@router.get("/google/start")
def google_start(settings: Config) -> RedirectResponse:
    if not settings.google_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Google sign-in is not set up")
    url, cookie = google.start(settings)
    response = RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        google.STATE_COOKIE,
        cookie,
        max_age=google.STATE_MAX_AGE,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",  # sent on Google's top-level redirect back to us
        path="/api/auth/google",
    )
    return response


@router.get("/google/callback")
def google_callback(
    request: Request,
    session: DB,
    settings: Config,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if not settings.google_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Google sign-in is not set up")
    if error or not code or not state:
        return _back_to_app("Google sign-in was cancelled")
    try:
        identity = google.finish(settings, code, state, request.cookies.get(google.STATE_COOKIE))
    except google.GoogleAuthError as exc:
        return _back_to_app(str(exc))

    user = session.scalar(select(User).where(User.google_sub == identity.sub))
    if user is None:
        # Same verified email as an existing account: link Google to it.
        user = session.scalar(select(User).where(User.email == identity.email))
        if user is not None:
            user.google_sub = identity.sub
            user.name = user.name or identity.name
        elif settings.signup_enabled:
            user = User(
                email=identity.email,
                name=identity.name,
                google_sub=identity.sub,
                timezone=settings.timezone,
            )
            session.add(user)
            session.flush()
            add_defaults(session, user)
        else:
            return _back_to_app("Sign-up is closed")
    if user.disabled:
        session.rollback()
        return _back_to_app("This account is disabled")

    response = _back_to_app()
    auth.start_session(user, request, response, session, settings)
    return response
