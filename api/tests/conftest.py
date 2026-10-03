"""Tests run against a real Postgres database (TEST_DATABASE_URL).

The schema is built with the real Alembic migrations, and every test runs inside a
transaction that is rolled back afterwards.
"""

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.main import create_app
from app.seed import seed

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/voxfin_test"
)
OWNER = "owner@example.com"


@pytest.fixture(scope="session")
def connection() -> Iterator[Connection]:
    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
        conn.commit()
        cfg = Config("alembic.ini")
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
        conn.commit()
        yield conn
    engine.dispose()


@pytest.fixture
def session(connection: Connection) -> Iterator[Session]:
    trans = connection.begin()
    with Session(bind=connection, join_transaction_mode="create_savepoint") as s:
        yield s
    trans.rollback()


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "database_url": TEST_DATABASE_URL,
        "owner_email": OWNER,
        "web_dist_dir": "/nonexistent",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def seeded(session: Session, settings: Settings) -> Session:
    seed(session, settings.owner_email, settings.timezone)
    return session


@pytest.fixture
def client(session: Session, settings: Settings) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c
