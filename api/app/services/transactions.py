"""Transaction writes. Shared by the manual API (M1) and confirmed voice actions (M2)."""

from typing import Any

from sqlalchemy.orm import Session

from app import audit
from app.errors import Invalid, get_owned
from app.models import (
    Account,
    Category,
    CategoryKind,
    Transaction,
    TransactionKind,
    TransactionSource,
    User,
)
from app.schemas import TransactionIn, TransactionPatch


def _check_refs(
    session: Session,
    user: User,
    kind: TransactionKind,
    account_id: int,
    category_id: int | None,
    *,
    allow_archived_account: bool,
) -> None:
    account = get_owned(session, Account, account_id, user.id)
    if account.archived and not allow_archived_account:
        raise Invalid(f"Account '{account.name}' is archived")
    if category_id is not None:
        category = get_owned(session, Category, category_id, user.id)
        if category.kind != CategoryKind(kind.value):
            raise Invalid(
                f"Category '{category.name}' is for {category.kind.value}, not {kind.value}"
            )


def create_transaction(
    session: Session,
    user: User,
    data: TransactionIn,
    *,
    source: TransactionSource = TransactionSource.MANUAL,
    raw_text: str | None = None,
) -> Transaction:
    _check_refs(
        session, user, data.kind, data.account_id, data.category_id, allow_archived_account=False
    )
    txn = Transaction(
        user_id=user.id,
        source=source,
        raw_text=raw_text,
        **data.model_dump(),
    )
    session.add(txn)
    session.flush()
    audit.record(
        session,
        user_id=user.id,
        action="create",
        entity="transaction",
        entity_id=txn.id,
        after=audit.snapshot(txn),
    )
    return txn


def update_transaction(
    session: Session, user: User, txn: Transaction, patch: TransactionPatch
) -> Transaction:
    changes: dict[str, Any] = patch.model_dump(exclude_unset=True)
    for required in ("kind", "amount_paise", "occurred_at", "account_id"):
        if required in changes and changes[required] is None:
            raise Invalid(f"{required} cannot be null")
    before = audit.snapshot(txn)
    kind = changes.get("kind", txn.kind)
    account_id = changes.get("account_id", txn.account_id)
    category_id = changes.get("category_id", txn.category_id)
    # Editing an old transaction on a since-archived account is fine; moving one onto it isn't.
    _check_refs(
        session,
        user,
        kind,
        account_id,
        category_id,
        allow_archived_account=account_id == txn.account_id,
    )
    for field, value in changes.items():
        setattr(txn, field, value)
    session.flush()
    audit.record(
        session,
        user_id=user.id,
        action="update",
        entity="transaction",
        entity_id=txn.id,
        before=before,
        after=audit.snapshot(txn),
    )
    return txn


def delete_transaction(session: Session, user: User, txn: Transaction) -> None:
    audit.record(
        session,
        user_id=user.id,
        action="delete",
        entity="transaction",
        entity_id=txn.id,
        before=audit.snapshot(txn),
    )
    session.delete(txn)
    session.flush()
