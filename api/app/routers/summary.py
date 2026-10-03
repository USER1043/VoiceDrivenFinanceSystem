from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.db import get_session
from app.models import Budget, Category, Transaction, TransactionKind, User
from app.schemas import BudgetStatus, CategorySpend, DailySpend, Summary
from app.timeutil import (
    MONTH_PATTERN,
    current_month,
    days_in_month,
    month_bounds,
    month_start,
    previous_month,
)

router = APIRouter(prefix="/summary", tags=["summary"])
DB = Annotated[Session, Depends(get_session)]


def _expense_by_category(session: Session, user: User, month: str) -> dict[int | None, int]:
    start, end = month_bounds(month, user.timezone)
    rows = session.execute(
        select(Transaction.category_id, func.sum(Transaction.amount_paise))
        .where(
            Transaction.user_id == user.id,
            Transaction.kind == TransactionKind.EXPENSE,
            Transaction.occurred_at >= start,
            Transaction.occurred_at < end,
        )
        .group_by(Transaction.category_id)
    )
    return {category_id: int(total) for category_id, total in rows}


@router.get("", response_model=Summary)
def summary(
    user: CurrentUser,
    session: DB,
    month: Annotated[str | None, Query(pattern=MONTH_PATTERN)] = None,
) -> Summary:
    """Everything the dashboard needs for one month, in four queries."""
    month = month or current_month(user.timezone)
    start, end = month_bounds(month, user.timezone)

    totals = dict(
        session.execute(
            select(Transaction.kind, func.sum(Transaction.amount_paise))
            .where(
                Transaction.user_id == user.id,
                Transaction.occurred_at >= start,
                Transaction.occurred_at < end,
            )
            .group_by(Transaction.kind)
        ).all()
    )
    spent = _expense_by_category(session, user, month)
    previous = sum(_expense_by_category(session, user, previous_month(month)).values())

    categories = {
        c.id: c for c in session.scalars(select(Category).where(Category.user_id == user.id))
    }

    def top_level(category_id: int | None) -> int | None:
        if category_id is None:
            return None
        parent_id = categories[category_id].parent_id
        return parent_id if parent_id is not None else category_id

    rollup: dict[int | None, int] = {}
    for category_id, amount in spent.items():
        key = top_level(category_id)
        rollup[key] = rollup.get(key, 0) + amount
    by_category = sorted(
        (
            CategorySpend(
                category_id=key,
                name=categories[key].name if key is not None else "Uncategorised",
                spent_paise=amount,
            )
            for key, amount in rollup.items()
        ),
        key=lambda c: c.spent_paise,
        reverse=True,
    )

    budgets = []
    for budget in session.scalars(select(Budget).where(Budget.user_id == user.id)):
        category = categories[budget.category_id]
        covered = {
            cid for cid, c in categories.items() if cid == category.id or c.parent_id == category.id
        }
        budgets.append(
            BudgetStatus(
                category_id=category.id,
                name=category.name,
                amount_paise=budget.amount_paise,
                spent_paise=sum(amount for cid, amount in spent.items() if cid in covered),
            )
        )
    budgets.sort(key=lambda b: b.spent_paise / b.amount_paise, reverse=True)

    local_day = func.date(func.timezone(user.timezone, Transaction.occurred_at))
    per_day: dict[date, int] = {
        day: int(total)
        for day, total in session.execute(
            select(local_day, func.sum(Transaction.amount_paise))
            .where(
                Transaction.user_id == user.id,
                Transaction.kind == TransactionKind.EXPENSE,
                Transaction.occurred_at >= start,
                Transaction.occurred_at < end,
            )
            .group_by(local_day)
        )
    }
    first = month_start(month)
    daily = [
        DailySpend(day=day, expense_paise=per_day.get(day, 0))
        for day in (first + timedelta(days=i) for i in range(days_in_month(month)))
    ]

    return Summary(
        month=month,
        income_paise=int(totals.get(TransactionKind.INCOME, 0)),
        expense_paise=int(totals.get(TransactionKind.EXPENSE, 0)),
        previous_expense_paise=previous,
        by_category=by_category,
        budgets=budgets,
        daily=daily,
    )
