import csv
import io
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.db import get_session
from app.models import Account, Category, Transaction
from app.money import format_rupees

router = APIRouter(prefix="/export", tags=["export"])
DB = Annotated[Session, Depends(get_session)]

COLUMNS = [
    "date",
    "time",
    "type",
    "amount_inr",
    "account",
    "category",
    "merchant",
    "note",
    "source",
]


def _cell(value: str | None) -> str:
    # Neutralise spreadsheet formula injection (a merchant named "=HYPERLINK(...)").
    value = value or ""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


@router.get("/transactions.csv")
def export_transactions(user: CurrentUser, session: DB) -> StreamingResponse:
    """All transactions, oldest first, for spreadsheets and your own backups."""
    tz = ZoneInfo(user.timezone)
    accounts = {
        a.id: a.name for a in session.scalars(select(Account).where(Account.user_id == user.id))
    }
    categories = {
        c.id: c for c in session.scalars(select(Category).where(Category.user_id == user.id))
    }

    def category_label(category_id: int | None) -> str:
        if category_id is None:
            return ""
        category = categories[category_id]
        parent = categories.get(category.parent_id) if category.parent_id else None
        return f"{parent.name} > {category.name}" if parent else category.name

    rows = session.scalars(
        select(Transaction)
        .where(Transaction.user_id == user.id)
        .order_by(Transaction.occurred_at, Transaction.id)
    ).all()

    def generate() -> Iterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(COLUMNS)
        for txn in rows:
            local = txn.occurred_at.astimezone(tz)
            writer.writerow(
                [
                    local.date().isoformat(),
                    local.strftime("%H:%M"),
                    txn.kind.value,
                    format_rupees(txn.amount_paise),
                    _cell(accounts.get(txn.account_id)),
                    _cell(category_label(txn.category_id)),
                    _cell(txn.merchant),
                    _cell(txn.note),
                    txn.source.value,
                ]
            )
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate()
        if not rows:
            yield buffer.getvalue()

    stamp = datetime.now(tz).strftime("%Y-%m-%d")
    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="voxfin-{stamp}.csv"'},
    )
