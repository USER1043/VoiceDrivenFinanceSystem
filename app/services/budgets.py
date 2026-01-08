from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional

from app.db.models import Budget
from app.audit.logger import log_action


# -----------------------------
# Create or Update Budget
# -----------------------------
def set_budget(
    db: Session,
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

    existing_budget = (
        db.query(Budget)
        .filter(Budget.user_id == user_id, Budget.category == category)
        .first()
    )

    if existing_budget:
        existing_budget.limit = limit
        action = "UPDATE_BUDGET"
        budget = existing_budget
    else:
        budget = Budget(
            user_id=user_id,
            category=category,
            limit=limit
        )
        db.add(budget)
        action = "CREATE_BUDGET"

    try:
        db.commit()
        db.refresh(budget)
    except IntegrityError:
        db.rollback()
        raise RuntimeError("Failed to set budget")

    # Audit log
    log_action(
        db=db,
        user_id=user_id,
        action=action,
        details=f"{category} budget set to {limit}"
    )

    return budget


# -----------------------------
# Get Budget for Category
# -----------------------------
def get_budget(
    db: Session,
    user_id: int,
    category: str
) -> Optional[Budget]:
    """
    Fetch budget for a specific category.
    """

    return (
        db.query(Budget)
        .filter(Budget.user_id == user_id, Budget.category == category)
        .first()
    )


# -----------------------------
# Get All Budgets for User
# -----------------------------
def get_all_budgets(
    db: Session,
    user_id: int
) -> list[Budget]:
    """
    Fetch all budgets for a user.
    """

    return (
        db.query(Budget)
        .filter(Budget.user_id == user_id)
        .all()
    )


# -----------------------------
# Delete Budget
# -----------------------------
def delete_budget(
    db: Session,
    user_id: int,
    category: str
) -> bool:
    """
    Delete a budget for a category.
    """

    budget = (
        db.query(Budget)
        .filter(Budget.user_id == user_id, Budget.category == category)
        .first()
    )

    if not budget:
        return False

    db.delete(budget)
    db.commit()

    # Audit log
    log_action(
        db=db,
        user_id=user_id,
        action="DELETE_BUDGET",
        details=f"{category} budget deleted"
    )

    return True
