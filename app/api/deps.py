from app.db.session import get_db_cursor
from typing import Generator
from psycopg2.extensions import cursor as Cursor


def get_db() -> Generator[Cursor, None, None]:
    """
    FastAPI dependency that provides a database cursor.
    """
    with get_db_cursor(commit=False) as cursor:
        yield cursor

