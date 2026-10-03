from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Category


def account_id(session: Session, name: str = "UPI") -> int:
    return session.scalar(select(Account.id).where(Account.name == name))


def category_id(session: Session, name: str) -> int:
    return session.scalar(select(Category.id).where(Category.name == name))


def add_txn(
    client,
    session,
    amount_paise=10000,
    category="Groceries",
    when="2026-09-15T12:00:00+05:30",
    **extra,
):
    body = {
        "amount_paise": amount_paise,
        "occurred_at": when,
        "account_id": account_id(session),
        "category_id": category_id(session, category) if category else None,
        **extra,
    }
    response = client.post("/api/transactions", json=body)
    assert response.status_code == 201, response.text
    return response.json()
