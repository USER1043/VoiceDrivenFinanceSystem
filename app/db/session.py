import os
import logging
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv
from contextlib import contextmanager
from typing import Optional, Generator

# Load environment variables from .env
load_dotenv()

# -------------------------------------------------
# LOGGING
# -------------------------------------------------
logger = logging.getLogger("db-session")

# -------------------------------------------------
# POSTGRESQL CONFIGURATION
# -------------------------------------------------
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_DB = os.getenv("POSTGRES_DB", "postgres")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

if not all([POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD]):
    raise RuntimeError("PostgreSQL environment variables must be set (POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD)")

# -------------------------------------------------
# CONNECTION POOL
# -------------------------------------------------
connection_pool = pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=20,
    host=POSTGRES_HOST,
    port=POSTGRES_PORT,
    database=POSTGRES_DB,
    user=POSTGRES_USER,
    password=POSTGRES_PASSWORD
)

# -------------------------------------------------
# CONTEXT MANAGER FOR CONNECTIONS
# -------------------------------------------------
@contextmanager
def get_db_connection() -> Generator:
    """
    Context manager for getting a database connection from the pool.
    Ensures connection is properly returned to the pool.
    """
    conn = connection_pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        connection_pool.putconn(conn)

@contextmanager
def get_db_cursor(commit: bool = True) -> Generator:
    """
    Context manager for getting a cursor with automatic connection management.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            yield cursor
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

# -------------------------------------------------
# DEPENDENCY (FASTAPI)
# -------------------------------------------------
def get_db() -> Generator:
    """
    FastAPI dependency that provides a database connection.
    """
    with get_db_cursor(commit=False) as cursor:
        yield cursor

# -------------------------------------------------
# INITIALIZE DATABASE TABLES
# -------------------------------------------------
def init_db():
    """
    Initialize database tables if they don't exist.
    """
    with get_db_cursor() as cursor:
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category VARCHAR(100) NOT NULL,
                amount DECIMAL(10, 2) NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create budgets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category VARCHAR(100) NOT NULL,
                limit_amount DECIMAL(10, 2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, category)
            )
        """)

        # Create reminders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                day INTEGER NOT NULL CHECK (day >= 1 AND day <= 28),
                frequency VARCHAR(50) NOT NULL DEFAULT 'monthly',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create audit_logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                action VARCHAR(100) NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    logger.info("Database tables initialized successfully")

# -------------------------------------------------
# CLOSE POOL
# -------------------------------------------------
def close_db_pool():
    """
    Close the connection pool. Call this on application shutdown.
    """
    connection_pool.closeall()
    logger.info("Database connection pool closed")


from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# -----------------------------
# User Model
# -----------------------------
class User(BaseModel):
    id: Optional[int] = None
    email: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# -----------------------------
# Transaction Model
# -----------------------------
class Transaction(BaseModel):
    id: Optional[int] = None
    user_id: int
    category: str
    amount: float
    description: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# -----------------------------
# Budget Model
# -----------------------------
class Budget(BaseModel):
    id: Optional[int] = None
    user_id: int
    category: str
    limit: float = Field(..., alias="limit_amount")
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        populate_by_name = True


# -----------------------------
# Reminder Model
# -----------------------------
class Reminder(BaseModel):
    id: Optional[int] = None
    user_id: int
    name: str
    day: int = Field(ge=1, le=28)  # day of month (1–28)
    frequency: str  # monthly / weekly
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# -----------------------------
# Audit Log Model
# -----------------------------
class AuditLog(BaseModel):
    id: Optional[int] = None
    user_id: int
    action: str
    details: str
    timestamp: Optional[datetime] = None

    class Config:
        from_attributes = True

