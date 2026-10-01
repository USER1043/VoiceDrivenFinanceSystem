from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.db import get_session
from app.errors import get_owned
from app.models import Category, Transaction, TransactionKind, User
from app.schemas import TransactionIn, TransactionOut, TransactionPage, TransactionPatch
from app.services import transactions as service
from app.timeutil import MONTH_PATTERN, month_bounds

router = APIRouter(prefix="/transactions", tags=["transactions"])
DB = Annotated[Session, Depends(get_session)]


def category_and_children(category_id: int) -> Select[int]:
    return select(Category.id).where(
        or_(Category.id == category_id, Category.parent_id == category_id)
    )


@router.get("", response_model=TransactionPage)
def list_transactions(
    user: CurrentUser,
    session: DB,
    month: Annotated[str | None, Query(pattern=MONTH_PATTERN)] = None,
    category_id: int | None = None,
    uncategorised: bool = False,
    account_id: int | None = None,
    kind: TransactionKind | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionPage:
    """Newest first. `category_id` includes its subcategories."""
    conditions = [Transaction.user_id == user.id]
    if month:
        start, end = month_bounds(month, user.timezone)
        conditions += [Transaction.occurred_at >= start, Transaction.occurred_at < end]
    if category_id is not None:
        conditions.append(Transaction.category_id.in_(category_and_children(category_id)))
    if uncategorised:
        conditions.append(Transaction.category_id.is_(None))
    if account_id is not None:
        conditions.append(Transaction.account_id == account_id)
    if kind is not None:
        conditions.append(Transaction.kind == kind)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions.append(or_(Transaction.merchant.ilike(pattern), Transaction.note.ilike(pattern)))

    total = session.scalar(select(func.count()).select_from(Transaction).where(*conditions))
    rows = session.scalars(
        select(Transaction)
        .where(*conditions)
        .order_by(Transaction.occurred_at.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return TransactionPage(items=[to_out(row, user) for row in rows], total=total or 0)


def to_out(txn: Transaction, user: User) -> TransactionOut:
    """Times are returned in the owner's timezone, so dates read the way they were lived."""
    out = TransactionOut.model_validate(txn)
    out.occurred_at = out.occurred_at.astimezone(ZoneInfo(user.timezone))
    return out


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(transaction_id: int, user: CurrentUser, session: DB) -> TransactionOut:
    return to_out(get_owned(session, Transaction, transaction_id, user.id), user)


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(body: TransactionIn, user: CurrentUser, session: DB) -> TransactionOut:
    txn = service.create_transaction(session, user, body)
    session.commit()
    return to_out(txn, user)


@router.patch("/{transaction_id}", response_model=TransactionOut)
def update_transaction(
    transaction_id: int, body: TransactionPatch, user: CurrentUser, session: DB
) -> TransactionOut:
    txn = get_owned(session, Transaction, transaction_id, user.id)
    service.update_transaction(session, user, txn, body)
    session.commit()
    return to_out(txn, user)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(transaction_id: int, user: CurrentUser, session: DB) -> None:
    txn = get_owned(session, Transaction, transaction_id, user.id)
    service.delete_transaction(session, user, txn)
    session.commit()
