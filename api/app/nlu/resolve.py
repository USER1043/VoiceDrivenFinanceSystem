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
from app.nlu.raw import Metric, RawCommand
from app.nlu.vocab import VocabAccount, VocabCategory, Vocabulary
from app.timeutil import MONTH_NAMES


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


class SpendingQuery(BaseModel):
    """A read-only question; answered straight away, no confirmation needed."""

    metric: Metric
    kind: TransactionKind
    category_id: int | None = None
    merchant: str | None = None
    account_id: int | None = None
    start: date  # first day, in the owner's timezone
    end: date  # day after the last day
    label: str  # "this month", "last week", "in August"
    month: str | None = None  # YYYY-MM when the range is one calendar month (for budgets)


class Answerable(BaseModel):
    status: Literal["query"] = "query"
    query: SpendingQuery


class NeedsInput(BaseModel):
    status: Literal["clarify", "unsupported"]
    message: str


Resolution = Understood | Answerable | NeedsInput


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


def named_account(vocab: Vocabulary, said: str | None) -> VocabAccount | None:
    if said:
        wanted = _norm(said)
        for account in vocab.accounts:
            if wanted in (_norm(account.name), account.kind.value):
                return account
    return None


def find_account(vocab: Vocabulary, said: str | None) -> VocabAccount:
    return named_account(vocab, said) or vocab.default_account


def _first_of(day: date) -> date:
    return day.replace(day=1)


def _next_month(day: date) -> date:
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1)


def period_range(period: str | None, today: date) -> tuple[date, date, str]:
    """[start, end) dates and a spoken label. Unknown periods mean this month."""
    tomorrow = today + timedelta(days=1)
    monday = today - timedelta(days=today.weekday())
    p = (period or "this_month").strip().lower()
    if p == "today":
        return today, tomorrow, "today"
    if p == "yesterday":
        return today - timedelta(days=1), today, "yesterday"
    if p == "this_week":
        return monday, tomorrow, "this week"
    if p == "last_week":
        return monday - timedelta(days=7), monday, "last week"
    if p == "last_month":
        start = _first_of(_first_of(today) - timedelta(days=1))
        return start, _first_of(today), "last month"
    if p == "this_year":
        return date(today.year, 1, 1), tomorrow, "this year"
    if p == "last_year":
        return date(today.year - 1, 1, 1), date(today.year, 1, 1), "last year"
    if match := re.fullmatch(r"last_(\d{1,3})_days?", p):
        days = int(match[1])
        if days == 1:
            return today, tomorrow, "today"
        if 1 < days <= 366:
            return tomorrow - timedelta(days=days), tomorrow, f"in the last {days} days"
    if match := re.fullmatch(r"(\d{4})-(\d{2})", p):
        year, month = int(match[1]), int(match[2])
        if 1 <= month <= 12 and 2000 <= year <= today.year + 1:
            start = date(year, month, 1)
            if start > today:  # "in December" asked in October means last December
                start = date(year - 1, month, 1)
            if start == _first_of(today):
                return start, _next_month(start), "this month"
            name = MONTH_NAMES[start.month - 1]
            label = f"in {name}" if start.year == today.year else f"in {name} {start.year}"
            return start, _next_month(start), label
    start = _first_of(today)
    return start, _next_month(start), "this month"


def _resolve_query(raw: RawCommand, vocab: Vocabulary, today: date) -> Answerable:
    metric = raw.metric or "total"
    kind = TransactionKind(raw.kind or "expense")
    if metric == "budget":
        kind = TransactionKind.EXPENSE
    category = find_category(vocab, raw.category, CategoryKind(kind.value))
    merchant = (raw.merchant or "").strip()[:120] or None
    if category is None and raw.category and not merchant:
        merchant = raw.category.strip()[:120]  # "how much on dominos": search for it instead
    account = named_account(vocab, raw.account)
    start, end, label = period_range(raw.period, today)
    one_month = start.day == 1 and end == _next_month(start)
    if metric == "budget" and not one_month:
        start = _first_of(today)
        end, label, one_month = _next_month(start), "this month", True
    return Answerable(
        query=SpendingQuery(
            metric=metric,
            kind=kind,
            category_id=category.id if category else None,
            merchant=merchant if metric != "budget" else None,
            account_id=account.id if account else None,
            start=start,
            end=end,
            label=label,
            month=start.strftime("%Y-%m") if one_month else None,
        )
    )


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

    if raw.tool == "query_spending":
        return _resolve_query(raw, vocab, now.date())

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
