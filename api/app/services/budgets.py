"""Budget writes and alerts. Shared by the budgets API (M1), voice actions (M2) and alerts (M3)."""

from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app import audit
from app.errors import Invalid, get_owned
from app.models import (
    Budget,
    BudgetPeriod,
    Category,
    CategoryKind,
    Transaction,
    TransactionKind,
    User,
)
from app.money import format_inr, percent
from app.schemas import BudgetAlert
from app.timeutil import MONTH_NAMES, current_month, month_bounds


def covered_categories(category_id: int) -> Select[int]:
    """A category and its subcategories: what its budget (or a question about it) covers."""
    return select(Category.id).where(
        or_(Category.id == category_id, Category.parent_id == category_id)
    )


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


def alerts_for(session: Session, user: User, txn: Transaction) -> list[BudgetAlert]:
    """Budgets that this new expense pushed past 80% or 100% for its month."""
    if txn.kind != TransactionKind.EXPENSE or txn.category_id is None:
        return []
    category = session.get(Category, txn.category_id)
    if category is None:
        return []
    month = txn.occurred_at.astimezone(ZoneInfo(user.timezone)).strftime("%Y-%m")
    start, end = month_bounds(month, user.timezone)
    suffix = ""
    if month != current_month(user.timezone):
        suffix = f" for {MONTH_NAMES[int(month[5:]) - 1]}"

    alerts = []
    for budget_category_id in (category.id, category.parent_id):
        if budget_category_id is None:
            continue
        budget = find_budget(session, user.id, budget_category_id)
        if budget is None:
            continue
        after = int(
            session.scalar(
                select(func.coalesce(func.sum(Transaction.amount_paise), 0)).where(
                    Transaction.user_id == user.id,
                    Transaction.kind == TransactionKind.EXPENSE,
                    Transaction.occurred_at >= start,
                    Transaction.occurred_at < end,
                    Transaction.category_id.in_(covered_categories(budget_category_id)),
                )
            )
            or 0
        )
        before = after - txn.amount_paise
        amount = budget.amount_paise
        name = category.name if budget_category_id == category.id else _parent_name(session, budget)
        if after >= amount > before:
            level: Literal["warning", "over"] = "over"
            message = (
                f"You've used all of your {name} budget{suffix}."
                if after == amount
                else f"You're {format_inr(after - amount)} over your {name} budget{suffix}."
            )
        elif after * 5 >= amount * 4 > before * 5:
            level = "warning"
            message = (
                f"You've used {percent(after, amount)}% of your {name} budget{suffix} "
                f"({format_inr(after)} of {format_inr(amount)})."
            )
        else:
            continue
        alerts.append(
            BudgetAlert(
                category_id=budget_category_id,
                name=name,
                level=level,
                spent_paise=after,
                amount_paise=amount,
                message=message,
            )
        )
    return alerts


def _parent_name(session: Session, budget: Budget) -> str:
    parent = session.get(Category, budget.category_id)
    return parent.name if parent else "this"
