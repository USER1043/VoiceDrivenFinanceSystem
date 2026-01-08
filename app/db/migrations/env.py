from logging.config import fileConfig
import os

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# --------------------------------------------------
# Load environment variables
# --------------------------------------------------
load_dotenv()

config = context.config

database_url = os.getenv("DIRECT_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL not found in environment")

config.set_main_option("sqlalchemy.url", database_url)

# --------------------------------------------------
# Logging configuration
# --------------------------------------------------
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --------------------------------------------------
# Import models for autogenerate
# --------------------------------------------------
from app.db.session import Base
from app.db import models

target_metadata = Base.metadata

# --------------------------------------------------
# Offline migrations
# --------------------------------------------------
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

# --------------------------------------------------
# Online migrations
# --------------------------------------------------
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()

# --------------------------------------------------
# Entry point
# --------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
