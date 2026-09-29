from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    # Small pool (one user). pre_ping + recycle because serverless Postgres (Neon) drops idle
    # connections when it scales to zero after 5 minutes.
    return create_engine(
        get_settings().database_url,
        pool_size=3,
        max_overflow=2,
        pool_pre_ping=True,
        pool_recycle=240,
    )


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, committed by the caller."""
    with get_sessionmaker()() as session:
        yield session
