from datetime import date, datetime
from enum import Enum
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models import AuditLog, Base


def snapshot(row: Base) -> dict[str, Any]:
    """Column values of an ORM row as JSON-safe data, for the audit log."""
    data: dict[str, Any] = {}
    for column in inspect(row).mapper.column_attrs:
        value = getattr(row, column.key)
        if isinstance(value, datetime | date):
            value = value.isoformat()
        elif isinstance(value, Enum):
            value = value.value
        data[column.key] = value
    return data


def record(
    session: Session,
    *,
    user_id: int,
    action: str,
    entity: str,
    entity_id: int | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            before=before,
            after=after,
        )
    )
