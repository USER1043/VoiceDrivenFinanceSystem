"""Answers to spending questions. Read-only: computed from the database, never by the LLM."""

from dataclasses import dataclass, field
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.models import Account, Budget, Category, Transaction, TransactionKind, User
from app.money import format_inr, percent
from app.nlu.resolve import SpendingQuery
from app.services.budgets import covered_categories

TOP_N = 5


@dataclass
class AnswerItem:
    label: str
    amount_paise: int
    limit_paise: int | None = None  # a budget's amount, for budget answers


@dataclass
class Answer:
    message: str
    total_paise: int | None = None
    items: list[AnswerItem] = field(default_factory=list)


def _join(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"


def _sentence_start(label: str) -> str:
    return label[0].upper() + label[1:]


class _Asker:
    def __init__(self, session: Session, user: User, query: SpendingQuery) -> None:
        self.session = session
        self.user = user
        self.q = query
        self.categories = {
            c.id: c for c in session.scalars(select(Category).where(Category.user_id == user.id))
        }

    def conditions(self, *, with_category: bool = True) -> list[ColumnElement[bool]]:
        zone = ZoneInfo(self.user.timezone)
        q = self.q
        where = [
            Transaction.user_id == self.user.id,
            Transaction.kind == q.kind,
            Transaction.occurred_at >= datetime.combine(q.start, time(), zone),
            Transaction.occurred_at < datetime.combine(q.end, time(), zone),
        ]
        if with_category and q.category_id is not None:
            where.append(Transaction.category_id.in_(covered_categories(q.category_id)))
        if q.merchant:
            escaped = q.merchant.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            where.append(or_(Transaction.merchant.ilike(pattern), Transaction.note.ilike(pattern)))
        if q.account_id is not None:
            where.append(Transaction.account_id == q.account_id)
        return where

    def total(self) -> tuple[int, int]:
        amount, count = self.session.execute(
            select(func.coalesce(func.sum(Transaction.amount_paise), 0), func.count()).where(
                *self.conditions()
            )
        ).one()
        return int(amount), int(count)

    def by_category(self) -> list[AnswerItem]:
        """Top-level categories, or the subcategories when asked about one category."""
        rows = self.session.execute(
            select(Transaction.category_id, func.sum(Transaction.amount_paise))
            .where(*self.conditions())
            .group_by(Transaction.category_id)
        ).all()
        rollup: dict[int | None, int] = {}
        for category_id, amount in rows:
            key = category_id
            if key is not None and self.q.category_id is None:
                key = self.categories[key].parent_id or key
            rollup[key] = rollup.get(key, 0) + int(amount)
        items = [
            AnswerItem(self.categories[key].name if key is not None else "Uncategorised", amount)
            for key, amount in rollup.items()
        ]
        return sorted(items, key=lambda i: i.amount_paise, reverse=True)[:TOP_N]

    def by_merchant(self) -> list[AnswerItem]:
        name = func.lower(func.trim(Transaction.merchant))
        rows = self.session.execute(
            select(func.min(Transaction.merchant), func.sum(Transaction.amount_paise))
            .where(*self.conditions(), Transaction.merchant.is_not(None))
            .group_by(name)
            .order_by(func.sum(Transaction.amount_paise).desc())
            .limit(TOP_N)
        ).all()
        return [AnswerItem(merchant or "", int(amount)) for merchant, amount in rows]

    def filters(self) -> str:
        """Spoken filters: ' on Food at Swiggy using Cash', or ' as Salary' for income."""
        q = self.q
        income = q.kind == TransactionKind.INCOME
        parts = []
        if q.category_id is not None:
            parts.append(f"{'as' if income else 'on'} {self.categories[q.category_id].name}")
        if q.merchant:
            parts.append(f"{'from' if income else 'at'} {q.merchant}")
        if q.account_id is not None:
            account = self.session.get(Account, q.account_id)
            if account is not None:
                parts.append(f"{'into' if income else 'using'} {account.name}")
        return "".join(f" {p}" for p in parts)

    def budget_for(self, category_id: int) -> tuple[Budget, Category] | None:
        category = self.categories[category_id]
        for candidate in (category, self.categories.get(category.parent_id or -1)):
            if candidate is None:
                continue
            budget = self.session.scalar(
                select(Budget).where(
                    Budget.user_id == self.user.id, Budget.category_id == candidate.id
                )
            )
            if budget is not None:
                return budget, candidate
        return None

    def spent_in(self, category_id: int) -> int:
        where = self.conditions(with_category=False)
        return int(
            self.session.scalar(
                select(func.coalesce(func.sum(Transaction.amount_paise), 0)).where(
                    *where, Transaction.category_id.in_(covered_categories(category_id))
                )
            )
            or 0
        )


def _budget_line(name: str, spent: int, amount: int) -> str:
    if spent > amount:
        return f"{name}: {format_inr(spent - amount)} over"
    return f"{name}: {format_inr(amount - spent)} left"


def _answer_total(ask: _Asker) -> Answer:
    q = ask.q
    amount, count = ask.total()
    where = ask.filters()
    if q.kind == TransactionKind.INCOME:
        if not count:
            return Answer(f"You haven't received anything{where} {q.label}.", 0)
        return Answer(f"You received {format_inr(amount)}{where} {q.label}.", amount)
    if not count:
        return Answer(f"You haven't spent anything{where} {q.label}.", 0)
    message = f"You spent {format_inr(amount)}{where} {q.label}"
    message += f", across {count} payments." if count > 1 else "."
    if q.category_id is not None and q.month and not q.merchant and q.account_id is None:
        found = ask.budget_for(q.category_id)
        if found and found[1].id == q.category_id:
            budget = found[0]
            message += (
                f" That's {percent(amount, budget.amount_paise)}% of your "
                f"{format_inr(budget.amount_paise)} budget."
            )
    has_children = q.category_id is not None and any(
        c.parent_id == q.category_id for c in ask.categories.values()
    )
    items = ask.by_category() if (q.category_id is None or has_children) and not q.merchant else []
    return Answer(message, amount, items if len(items) > 1 else [])


def _answer_top(ask: _Asker, merchants: bool) -> Answer:
    q = ask.q
    items = ask.by_merchant() if merchants else ask.by_category()
    income = q.kind == TransactionKind.INCOME
    if not items:
        if merchants:
            return Answer(
                f"No shop or app names were recorded{ask.filters()} {q.label}. "
                "Say “at Swiggy” or similar when logging to track them."
            )
        verb = "received anything" if income else "spent anything"
        return Answer(f"You haven't {verb}{ask.filters()} {q.label}.")
    named = [f"{i.label} ({format_inr(i.amount_paise)})" for i in items[:3]]
    if merchants:
        lead = "you received the most from" if income else "you spent the most at"
    else:
        lead = "most came from" if income else "most went on"
        if len(items) == 1:
            lead = "it all came from" if income else "it all went on"
    rest = f", then {_join(named[1:])}" if len(named) > 1 else ""
    return Answer(f"{_sentence_start(q.label)}, {lead} {named[0]}{rest}.", items=items)


def _answer_budget(ask: _Asker) -> Answer:
    q = ask.q
    label = _sentence_start(q.label)
    if q.category_id is not None:
        found = ask.budget_for(q.category_id)
        name = ask.categories[q.category_id].name
        if found is None:
            return Answer(
                f"You haven't set a {name} budget. Try “set {name.lower()} budget to 5000”."
            )
        budget, category = found
        spent = ask.spent_in(category.id)
        amount = budget.amount_paise
        tail = (
            f"{format_inr(spent - amount)} over"
            if spent > amount
            else f"{format_inr(amount - spent)} left"
        )
        return Answer(
            f"{label}, you've used {format_inr(spent)} of your {format_inr(amount)} "
            f"{category.name} budget ({percent(spent, amount)}%): {tail}.",
            spent,
            [AnswerItem(category.name, spent, amount)],
        )

    budgets = ask.session.scalars(select(Budget).where(Budget.user_id == ask.user.id)).all()
    if not budgets:
        return Answer("You haven't set any budgets yet. Try “set food budget to 5000”.")
    items = [
        AnswerItem(ask.categories[b.category_id].name, ask.spent_in(b.category_id), b.amount_paise)
        for b in budgets
    ]
    items.sort(key=lambda i: i.amount_paise / (i.limit_paise or 1), reverse=True)
    over = sum(1 for i in items if i.amount_paise > (i.limit_paise or 0))
    close = sum(1 for i in items if (i.limit_paise or 0) * 4 <= i.amount_paise * 5) - over
    lines = [_budget_line(i.label, i.amount_paise, i.limit_paise or 0) for i in items[:3]]
    if len(items) == 1:
        summary = "your budget is over" if over else "your budget is close to its limit"
        summary = summary if over or close else "your budget is on track"
    elif over:
        summary = f"{over} of {len(items)} budgets are over"
    elif close:
        summary = f"{close} of {len(items)} budgets are close to their limit"
    else:
        summary = f"all {len(items)} budgets are on track"
    return Answer(f"{label}, {summary}. {'. '.join(lines)}.", items=items)


def answer(session: Session, user: User, query: SpendingQuery) -> Answer:
    ask = _Asker(session, user, query)
    if query.metric == "budget":
        return _answer_budget(ask)
    if query.metric in ("top_categories", "top_merchants"):
        return _answer_top(ask, merchants=query.metric == "top_merchants")
    return _answer_total(ask)
