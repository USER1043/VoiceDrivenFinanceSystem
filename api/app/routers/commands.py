from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.config import Settings, get_settings
from app.db import get_session
from app.models import Transaction, User
from app.money import format_inr
from app.nlu.llm import configured_providers
from app.nlu.stt import MAX_AUDIO_BYTES, TranscriptionError, transcriber_from_settings
from app.nlu.vocab import Vocabulary
from app.routers.transactions import to_out
from app.schemas import (
    BudgetOut,
    CommandIn,
    CommandOut,
    ConfirmIn,
    ConfirmOut,
    PendingActionOut,
    VoiceStatus,
)
from app.services import commands as service

router = APIRouter(tags=["voice"])
DB = Annotated[Session, Depends(get_session)]
Config = Annotated[Settings, Depends(get_settings)]


def _combine(text: str, previous: str | None) -> str:
    return f"{previous} {text}" if previous else text


def _out(result: service.CommandResult, transcript: str) -> CommandOut:
    action = None
    if result.action is not None:
        action = PendingActionOut(
            id=result.action.id,
            tool=result.action.tool,
            data=result.action.payload["data"],
            expires_at=result.action.expires_at,
        )
    return CommandOut(
        status=result.status,
        transcript=transcript,
        message=result.message,
        parser=result.parser,
        action=action,
    )


@router.get("/voice/status", response_model=VoiceStatus)
def voice_status(user: CurrentUser, settings: Config) -> VoiceStatus:
    """Lets the app choose server speech-to-text or the browser's own."""
    return VoiceStatus(
        server_stt=transcriber_from_settings(settings) is not None,
        llm=[p.name for p in configured_providers(settings)],
    )


@router.post("/commands", response_model=CommandOut)
def typed_command(body: CommandIn, user: CurrentUser, session: DB, settings: Config) -> CommandOut:
    """Understand a typed (or browser-transcribed) command and propose an action."""
    text = _combine(body.text, body.previous)
    return _out(service.run_command(session, user, settings, text, via=body.via), body.text)


@router.post("/voice", response_model=CommandOut)
def voice_command(
    user: CurrentUser,
    session: DB,
    settings: Config,
    audio: Annotated[UploadFile, File()],
    previous: Annotated[str | None, Form(max_length=500)] = None,
) -> CommandOut:
    """Transcribe a short recording on the server (Groq Whisper), then as /commands."""
    transcriber = transcriber_from_settings(settings)
    if transcriber is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Server speech-to-text is off")
    data = audio.file.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Recording is too long")
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Empty recording")
    try:
        transcript = transcriber.transcribe(
            data,
            audio.filename or "command.webm",
            audio.content_type or "application/octet-stream",
            Vocabulary.load(session, user),
        )
    except TranscriptionError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Speech-to-text failed") from exc
    if not transcript:
        return CommandOut(
            status="clarify", transcript="", message="I didn't catch that.", parser="none"
        )
    text = _combine(transcript[:500], previous)
    return _out(service.run_command(session, user, settings, text, via="voice"), transcript)


def _confirm_message(written: Any, user: User) -> str:
    if isinstance(written, Transaction):
        return f"Saved {format_inr(written.amount_paise)}."
    return f"Budget set to {format_inr(written.amount_paise)} a month."


@router.post("/pending-actions/{action_id}/confirm", response_model=ConfirmOut)
def confirm_action(
    action_id: int, user: CurrentUser, session: DB, body: ConfirmIn | None = None
) -> ConfirmOut:
    overrides = body.model_dump(exclude_unset=True, mode="json") if body else {}
    written = service.confirm(session, user, action_id, overrides)
    if isinstance(written, Transaction):
        return ConfirmOut(
            tool="add_transaction",
            message=_confirm_message(written, user),
            transaction=to_out(written, user),
        )
    return ConfirmOut(
        tool="set_budget",
        message=_confirm_message(written, user),
        budget=BudgetOut.model_validate(written),
    )


@router.post("/pending-actions/{action_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_action(action_id: int, user: CurrentUser, session: DB) -> None:
    service.cancel(session, user, action_id)
