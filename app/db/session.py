import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()
# -------------------------------------------------
# LOGGING
# -------------------------------------------------
logger = logging.getLogger("db-session")

# -------------------------------------------------
# DATABASE URL
# -------------------------------------------------

# Fetch variables
USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")

# Construct the SQLAlchemy connection string
DATABASE_URL = f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}?sslmode=require"


if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable not set")

# Clean up common env issues
DATABASE_URL = DATABASE_URL.strip()

# -------------------------------------------------
# ENGINE CONFIG (PROD SAFE)
# -------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,            # good default for Supabase
    max_overflow=10,
    pool_timeout=30,
    pool_pre_ping=True,     # prevents stale connections
    pool_recycle=1800,      # recycle every 30 mins
    echo=False,             # set True only for debugging
)

# -------------------------------------------------
# SESSION FACTORY
# -------------------------------------------------
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# -------------------------------------------------
# BASE MODEL
# -------------------------------------------------
Base = declarative_base()

# -------------------------------------------------
# DEPENDENCY (FASTAPI)
# -------------------------------------------------
def get_db():
    """
    FastAPI dependency that provides a DB session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------------------------------
# OPTIONAL: SAFE DB INIT (DO NOT CRASH APP)
# -------------------------------------------------
def init_db():
    """
    Initialize DB tables safely.
    Call this manually if needed.
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables ensured")
    except Exception as e:
        logger.error(f"⚠️ Database init skipped: {e}")
