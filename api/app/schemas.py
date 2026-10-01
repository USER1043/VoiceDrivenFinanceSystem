"""Request and response bodies. Amounts are always integer paise."""

from datetime import date, datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.models import AccountKind, CategoryKind, TransactionKind, TransactionSource
from app.money import MAX_AMOUNT_PAISE

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Merchant = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
Paise = Annotated[int, Field(gt=0, le=MAX_AMOUNT_PAISE)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Accounts ----------


class AccountOut(ORM):
    id: int
    name: str
    kind: AccountKind
    is_default: bool
    archived: bool


class AccountIn(BaseModel):
    name: Name
    kind: AccountKind
    is_default: bool = False


class AccountPatch(BaseModel):
    name: Name | None = None
    kind: AccountKind | None = None
    is_default: bool | None = None
    archived: bool | None = None


# ---------- Categories ----------


def _normalise_aliases(aliases: list[str]) -> list[str]:
    seen: list[str] = []
    for alias in aliases:
        cleaned = " ".join(alias.lower().split())
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


Aliases = Annotated[list[Annotated[str, StringConstraints(max_length=40)]], Field(max_length=50)]


class CategoryOut(ORM):
    id: int
    name: str
    kind: CategoryKind
    parent_id: int | None
    aliases: list[str]
    archived: bool


class CategoryIn(BaseModel):
    name: Name
    kind: CategoryKind
    parent_id: int | None = None
    aliases: Aliases = []

    _aliases = field_validator("aliases")(_normalise_aliases)


class CategoryPatch(BaseModel):
    """Only fields that are sent are changed; send `parent_id: null` to make it top-level."""

    name: Name | None = None
    parent_id: int | None = None
    aliases: Aliases | None = None
    archived: bool | None = None

    @field_validator("aliases")
    @classmethod
    def _aliases(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _normalise_aliases(value)


# ---------- Transactions ----------


class TransactionOut(ORM):
    id: int
    kind: TransactionKind
    amount_paise: int
    occurred_at: datetime
    account_id: int
    category_id: int | None
    merchant: str | None
    note: str | None
    source: TransactionSource


class TransactionIn(BaseModel):
    kind: TransactionKind = TransactionKind.EXPENSE
    amount_paise: Paise
    occurred_at: AwareDatetime
    account_id: int
    category_id: int | None = None
    merchant: Merchant | None = None
    note: Note | None = None


class TransactionPatch(BaseModel):
    """Only fields that are sent are changed; send `category_id: null` to uncategorise."""

    kind: TransactionKind | None = None
    amount_paise: Paise | None = None
    occurred_at: AwareDatetime | None = None
    account_id: int | None = None
    category_id: int | None = None
    merchant: Merchant | None = None
    note: Note | None = None


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int


# ---------- Budgets ----------


class BudgetOut(ORM):
    category_id: int
    amount_paise: int


class BudgetIn(BaseModel):
    amount_paise: Paise


# ---------- Summary ----------


class CategorySpend(BaseModel):
    category_id: int | None
    name: str
    spent_paise: int


class BudgetStatus(BaseModel):
    category_id: int
    name: str
    amount_paise: int
    spent_paise: int


class DailySpend(BaseModel):
    day: date
    expense_paise: int


class Summary(BaseModel):
    month: str
    income_paise: int
    expense_paise: int
    previous_expense_paise: int
    by_category: list[CategorySpend]
    budgets: list[BudgetStatus]
    daily: list[DailySpend]
