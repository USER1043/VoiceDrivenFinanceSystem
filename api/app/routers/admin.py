"""Admin: manage people's accounts. Shows counts and dates only, never anyone's money."""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import auth
from app.auth import AdminUser
from app.config import Settings, get_settings
from app.db import get_session
from app.models import PasswordReset, PendingAction, Transaction, User

router = APIRouter(prefix="/admin", tags=["admin"])
DB = Annotated[Session, Depends(get_session)]
RESET_LINK_HOURS = 24


class UserRow(BaseModel):
    id: int
    email: str
    name: str | None
    is_admin: bool
    disabled: bool
    has_password: bool
    has_google: bool
    created_at: datetime
    last_seen_at: datetime | None
    transactions: int
    last_transaction_at: datetime | None
    commands_last_30_days: int


class ResetLinkOut(BaseModel):
    url: str
    expires_at: datetime


class UserPatch(BaseModel):
    disabled: bool


@router.get("/users", response_model=list[UserRow])
def list_users(admin: AdminUser, session: DB) -> list[UserRow]:
    txns = (
        select(
            Transaction.user_id,
            func.count().label("n"),
            func.max(Transaction.created_at).label("last"),
        )
        .group_by(Transaction.user_id)
        .subquery()
    )
    since = datetime.now(UTC) - timedelta(days=30)
    commands = (
        select(PendingAction.user_id, func.count().label("n"))
        .where(PendingAction.created_at >= since)
        .group_by(PendingAction.user_id)
        .subquery()
    )
    rows = session.execute(
        select(User, txns.c.n, txns.c.last, commands.c.n)
        .outerjoin(txns, txns.c.user_id == User.id)
        .outerjoin(commands, commands.c.user_id == User.id)
        .order_by(User.created_at)
    )
    return [
        UserRow(
            id=user.id,
            email=user.email,
            name=user.name,
            is_admin=user.is_admin,
            disabled=user.disabled,
            has_password=user.password_hash is not None,
            has_google=user.google_sub is not None,
            created_at=user.created_at,
            last_seen_at=user.last_seen_at,
            transactions=n_txns or 0,
            last_transaction_at=last_txn,
            commands_last_30_days=n_commands or 0,
        )
        for user, n_txns, last_txn, n_commands in rows
    ]


@router.post("/users/{user_id}/reset-link", response_model=ResetLinkOut)
def create_reset_link(
    user_id: int,
    admin: AdminUser,
    session: DB,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResetLinkOut:
    """A one-time link (valid 24 h) for someone to choose a new password. Send it privately."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such user")
    now = datetime.now(UTC)
    # Only the newest link works.
    session.execute(
        update(PasswordReset)
        .where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None))
        .values(used_at=now)
    )
    token = secrets.token_urlsafe(32)
    expires = now + timedelta(hours=RESET_LINK_HOURS)
    session.add(
        PasswordReset(
            user_id=user.id,
            token_hash=auth.token_hash(token),
            created_by=admin.id,
            expires_at=expires,
        )
    )
    session.commit()
    base = settings.public_url.rstrip("/") or str(request.base_url).rstrip("/")
    return ResetLinkOut(url=f"{base}/reset#{token}", expires_at=expires)


@router.patch("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def set_disabled(user_id: int, body: UserPatch, admin: AdminUser, session: DB) -> None:
    """Disable (signs them out everywhere) or re-enable an account. Data is kept."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such user")
    if user.id == admin.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "You can't disable yourself")
    user.disabled = body.disabled
    if body.disabled:
        auth.end_all_sessions(session, user.id)
    session.commit()
