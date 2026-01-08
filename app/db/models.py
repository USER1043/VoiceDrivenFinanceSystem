from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text
)
from sqlalchemy.sql import func
from app.db.session import Base


# -----------------------------
# User Model
# -----------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# -----------------------------
# Transaction Model
# -----------------------------
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    category = Column(String, nullable=False)
    limit = Column(Float, nullable=False)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# -----------------------------
# Budget Model
# -----------------------------
class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    category = Column(String, nullable=False)
    limit = Column(Float, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# -----------------------------
# Reminder Model
# -----------------------------
class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    name = Column(String, nullable=False)
    day = Column(Integer, nullable=False)          # day of month (1–28)
    frequency = Column(String, nullable=False)     # monthly / weekly

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# -----------------------------
# Audit Log Model
# -----------------------------
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)

    action = Column(String, nullable=False)
    details = Column(Text, nullable=False)

    timestamp = Column(DateTime(timezone=True), server_default=func.now())
