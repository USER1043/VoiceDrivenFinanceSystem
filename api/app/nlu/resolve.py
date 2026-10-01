"""Turn a RawCommand (names, rupee text, date words) into concrete ids, paise and times."""

import difflib
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.models import CategoryKind, TransactionKind
from app.money import MAX_AMOUNT_PAISE
from app.nlu.raw import RawCommand
from app.nlu.vocab import VocabAccount, VocabCategory, Vocabulary


class TransactionProposal(BaseModel):
    kind: TransactionKind
    amount_paise: int
    category_id: int | None
    account_id: int
    occurred_at: datetime
    merchant: str | None = None
    note: str | None = None


class BudgetProposal(BaseModel):
    category_id: int
    amount_paise: int


class Understood(BaseModel):
    status: Literal["proposal"] = "proposal"
    tool: Literal["add_transaction", "set_budget"]
    payload: TransactionProposal | BudgetProposal


class NeedsInput(BaseModel):
    status: Literal["clarify", "unsupported"]
    message: str


Resolution = Understood | NeedsInput


def to_paise(amount: str | None) -> int | None:
    if amount is None:
        return None
    cleaned = re.sub(r"[₹,\s]|rs\.?|inr", "", str(amount).lower())
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    paise = int((value * 100).to_integral_value())
    return paise if 0 < paise <= MAX_AMOUNT_PAISE else None


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9& ]+", " ", text.lower()).strip()


def find_category(vocab: Vocabulary, said: str | None, kind: CategoryKind) -> VocabCategory | None:
    """Exact name, "Parent > Child" label, alias, then a close fuzzy match."""
    if not said:
        return None
    wanted = _norm(said.split(">")[-1].split("\u203a")[-1])
    candidates = vocab.of_kind(kind)
    for category in candidates:
        if wanted in (_norm(category.name), _norm(category.label)):
            return category
    for category in candidates:
        if wanted in category.aliases:
            return category
    lookup = {_norm(c.name): c for c in candidates} | {
        alias: c for c in candidates for alias in c.aliases
    }
    close = difflib.get_close_matches(wanted, list(lookup), n=1, cutoff=0.75)
    return lookup[close[0]] if close else None


def find_account(vocab: Vocabulary, said: str | None) -> VocabAccount:
    if said:
        wanted = _norm(said)
        for account in vocab.accounts:
            if wanted in (_norm(account.name), account.kind.value):
                return account
    return vocab.default_account


def _when(raw_date: str | None, now: datetime) -> datetime:
    """Today keeps the current time; past days are logged at noon. Never in the future."""
    if not raw_date:
        return now
    try:
        day = date.fromisoformat(raw_date[:10])
    except ValueError:
        return now
    if day >= now.date():
        return now
    if day < now.date() - timedelta(days=366):
        return now
    return datetime.combine(day, time(12, 0), tzinfo=now.tzinfo)


def resolve(raw: RawCommand, vocab: Vocabulary, now: datetime) -> Resolution:
    if raw.tool in ("clarify", "unsupported"):
        fallback = "Could you say that again?" if raw.tool == "clarify" else "I can't do that yet."
        return NeedsInput(status=raw.tool, message=raw.question or fallback)

    amount = to_paise(raw.amount)

    if raw.tool == "set_budget":
        budget_category = find_category(vocab, raw.category, CategoryKind.EXPENSE)
        if budget_category is None:
            return NeedsInput(status="clarify", message="Which category is the budget for?")
        if amount is None:
            return NeedsInput(
                status="clarify", message=f"How much should the {budget_category.name} budget be?"
            )
        return Understood(
            tool="set_budget",
            payload=BudgetProposal(category_id=budget_category.id, amount_paise=amount),
        )

    if amount is None:
        return NeedsInput(status="clarify", message="How much was it?")
    kind = TransactionKind(raw.kind or "expense")
    category = find_category(vocab, raw.category, CategoryKind(kind.value))
    merchant = (raw.merchant or "").strip()[:120] or None
    note = (raw.note or "").strip()[:1000] or None
    return Understood(
        tool="add_transaction",
        payload=TransactionProposal(
            kind=kind,
            amount_paise=amount,
            category_id=category.id if category else None,
            account_id=find_account(vocab, raw.account).id,
            occurred_at=_when(raw.date, now),
            merchant=merchant,
            note=note,
        ),
    )


def now_in(tz: str) -> datetime:
    return datetime.now(ZoneInfo(tz))
