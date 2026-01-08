from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional

from app.db.models import Transaction
from app.audit.logger import log_action
from app.services.budgets import get_budget


# -----------------------------
# Add Transaction / Expense
# -----------------------------
def add_transaction(
    db: Session,
    user_id: int,
    category: str,
    amount: float,
    description: Optional[str] = None
) -> Transaction:
    """
    Add a new transaction (expense).
    """

    if amount <= 0:
        raise ValueError("Transaction amount must be positive")

    budget = get_budget(db=db, user_id=user_id, category=category)

    total_spent = get_total_spent(db=db, user_id=user_id, category=category)
    new_total = total_spent + amount

    budget_warning = None
    if budget:
        if new_total > budget.limit:
            budget_warning = (
                f"WARNING: Budget exceeded! Limit: {budget.limit}, "
                f"Total spent: {new_total:.2f}"
            )
        elif new_total > budget.limit * 0.9:
            budget_warning = (
                f"WARNING: Approaching budget limit. Limit: {budget.limit}, "
                f"Total spent: {new_total:.2f}"
            )

    transaction = Transaction(
        user_id=user_id,
        category=category,
        amount=amount,                 # ✅ FIX
        description=description
    )

    try:
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
    except IntegrityError:
        db.rollback()
        raise RuntimeError("Failed to add transaction")

    log_action(
        db=db,
        user_id=user_id,
        action="ADD_TRANSACTION",
        details=f"{category} → {amount}"
    )

    if budget_warning:
        transaction.budget_warning = budget_warning

    return transaction


# -----------------------------
# Get Transactions
# -----------------------------
def get_transactions(
    db: Session,
    user_id: int,
    limit: int = 50
) -> List[Transaction]:
    return (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .all()
    )


# -----------------------------
# Get Total Spent
# -----------------------------
def get_total_spent(
    db: Session,
    user_id: int,
    category: Optional[str] = None
) -> float:
    query = db.query(Transaction).filter(Transaction.user_id == user_id)

    if category:
        query = query.filter(Transaction.category == category)

    return sum(t.amount for t in query.all())   # ✅ FIX
