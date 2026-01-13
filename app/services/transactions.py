from typing import List, Optional
from datetime import datetime
import psycopg2

from app.db.models import Transaction
from app.audit.logger import log_action
from app.services.budgets import get_budget
from app.db.session import get_db_cursor


# -----------------------------
# Add Transaction / Expense
# -----------------------------
def add_transaction(
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

    budget = get_budget(user_id=user_id, category=category)

    total_spent = get_total_spent(user_id=user_id, category=category)
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

    # Insert transaction
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO transactions (user_id, category, amount, description, created_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, user_id, category, amount, description, created_at
            """,
            (user_id, category, amount, description, datetime.utcnow())
        )
        
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("Failed to add transaction")
        
        transaction_data = {
            "id": row[0],
            "user_id": row[1],
            "category": row[2],
            "amount": float(row[3]),
            "description": row[4],
            "created_at": row[5]
        }
        
        transaction = Transaction(**transaction_data)
        
        log_action(
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
    user_id: int,
    limit: int = 50
) -> List[Transaction]:
    with get_db_cursor(commit=False) as cursor:
        cursor.execute(
            """
            SELECT id, user_id, category, amount, description, created_at
            FROM transactions
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, limit)
        )
        
        rows = cursor.fetchall()
        transactions = []
        for row in rows:
            transactions.append(Transaction(
                id=row[0],
                user_id=row[1],
                category=row[2],
                amount=float(row[3]),
                description=row[4],
                created_at=row[5]
            ))
        
        return transactions


# -----------------------------
# Get Total Spent
# -----------------------------
def get_total_spent(
    user_id: int,
    category: Optional[str] = None
) -> float:
    with get_db_cursor(commit=False) as cursor:
        if category:
            cursor.execute(
                """
                SELECT amount FROM transactions
                WHERE user_id = %s AND category = %s
                """,
                (user_id, category)
            )
        else:
            cursor.execute(
                """
                SELECT amount FROM transactions
                WHERE user_id = %s
                """,
                (user_id,)
            )
        
        rows = cursor.fetchall()
        return sum(float(row[0]) for row in rows)

