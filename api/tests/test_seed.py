import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Account, Category, CategoryKind, Transaction, TransactionKind
from app.seed import DEFAULT_ACCOUNTS, seed
from tests.conftest import OWNER


def _count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def test_seed_is_idempotent(seeded):
    accounts, categories = _count(seeded, Account), _count(seeded, Category)
    seed(seeded, OWNER, "Asia/Kolkata")
    assert _count(seeded, Account) == accounts == len(DEFAULT_ACCOUNTS)
    assert _count(seeded, Category) == categories


def test_upi_is_the_default_account(seeded):
    default = seeded.scalars(select(Account).where(Account.is_default)).all()
    assert [a.name for a in default] == ["UPI"]


def test_top_level_category_names_are_unique(seeded):
    user_id = seeded.scalar(select(Account.user_id))
    seeded.add(Category(user_id=user_id, kind=CategoryKind.EXPENSE, name="Food"))
    with pytest.raises(IntegrityError):
        seeded.flush()


def test_amount_must_be_positive(seeded):
    account = seeded.scalar(select(Account).where(Account.is_default))
    seeded.add(
        Transaction(
            user_id=account.user_id,
            account_id=account.id,
            kind=TransactionKind.EXPENSE,
            amount_paise=0,
            occurred_at=func.now(),
            source="manual",
        )
    )
    with pytest.raises(IntegrityError):
        seeded.flush()
