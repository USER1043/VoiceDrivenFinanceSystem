"""Domain errors raised by services; app.main maps them to HTTP responses."""

from typing import TypeVar

from sqlalchemy.orm import Session

from app.models import Base


class DomainError(Exception):
    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFound(DomainError):
    status_code = 404


class Invalid(DomainError):
    status_code = 422


class Conflict(DomainError):
    status_code = 409


M = TypeVar("M", bound=Base)


def get_owned(session: Session, model: type[M], row_id: int, user_id: int) -> M:
    """Fetch a row belonging to the user, or raise NotFound (never reveal other users' ids)."""
    row = session.get(model, row_id)
    if row is None or getattr(row, "user_id", None) != user_id:
        raise NotFound(f"{model.__name__} {row_id} not found")
    return row
