"""Database schema. Alembic migrations are generated from these models.

Money is always stored as integer paise (BIGINT). Never use floats for amounts.
"""

import enum
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    # Stored as VARCHAR + CHECK so adding a value is a plain migration, not ALTER TYPE.
    return Enum(
        cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=20,
        values_callable=lambda e: [m.value for m in e],
    )


class AccountKind(enum.StrEnum):
    UPI = "upi"
    CASH = "cash"
    CARD = "card"
    BANK = "bank"


class CategoryKind(enum.StrEnum):
    EXPENSE = "expense"
    INCOME = "income"


class TransactionKind(enum.StrEnum):
    EXPENSE = "expense"
    INCOME = "income"


class TransactionSource(enum.StrEnum):
    VOICE = "voice"
    TEXT = "text"
    MANUAL = "manual"
    IMPORT = "import"


class BudgetPeriod(enum.StrEnum):
    MONTHLY = "monthly"


class Cadence(enum.StrEnum):
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    YEARLY = "yearly"


class PendingStatus(enum.StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")


class Account(TimestampMixin, Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("user_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[AccountKind] = mapped_column(_enum(AccountKind, "account_kind"))
    is_default: Mapped[bool] = mapped_column(default=False)
    archived: Mapped[bool] = mapped_column(default=False)


class Category(TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (
        # NULLS NOT DISTINCT so two top-level categories can't share a name (Postgres 15+).
        UniqueConstraint(
            "user_id", "kind", "parent_id", "name", postgresql_nulls_not_distinct=True
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[CategoryKind] = mapped_column(_enum(CategoryKind, "category_kind"))
    # Words the user says for this category ("chai", "zomato"); fed to the LLM and fallback parser.
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    archived: Mapped[bool] = mapped_column(default=False)


class Transaction(TimestampMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount_paise > 0", name="amount_positive"),
        Index("ix_transactions_user_occurred", "user_id", "occurred_at"),
        # Statement import dedupe: one row per bank/UPI reference per account.
        UniqueConstraint("account_id", "external_ref"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[TransactionKind] = mapped_column(_enum(TransactionKind, "transaction_kind"))
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    merchant: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[TransactionSource] = mapped_column(
        _enum(TransactionSource, "transaction_source")
    )
    raw_text: Mapped[str | None] = mapped_column(Text)
    external_ref: Mapped[str | None] = mapped_column(String(64))


class Budget(TimestampMixin, Base):
    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("user_id", "category_id", "period"),
        CheckConstraint("amount_paise > 0", name="amount_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    period: Mapped[BudgetPeriod] = mapped_column(
        _enum(BudgetPeriod, "budget_period"), default=BudgetPeriod.MONTHLY
    )
    amount_paise: Mapped[int] = mapped_column(BigInteger)


class RecurringRule(TimestampMixin, Base):
    __tablename__ = "recurring_rules"
    __table_args__ = (
        CheckConstraint("amount_paise IS NULL OR amount_paise > 0", name="amount_positive"),
        CheckConstraint(
            "day_of_month IS NULL OR day_of_month BETWEEN 1 AND 31", name="day_of_month_range"
        ),
        CheckConstraint("remind_days_before >= 0", name="remind_days_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    # Nullable: some bills vary (electricity), so only the reminder is fixed.
    amount_paise: Mapped[int | None] = mapped_column(BigInteger)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    cadence: Mapped[Cadence] = mapped_column(_enum(Cadence, "cadence"))
    # Day 29-31 falls back to the month's last day when scheduling.
    day_of_month: Mapped[int | None] = mapped_column()
    next_due_on: Mapped[date] = mapped_column(Date)
    remind_days_before: Mapped[int] = mapped_column(default=1)
    active: Mapped[bool] = mapped_column(default=True)


class PendingAction(TimestampMixin, Base):
    """A validated tool call waiting for the user's confirmation. Nothing writes without one."""

    __tablename__ = "pending_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    tool: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    source_text: Mapped[str] = mapped_column(Text)
    status: Mapped[PendingStatus] = mapped_column(
        _enum(PendingStatus, "pending_status"), default=PendingStatus.PENDING
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(40))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column()
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
