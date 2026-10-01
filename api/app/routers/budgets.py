from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.auth import CurrentUser
from app.db import get_session
from app.errors import NotFound
from app.models import Budget
from app.schemas import BudgetIn, BudgetOut
from app.services import budgets as service

router = APIRouter(prefix="/budgets", tags=["budgets"])
DB = Annotated[Session, Depends(get_session)]


@router.get("", response_model=list[BudgetOut])
def list_budgets(user: CurrentUser, session: DB) -> list[Budget]:
    return list(session.scalars(select(Budget).where(Budget.user_id == user.id)))


@router.put("/{category_id}", response_model=BudgetOut)
def set_budget(category_id: int, body: BudgetIn, user: CurrentUser, session: DB) -> Budget:
    """Create or replace the monthly budget for a category."""
    budget = service.set_budget(session, user, category_id, body.amount_paise)
    session.commit()
    return budget


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(category_id: int, user: CurrentUser, session: DB) -> None:
    budget = service.find_budget(session, user.id, category_id)
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
