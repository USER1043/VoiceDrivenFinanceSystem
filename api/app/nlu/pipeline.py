"""understand(text): try each configured LLM, then the rule parser, and resolve the result."""

import logging
from collections.abc import Sequence
from datetime import datetime

from app.nlu import rules
from app.nlu.llm import LLMProvider, ProviderError
from app.nlu.raw import RawCommand
from app.nlu.resolve import Resolution, resolve
from app.nlu.vocab import Vocabulary

log = logging.getLogger(__name__)


def understand(
    text: str, vocab: Vocabulary, now: datetime, providers: Sequence[LLMProvider]
) -> tuple[Resolution, str]:
    """Returns the resolution and the name of the parser that produced it."""
    raw: RawCommand | None = None
    parser = "rules"
    for provider in providers:
        try:
            raw = provider.parse(text, vocab, now.date())
            parser = provider.name
            break
        except ProviderError as exc:
            log.warning("LLM provider failed, falling back: %s", exc)
    if raw is None:
        raw = rules.parse(text, vocab, now.date())
    elif raw.tool == "unsupported" and (fallback := rules.parse(text, vocab, now.date())).tool in (
        "add_transaction",
        "set_budget",
    ):
        # A cautious model refused something the rules understand ("chai 20"): take the rules.
        raw, parser = fallback, "rules"
    return resolve(raw, vocab, now), parser
