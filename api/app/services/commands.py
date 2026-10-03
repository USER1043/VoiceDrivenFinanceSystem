"""Voice and typed commands: understand, propose, confirm. Nothing writes without a confirm."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import Conflict, get_owned
from app.models import Budget, PendingAction, PendingStatus, Transaction, TransactionSource, User
from app.money import format_inr
from app.nlu.llm import configured_providers
from app.nlu.pipeline import understand
from app.nlu.resolve import BudgetProposal, TransactionProposal, Understood, now_in
from app.nlu.vocab import Vocabulary
from app.schemas import TransactionIn
from app.services import budgets as budget_service
from app.services import transactions as transaction_service

Via = Literal["voice", "text"]


@dataclass
class CommandResult:
    status: Literal["proposal", "clarify", "unsupported"]
    message: str
    parser: str
    action: PendingAction | None = None


def describe(tool: str, data: dict[str, Any], vocab: Vocabulary, tz: str) -> str:
    """A short sentence for the confirm card and for reading aloud."""
    category = vocab.category(data["category_id"]) if data.get("category_id") else None
    amount = format_inr(data["amount_paise"])
    if tool == "set_budget":
        name = category.name if category else "that category"
        return f"Set the {name} budget to {amount} a month?"
    account = next((a.name for a in vocab.accounts if a.id == data["account_id"]), "")
    when = datetime.fromisoformat(data["occurred_at"]).astimezone(ZoneInfo(tz))
    today = datetime.now(ZoneInfo(tz)).date()
    day = (
        "today"
        if when.date() == today
        else "yesterday"
        if when.date() == today - timedelta(days=1)
        else when.strftime("%-d %b")
    )
    what = category.name if category else "uncategorised"
    merchant = f" at {data['merchant']}" if data.get("merchant") else ""
    if data["kind"] == "income":
        return f"Received {amount}{merchant} ({what}) into {account}, {day}?"
    return f"{amount} for {what}{merchant}, paid by {account}, {day}?"


def run_command(
    session: Session, user: User, settings: Settings, text: str, *, via: Via
) -> CommandResult:
    session.execute(
        update(PendingAction)
        .where(
            PendingAction.user_id == user.id,
            PendingAction.status == PendingStatus.PENDING,
            PendingAction.expires_at < datetime.now(UTC),
        )
        .values(status=PendingStatus.EXPIRED)
    )
    vocab = Vocabulary.load(session, user)
    result, parser = understand(text, vocab, now_in(user.timezone), configured_providers(settings))
    if not isinstance(result, Understood):
        session.commit()
        return CommandResult(status=result.status, message=result.message, parser=parser)

    data = result.payload.model_dump(mode="json")
    action = PendingAction(
        user_id=user.id,
        tool=result.tool,
        payload={"data": data, "via": via, "parser": parser},
        source_text=text,
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.pending_action_minutes),
    )
    session.add(action)
    session.commit()
    return CommandResult(
        status="proposal",
        message=describe(result.tool, data, vocab, user.timezone),
        action=action,
        parser=parser,
    )


def _open_action(session: Session, user: User, action_id: int) -> PendingAction:
    action = get_owned(session, PendingAction, action_id, user.id)
    if action.status != PendingStatus.PENDING:
        raise Conflict(f"This action was already {action.status.value}")
    if action.expires_at < datetime.now(UTC):
        action.status = PendingStatus.EXPIRED
        session.commit()
        raise Conflict("This action expired; please say it again")
    return action


def confirm(
    session: Session, user: User, action_id: int, overrides: dict[str, Any]
) -> Transaction | Budget:
    """Apply the user's corrections from the card, validate, and write."""
    action = _open_action(session, user, action_id)
    data = {**action.payload["data"], **overrides}
    written: Transaction | Budget
    if action.tool == "add_transaction":
        TransactionProposal.model_validate(data)  # shape check before the strict input model
        written = transaction_service.create_transaction(
            session,
            user,
            TransactionIn.model_validate(data),
            source=TransactionSource(action.payload.get("via", "voice")),
            raw_text=action.source_text,
        )
    else:
        budget = BudgetProposal.model_validate(data)
        written = budget_service.set_budget(session, user, budget.category_id, budget.amount_paise)
    action.status = PendingStatus.CONFIRMED
    session.commit()
    return written


def cancel(session: Session, user: User, action_id: int) -> None:
    action = _open_action(session, user, action_id)
    action.status = PendingStatus.CANCELLED
    session.commit()
