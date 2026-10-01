from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.auth import CurrentUser
from app.db import get_session
from app.errors import Invalid, NotFound, get_owned
from app.models import Budget, BudgetPeriod, Category, CategoryKind
from app.schemas import BudgetIn, BudgetOut

router = APIRouter(prefix="/budgets", tags=["budgets"])
DB = Annotated[Session, Depends(get_session)]


def _find(session: Session, user_id: int, category_id: int) -> Budget | None:
    return session.scalar(
        select(Budget).where(
            Budget.user_id == user_id,
            Budget.category_id == category_id,
            Budget.period == BudgetPeriod.MONTHLY,
        )
    )


@router.get("", response_model=list[BudgetOut])
def list_budgets(user: CurrentUser, session: DB) -> list[Budget]:
    return list(session.scalars(select(Budget).where(Budget.user_id == user.id)))


@router.put("/{category_id}", response_model=BudgetOut)
def set_budget(category_id: int, body: BudgetIn, user: CurrentUser, session: DB) -> Budget:
    """Create or replace the monthly budget for a category."""
    category = get_owned(session, Category, category_id, user.id)
    if category.kind != CategoryKind.EXPENSE:
        raise Invalid("Budgets are for expense categories")
    budget = _find(session, user.id, category_id)
    before = audit.snapshot(budget) if budget else None
    if budget is None:
        budget = Budget(user_id=user.id, category_id=category_id, amount_paise=body.amount_paise)
        session.add(budget)
    else:
        budget.amount_paise = body.amount_paise
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
    session.commit()
    return budget


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(category_id: int, user: CurrentUser, session: DB) -> None:
    budget = _find(session, user.id, category_id)
    if budget is None:
        raise NotFound(f"No budget for category {category_id}")
    audit.record(
        session,
        user_id=user.id,
        action="delete",
        entity="budget",
        entity_id=budget.id,
        before=audit.snapshot(budget),
    )
    session.delete(budget)
    session.commit()
