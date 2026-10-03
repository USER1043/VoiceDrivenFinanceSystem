import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.models import CategoryKind
from app.money import format_inr
from app.nlu import rules
from app.nlu.llm import LLMProvider, ProviderError
from app.nlu.pipeline import understand
from app.nlu.raw import RawCommand
from app.nlu.resolve import (
    Answerable,
    NeedsInput,
    Understood,
    find_category,
    period_range,
    resolve,
    to_paise,
)
from app.nlu.vocab import Vocabulary
from evals.run import evaluate

VOCAB = Vocabulary.from_seed()
NOW = datetime(2026, 10, 1, 18, 30, tzinfo=ZoneInfo("Asia/Kolkata"))


def test_rule_parser_meets_the_eval_bar():
    outcomes = evaluate(rules.parse)
    failures = [o.case["text"] for o in outcomes if not o.passed]
    accuracy = 1 - len(failures) / len(outcomes)
    assert accuracy >= 0.95, f"{accuracy:.0%}; failing: {failures}"


@pytest.mark.parametrize(
    ("text", "paise"),
    [("180", 18000), ("1,250.50", 125050), ("₹99", 9900), ("Rs. 40", 4000), ("0.295", 30)],
)
def test_to_paise(text, paise):
    assert to_paise(text) == paise


@pytest.mark.parametrize("text", [None, "", "abc", "0", "-5", "100000000000"])
def test_to_paise_rejects(text):
    assert to_paise(text) is None


@pytest.mark.parametrize(
    ("said", "expected"),
    [
        ("Groceries", "Groceries"),
        ("food > groceries", "Groceries"),
        ("Food \u203a Groceries", "Groceries"),
        ("grocery", "Groceries"),  # fuzzy
        ("chai", "Tea & snacks"),  # alias
        ("spaceships", None),
    ],
)
def test_find_category(said, expected):
    found = find_category(VOCAB, said, CategoryKind.EXPENSE)
    assert (found.name if found else None) == expected


def test_resolve_clamps_future_dates_and_defaults_account():
    raw = RawCommand(tool="add_transaction", amount="50", kind="expense", date="2026-10-05")
    result = resolve(raw, VOCAB, NOW)
    assert isinstance(result, Understood)
    assert result.payload.occurred_at == NOW
    assert result.payload.account_id == VOCAB.default_account.id


def test_resolve_past_day_is_logged_at_noon():
    raw = RawCommand(tool="add_transaction", amount="50", date="2026-09-28")
    result = resolve(raw, VOCAB, NOW)
    assert result.payload.occurred_at == datetime(2026, 9, 28, 12, tzinfo=NOW.tzinfo)


def test_missing_amount_asks():
    result = resolve(RawCommand(tool="add_transaction", category="Fuel"), VOCAB, NOW)
    assert result == NeedsInput(status="clarify", message="How much was it?")


def test_format_inr():
    assert format_inr(12345650) == "₹1,23,456.50"
    assert format_inr(18000) == "₹180"


# ---------- LLM provider (HTTP mocked) ----------


def _provider(handler):
    return LLMProvider(
        "groq", "https://llm.test/v1", "sk-test", "model-x", 5, httpx.MockTransport(handler)
    )


def _tool_response(name, args):
    call = {"function": {"name": name, "arguments": json.dumps(args)}}
    return httpx.Response(200, json={"choices": [{"message": {"tool_calls": [call]}}]})


def test_llm_tool_call_becomes_raw_command():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return _tool_response(
            "add_transaction",
            {"amount": "450", "kind": "expense", "category": "Eating out", "account": "",
             "merchant": "Swiggy", "date": ""},
        )  # fmt: skip

    raw = _provider(handler).parse("swiggy 450", VOCAB, NOW.date())
    assert raw == RawCommand(
        tool="add_transaction",
        amount="450",
        kind="expense",
        category="Eating out",
        merchant="Swiggy",
    )
    assert seen["auth"] == "Bearer sk-test"
    body = seen["body"]
    assert body["tool_choice"] == "required"
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert body["messages"][1]["content"] == "swiggy 450"  # only the utterance is sent
    assert {t["function"]["name"] for t in body["tools"]} == {
        "add_transaction", "set_budget", "query_spending", "clarify", "unsupported"
    }  # fmt: skip


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(429, json={"error": "rate limited"}),
        httpx.Response(200, json={"choices": [{"message": {"content": "sure!"}}]}),
        httpx.Response(200, text="not json"),
    ],
    ids=["http-error", "no-tool-call", "garbage"],
)
def test_llm_failures_raise_provider_error(response):
    with pytest.raises(ProviderError):
        _provider(lambda request: response).parse("chai 20", VOCAB, NOW.date())


def test_pipeline_falls_back_to_rules_when_llm_fails():
    broken = _provider(lambda request: httpx.Response(500))
    result, parser = understand("chai 20 cash", VOCAB, NOW, [broken])
    assert parser == "rules"
    assert isinstance(result, Understood)
    assert result.payload.amount_paise == 2000


def test_pipeline_prefers_llm():
    llm = _provider(
        lambda request: _tool_response("set_budget", {"category": "Food", "amount": "6000"})
    )
    result, parser = understand("keep food under six grand", VOCAB, NOW, [llm])
    assert parser == "groq"
    assert result.tool == "set_budget"
    assert result.payload.amount_paise == 600000


def test_pipeline_overrides_an_overcautious_refusal():
    refusing = _provider(lambda request: _tool_response("unsupported", {"reason": "unclear"}))
    result, parser = understand("chai 20", VOCAB, NOW, [refusing])
    assert parser == "rules"
    assert isinstance(result, Understood)


def test_questions_become_queries():
    raw = rules.parse("how much did I spend on food last week?", VOCAB, date(2026, 10, 1))
    assert (raw.tool, raw.metric, raw.category, raw.period) == (
        "query_spending",
        "total",
        "Food",
        "last_week",
    )
    raw = rules.parse("total spending in the last 7 days", VOCAB, date(2026, 10, 1))
    assert (raw.tool, raw.period) == ("query_spending", "last_7_days")
    assert rules.parse("what's my balance?", VOCAB, date(2026, 10, 1)).tool == "unsupported"


@pytest.mark.parametrize(
    ("period", "start", "end", "label"),
    [
        (None, date(2026, 10, 1), date(2026, 11, 1), "this month"),
        ("today", date(2026, 10, 7), date(2026, 10, 8), "today"),
        ("this_week", date(2026, 10, 5), date(2026, 10, 8), "this week"),
        ("last_week", date(2026, 9, 28), date(2026, 10, 5), "last week"),
        ("last_month", date(2026, 9, 1), date(2026, 10, 1), "last month"),
        ("last_30_days", date(2026, 9, 8), date(2026, 10, 8), "in the last 30 days"),
        ("2026-08", date(2026, 8, 1), date(2026, 9, 1), "in August"),
        ("2026-12", date(2025, 12, 1), date(2026, 1, 1), "in December 2025"),
        ("2026-10", date(2026, 10, 1), date(2026, 11, 1), "this month"),
        ("nonsense", date(2026, 10, 1), date(2026, 11, 1), "this month"),
    ],
)
def test_period_range(period, start, end, label):
    assert period_range(period, date(2026, 10, 7)) == (start, end, label)  # a Wednesday


def test_llm_query_tool_resolves_to_a_question():
    llm = _provider(
        lambda request: _tool_response(
            "query_spending",
            {
                "metric": "top_categories",
                "kind": "expense",
                "category": "",
                "merchant": "",
                "account": "",
                "period": "2026-08",
            },
        )
    )
    result, parser = understand("where did my money go in august", VOCAB, NOW, [llm])
    assert parser == "groq"
    assert isinstance(result, Answerable)
    assert result.query.metric == "top_categories"
    assert (result.query.start, result.query.end) == (date(2026, 8, 1), date(2026, 9, 1))
    assert result.query.month == "2026-08"


def test_unknown_category_in_a_question_searches_merchants():
    raw = RawCommand(tool="query_spending", category="ramesh")
    result = resolve(raw, VOCAB, NOW)
    assert isinstance(result, Answerable)
    assert (result.query.category_id, result.query.merchant) == (None, "ramesh")
