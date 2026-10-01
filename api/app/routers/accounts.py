from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import audit
from app.auth import CurrentUser
from app.db import get_session
from app.errors import Invalid, get_owned
from app.models import Account
from app.schemas import AccountIn, AccountOut, AccountPatch

router = APIRouter(prefix="/accounts", tags=["accounts"])
DB = Annotated[Session, Depends(get_session)]


def _make_default(session: Session, account: Account) -> None:
    session.execute(
        update(Account)
        .where(Account.user_id == account.user_id, Account.id != account.id)
        .values(is_default=False)
    )
    account.is_default = True


@router.get("", response_model=list[AccountOut])
def list_accounts(user: CurrentUser, session: DB) -> list[Account]:
    return list(
        session.scalars(select(Account).where(Account.user_id == user.id).order_by(Account.id))
    )


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(body: AccountIn, user: CurrentUser, session: DB) -> Account:
    account = Account(user_id=user.id, name=body.name, kind=body.kind)
    session.add(account)
    session.flush()
    if body.is_default:
        _make_default(session, account)
    audit.record(
        session,
        user_id=user.id,
        action="create",
        entity="account",
        entity_id=account.id,
        after=audit.snapshot(account),
    )
    session.commit()
    return account


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(account_id: int, body: AccountPatch, user: CurrentUser, session: DB) -> Account:
    account = get_owned(session, Account, account_id, user.id)
    before = audit.snapshot(account)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if changes.get("archived") and (account.is_default or changes.get("is_default")):
        raise Invalid("Make another account the default before archiving this one")
    if changes.get("is_default") is False and account.is_default:
        raise Invalid("Make another account the default instead")
    if changes.pop("is_default", False):
        if account.archived and changes.get("archived") is not False:
            raise Invalid("An archived account can't be the default")
        _make_default(session, account)
    for field, value in changes.items():
        setattr(account, field, value)
    session.flush()
    audit.record(
        session,
        user_id=user.id,
        action="update",
        entity="account",
        entity_id=account.id,
        before=before,
        after=audit.snapshot(account),
    )
    session.commit()
    return account
