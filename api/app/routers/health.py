from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_session

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health() -> dict[str, str]:
    """Liveness only. Deliberately does NOT touch the database: Render's health checks and
    keep-warm pings hit this, and querying Neon would stop it from ever scaling to zero and
    burn the free compute hours."""
    return {"status": "ok"}


@router.get("/db")
def health_db(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
    """Readiness including the database. For manual checks and CI, not for frequent pings."""
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok", "database": "ok"}
