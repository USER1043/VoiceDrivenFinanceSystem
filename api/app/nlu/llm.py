"""LLM command parsing through OpenAI-compatible chat completions with tool calling.

Groq and Gemini both expose this API, so one client serves both. The model may only answer
by calling one of the tools below; anything else is treated as a failure and the next
provider (ultimately the rule parser) takes over. Only the utterance and the category and
account names are sent: no amounts, balances or history. Questions are answered from the
database afterwards, so the model never sees the numbers.
"""

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.models import CategoryKind
from app.nlu.raw import RawCommand
from app.nlu.vocab import Vocabulary


class ProviderError(Exception):
    pass


def _tools(vocab: Vocabulary) -> list[dict[str, Any]]:
    expense = sorted({c.name for c in vocab.of_kind(CategoryKind.EXPENSE)})
    income = sorted({c.name for c in vocab.of_kind(CategoryKind.INCOME)})
    accounts = [a.name for a in vocab.accounts]
    amount = {
        "type": "string",
        "description": "Amount in rupees as digits, e.g. '180' or '1250.50'. 'k' = thousand, "
        "'lakh' = 100000, so '1.5k' -> '1500'.",
    }

    def fn(
        name: str, description: str, props: dict[str, Any], required: list[str]
    ) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                    "additionalProperties": False,
                },
            },
        }

    return [
        fn(
            "add_transaction",
            "Record money spent (expense) or received (income).",
            {
                "amount": amount,
                "kind": {"type": "string", "enum": ["expense", "income"]},
                "category": {
                    "type": "string",
                    "description": "Best matching category name, or empty if none fits. "
                    f"Expense: {', '.join(expense)}. Income: {', '.join(income)}.",
                },
                "account": {
                    "type": "string",
                    "description": f"One of {', '.join(accounts)} if the user said how they "
                    "paid (gpay/phonepe/paytm/scan = UPI); otherwise empty.",
                },
                "merchant": {
                    "type": "string",
                    "description": "Shop, app or person paid or received from, if said.",
                },
                "date": {
                    "type": "string",
                    "description": "YYYY-MM-DD if the user named a day (yesterday, Monday); "
                    "otherwise empty for today.",
                },
            },
            ["amount", "kind", "category", "account", "merchant", "date"],
        ),
        fn(
            "set_budget",
            "Set the monthly spending limit for an expense category.",
            {
                "category": {"type": "string", "description": f"One of: {', '.join(expense)}."},
                "amount": amount,
            },
            ["category", "amount"],
        ),
        fn(
            "query_spending",
            "Answer a question about past spending or income, or how a budget is doing.",
            {
                "metric": {
                    "type": "string",
                    "enum": ["total", "top_categories", "top_merchants", "budget"],
                    "description": "total: how much; top_categories: where the money went; "
                    "top_merchants: which shops/apps/people; budget: how much budget is left.",
                },
                "kind": {
                    "type": "string",
                    "enum": ["expense", "income"],
                    "description": "income for earnings/received money, otherwise expense.",
                },
                "category": {
                    "type": "string",
                    "description": "Category name if the question is about one, else empty.",
                },
                "merchant": {
                    "type": "string",
                    "description": "Shop, app or person if asked about one that is not a "
                    "category word, else empty.",
                },
                "account": {
                    "type": "string",
                    "description": f"One of {', '.join(accounts)} if asked, else empty.",
                },
                "period": {
                    "type": "string",
                    "description": "One of today, yesterday, this_week, last_week, this_month, "
                    "last_month, this_year, last_year, last_<N>_days (e.g. last_7_days), or a "
                    "month as YYYY-MM (the most recent one not in the future). Empty means "
                    "this month.",
                },
            },
            ["metric", "kind", "category", "merchant", "account", "period"],
        ),
        fn(
            "clarify",
            "Ask one short question when the amount (or a budget's category) is missing.",
            {"question": {"type": "string"}},
            ["question"],
        ),
        fn(
            "unsupported",
            "Anything else: small talk, account balances, advice, other topics.",
            {"reason": {"type": "string"}},
            ["reason"],
        ),
    ]


def _system_prompt(vocab: Vocabulary, today: date) -> str:
    aliases = "; ".join(f"{c.name}: {', '.join(c.aliases)}" for c in vocab.categories if c.aliases)
    return (
        "You convert one short spoken note or question from a user in India into exactly "
        "one tool call. "
        "Currency is INR. Speech-to-text may contain small errors; use common sense. "
        f"Today is {today:%A, %Y-%m-%d}. "
        "Paying staff (maid, driver) is an expense even if called salary. "
        f"Words the user uses for categories: {aliases}."
    )


def _blank(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def to_raw(name: str, args: dict[str, Any]) -> RawCommand:
    if name == "add_transaction":
        return RawCommand(
            tool="add_transaction",
            amount=_blank(args.get("amount")),
            kind="income" if args.get("kind") == "income" else "expense",
            category=_blank(args.get("category")),
            account=_blank(args.get("account")),
            merchant=_blank(args.get("merchant")),
            date=_blank(args.get("date")),
        )
    if name == "set_budget":
        return RawCommand(
            tool="set_budget",
            category=_blank(args.get("category")),
            amount=_blank(args.get("amount")),
        )
    if name == "query_spending":
        metric = args.get("metric")
        return RawCommand(
            tool="query_spending",
            metric=metric if metric in ("top_categories", "top_merchants", "budget") else "total",
            kind="income" if args.get("kind") == "income" else "expense",
            category=_blank(args.get("category")),
            merchant=_blank(args.get("merchant")),
            account=_blank(args.get("account")),
            period=_blank(args.get("period")),
        )
    if name == "clarify":
        return RawCommand(tool="clarify", question=_blank(args.get("question")))
    if name == "unsupported":
        return RawCommand(
            tool="unsupported",
            question="I can log spending and answer questions like "
            "“how much did I spend on food this month?”",
        )
    raise ProviderError(f"unknown tool {name!r}")


@dataclass
class LLMProvider:
    name: str
    base_url: str
    api_key: str
    model: str
    timeout: float
    transport: httpx.BaseTransport | None = None  # injected in tests

    def parse(self, text: str, vocab: Vocabulary, today: date) -> RawCommand:
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": _system_prompt(vocab, today)},
                {"role": "user", "content": text},
            ],
            "tools": _tools(vocab),
            "tool_choice": "required",
        }
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=body,
                )
            response.raise_for_status()
            call = response.json()["choices"][0]["message"]["tool_calls"][0]["function"]
            args = json.loads(call["arguments"] or "{}")
            if not isinstance(args, dict):
                raise ProviderError("tool arguments are not an object")
            return to_raw(call["name"], args)
        except ProviderError:
            raise
        except (
            httpx.HTTPError,
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            ValidationError,
        ) as exc:
            # Never include the response body: it may echo the request.
            raise ProviderError(f"{self.name}: {type(exc).__name__}") from exc


def provider_from_settings(settings: Settings, name: str) -> LLMProvider | None:
    if name == "groq" and settings.groq_api_key:
        return LLMProvider(
            "groq",
            settings.groq_base_url,
            settings.groq_api_key,
            settings.groq_llm_model,
            settings.ai_timeout_seconds,
        )
    if name == "gemini" and settings.gemini_api_key:
        return LLMProvider(
            "gemini",
            settings.gemini_base_url,
            settings.gemini_api_key,
            settings.gemini_llm_model,
            settings.ai_timeout_seconds,
        )
    return None


def configured_providers(settings: Settings) -> list[LLMProvider]:
    return [p for name in ("groq", "gemini") if (p := provider_from_settings(settings, name))]
