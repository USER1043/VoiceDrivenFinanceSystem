"""Score a parser against evals/commands.jsonl.

    uv run python -m evals.run                 # offline rule parser
    uv run python -m evals.run --provider groq # needs GROQ_API_KEY
    uv run python -m evals.run --provider gemini

Each case lists only the fields it cares about; a case passes when all of them match.
"""

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from app.nlu.raw import RawCommand
from app.nlu.resolve import (
    Answerable,
    BudgetProposal,
    TransactionProposal,
    Understood,
    resolve,
)
from app.nlu.vocab import Vocabulary

CASES = Path(__file__).with_name("commands.jsonl")
TODAY = date(2026, 10, 1)  # a Thursday; "on monday" is 3 days back
NOW = datetime.combine(TODAY, time(18, 30), tzinfo=ZoneInfo("Asia/Kolkata"))

Parser = Callable[[str, Vocabulary, date], RawCommand]


@dataclass
class Outcome:
    case: dict[str, object]
    got: dict[str, object]
    passed: bool


def load_cases() -> list[dict[str, object]]:
    return [json.loads(line) for line in CASES.read_text().splitlines() if line.strip()]


def describe(raw: RawCommand, vocab: Vocabulary) -> dict[str, object]:
    result = resolve(raw, vocab, NOW)
    if isinstance(result, Answerable):
        q = result.query
        category = vocab.category(q.category_id) if q.category_id else None
        account = next((a.name for a in vocab.accounts if a.id == q.account_id), None)
        return {
            "tool": "query_spending",
            "metric": q.metric,
            "kind": q.kind.value,
            "category": category.name if category else None,
            "merchant": q.merchant,
            "account": account,
            "period": q.label,
        }
    if not isinstance(result, Understood):
        return {"tool": result.status}
    payload = result.payload
    got: dict[str, object] = {"tool": result.tool, "amount_paise": payload.amount_paise}
    category = vocab.category(payload.category_id) if payload.category_id else None
    got["category"] = category.name if category else None
    if isinstance(payload, TransactionProposal):
        account = next(a for a in vocab.accounts if a.id == payload.account_id)
        got |= {
            "kind": payload.kind.value,
            "account": account.name,
            "merchant": payload.merchant,
            "days_ago": (NOW.date() - payload.occurred_at.date()).days,
        }
    assert isinstance(payload, TransactionProposal | BudgetProposal)
    return got


def check(case: dict[str, object], got: dict[str, object]) -> bool:
    for key, expected in case.items():
        if key == "text":
            continue
        actual = got.get(key)
        if key == "merchant":
            if not actual or str(expected).lower() not in str(actual).lower():
                return False
        elif actual != expected:
            return False
    return True


def evaluate(parser: Parser) -> list[Outcome]:
    vocab = Vocabulary.from_seed()
    outcomes = []
    for case in load_cases():
        try:
            got = describe(parser(str(case["text"]), vocab, TODAY), vocab)
        except Exception as exc:  # a provider failure counts as a miss, not a crash
            got = {"error": repr(exc)}
        outcomes.append(Outcome(case, got, check(case, got)))
    return outcomes


def _parser(provider: str) -> Parser:
    if provider == "rules":
        from app.nlu import rules

        return rules.parse
    from app.config import get_settings
    from app.nlu.llm import provider_from_settings

    llm = provider_from_settings(get_settings(), provider)
    if llm is None:
        sys.exit(f"{provider} is not configured (missing API key)")
    return llm.parse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="rules", choices=["rules", "groq", "gemini"])
    parser.add_argument("--show", choices=["fail", "all"], default="fail")
    args = parser.parse_args()
    outcomes = evaluate(_parser(args.provider))
    for o in outcomes:
        if args.show == "all" or not o.passed:
            mark = "PASS" if o.passed else "FAIL"
            print(f"{mark}  {o.case['text']!r}\n      want {o.case}\n      got  {o.got}")
    passed = sum(o.passed for o in outcomes)
    print(f"\n{args.provider}: {passed}/{len(outcomes)} = {passed / len(outcomes):.0%}")


if __name__ == "__main__":
    main()
