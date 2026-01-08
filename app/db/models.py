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
    limit: float
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


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
