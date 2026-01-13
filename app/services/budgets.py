from typing import Optional
from datetime import datetime
import psycopg2

from app.db.models import Budget
from app.audit.logger import log_action
from app.db.session import get_db_cursor


# -----------------------------
# Create or Update Budget
# -----------------------------
def set_budget(
    user_id: int,
    category: str,
    limit: float
) -> Budget:
    """
    Create a new budget or update an existing one for a category.
    """

    # Validation (service-level safety)
    if limit <= 0:
        raise ValueError("Budget limit must be greater than zero")

    with get_db_cursor() as cursor:
        # Check if budget exists
        cursor.execute(
            """
            SELECT id, user_id, category, limit_amount, created_at
            FROM budgets
            WHERE user_id = %s AND category = %s
            """,
            (user_id, category)
        )
        
        existing_budget_data = cursor.fetchone()

        if existing_budget_data:
            # Update existing budget
            cursor.execute(
                """
                UPDATE budgets
                SET limit_amount = %s
                WHERE id = %s
                RETURNING id, user_id, category, limit_amount, created_at
                """,
                (limit, existing_budget_data[0])
            )
            
            row = cursor.fetchone()
            if not row:
                raise RuntimeError("Failed to update budget")
            
            budget_data = {
                "id": row[0],
                "user_id": row[1],
                "category": row[2],
                "limit_amount": float(row[3]),
                "created_at": row[4]
            }
            
            budget = Budget(**budget_data)
            action = "UPDATE_BUDGET"
        else:
            # Create new budget
            cursor.execute(
                """
                INSERT INTO budgets (user_id, category, limit_amount, created_at)
                VALUES (%s, %s, %s, %s)
                RETURNING id, user_id, category, limit_amount, created_at
                """,
                (user_id, category, limit, datetime.utcnow())
            )
            
            row = cursor.fetchone()
            if not row:
                raise RuntimeError("Failed to create budget")
            
            budget_data = {
                "id": row[0],
                "user_id": row[1],
                "category": row[2],
                "limit_amount": float(row[3]),
                "created_at": row[4]
            }
            
            budget = Budget(**budget_data)
            action = "CREATE_BUDGET"

    # Audit log
    log_action(
        user_id=user_id,
        action=action,
        details=f"{category} budget set to {limit}"
    )

    return budget


# -----------------------------
# Get Budget for Category
# -----------------------------
def get_budget(
    user_id: int,
    category: str
) -> Optional[Budget]:
    """
    Fetch budget for a specific category.
    """

    with get_db_cursor(commit=False) as cursor:
        cursor.execute(
            """
            SELECT id, user_id, category, limit_amount, created_at
            FROM budgets
            WHERE user_id = %s AND category = %s
            """,
            (user_id, category)
        )
        
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return Budget(
            id=row[0],
            user_id=row[1],
            category=row[2],
            limit_amount=float(row[3]),
            created_at=row[4]
        )


# -----------------------------
# Get All Budgets for User
# -----------------------------
def get_all_budgets(
    user_id: int
) -> list[Budget]:
    """
    Fetch all budgets for a user.
    """

    with get_db_cursor(commit=False) as cursor:
        cursor.execute(
            """
            SELECT id, user_id, category, limit_amount, created_at
            FROM budgets
            WHERE user_id = %s
            """,
            (user_id,)
        )
        
        rows = cursor.fetchall()
        budgets = []
        for row in rows:
            budgets.append(Budget(
                id=row[0],
                user_id=row[1],
                category=row[2],
                limit_amount=float(row[3]),
                created_at=row[4]
            ))
        
        return budgets


# -----------------------------
# Delete Budget
# -----------------------------
def delete_budget(
    user_id: int,
    category: str
) -> bool:
    """
    Delete a budget for a category.
    """

    with get_db_cursor() as cursor:
        # First find the budget
        cursor.execute(
            """
            SELECT id FROM budgets
            WHERE user_id = %s AND category = %s
            """,
            (user_id, category)
        )
        
        row = cursor.fetchone()
        
        if not row:
            return False

        budget_id = row[0]
        
        # Delete the budget
        cursor.execute(
            """
            DELETE FROM budgets WHERE id = %s
            """,
            (budget_id,)
        )

    # Audit log (outside transaction to avoid issues)
    log_action(
        user_id=user_id,
        action="DELETE_BUDGET",
        details=f"{category} budget deleted"
    )

    return True

