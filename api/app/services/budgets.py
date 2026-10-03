"""Budget writes. Shared by the budgets API (M1) and confirmed voice actions (M2)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.errors import Invalid, get_owned
from app.models import Budget, BudgetPeriod, Category, CategoryKind, User


def find_budget(session: Session, user_id: int, category_id: int) -> Budget | None:
    return session.scalar(
        select(Budget).where(
            Budget.user_id == user_id,
            Budget.category_id == category_id,
            Budget.period == BudgetPeriod.MONTHLY,
        )
    )


def set_budget(session: Session, user: User, category_id: int, amount_paise: int) -> Budget:
    """Create or replace the monthly budget for an expense category."""
    category = get_owned(session, Category, category_id, user.id)
    if category.kind != CategoryKind.EXPENSE:
        raise Invalid("Budgets are for expense categories")
    budget = find_budget(session, user.id, category_id)
    before = audit.snapshot(budget) if budget else None
    if budget is None:
        budget = Budget(user_id=user.id, category_id=category_id, amount_paise=amount_paise)
        session.add(budget)
    else:
        budget.amount_paise = amount_paise
    session.flush()
    audit.record(
        session,
        user_id=user.id,
        action="update" if before else "create",
        entity="budget",
        entity_id=budget.id,
        before=before,
        after=audit.snapshot(budget),
    )
    return budget
