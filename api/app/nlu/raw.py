"""The common shape every parser (LLM or rules) produces, before names are resolved to ids."""

from typing import Literal

from pydantic import BaseModel

Tool = Literal["add_transaction", "set_budget", "query_spending", "clarify", "unsupported"]
Metric = Literal["total", "top_categories", "top_merchants", "budget"]


class RawCommand(BaseModel):
    tool: Tool
    amount: str | None = None  # rupees as text ("180", "1250.50"); never a float
    kind: Literal["expense", "income"] | None = None
    category: str | None = None  # a category name or alias, as the parser understood it
    account: str | None = None
    merchant: str | None = None
    note: str | None = None
    date: str | None = None  # YYYY-MM-DD in the owner's timezone; None means today
    question: str | None = None  # for clarify / unsupported
    # query_spending only. period: today, yesterday, this_week, last_week, this_month,
    # last_month, this_year, last_year, last_<N>_days, or a month as YYYY-MM.
    metric: Metric | None = None
    period: str | None = None
