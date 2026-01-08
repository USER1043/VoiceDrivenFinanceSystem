from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional

from app.db.models import Transaction
from app.audit.logger import log_action


# -----------------------------
# Add Transaction / Expense
# -----------------------------
def add_transaction(
    db: Session,
    user_id: int,
    category: str,
    limit: float,
    description: Optional[str] = None
) -> Transaction:
    """
    Add a new transaction (expense).
    """

    # Service-level validation
    if limit <= 0:
        raise ValueError("Transaction limit must be positive")

    transaction = Transaction(
        user_id=user_id,
        category=category,
        limit=limit,
        description=description
    )

    try:
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
    except IntegrityError:
        db.rollback()
        raise RuntimeError("Failed to add transaction")

    # Audit log
    log_action(
        db=db,
        user_id=user_id,
        action="ADD_TRANSACTION",
        details=f"{category} → {limit}"
    )

    return transaction


# -----------------------------
# Get All Transactions
# -----------------------------
def get_transactions(
    db: Session,
    user_id: int,
    limit: int = 50
) -> List[Transaction]:
    """
    Fetch recent transactions for a user.
    """

    return (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .all()
    )


# -----------------------------
# Get Transactions by Category
# -----------------------------
def get_transactions_by_category(
    db: Session,
    user_id: int,
    category: str
) -> List[Transaction]:
    """
    Fetch transactions for a specific category.
    """

    return (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.category == category
        )
        .order_by(Transaction.created_at.desc())
        .all()
    )


# -----------------------------
# Get Total Spent (Optional Helper)
# -----------------------------
def get_total_spent(
    db: Session,
    user_id: int,
    category: Optional[str] = None
) -> float:
    """
    Calculate total spent by user.
    Optionally filtered by category.
    """

    query = db.query(Transaction).filter(Transaction.user_id == user_id)

    if category:
        query = query.filter(Transaction.category == category)

    return sum(t.limit for t in query.all())


# -----------------------------
# Delete Transaction (Optional)
# -----------------------------
def delete_transaction(
    db: Session,
    transaction_id: int,
    user_id: int
) -> bool:
    """
    Delete a transaction.
    """

    transaction = (
        db.query(Transaction)
        .filter(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id
        )
        .first()
    )

    if not transaction:
        return False

    db.delete(transaction)
    db.commit()

    log_action(
        db=db,
        user_id=user_id,
        action="DELETE_TRANSACTION",
        details=f"Transaction {transaction_id} deleted"
    )

    return True
