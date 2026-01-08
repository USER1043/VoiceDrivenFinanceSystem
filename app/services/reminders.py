from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional, List

from app.db.models import Reminder
from app.audit.logger import log_action


# -----------------------------
# Create Reminder
# -----------------------------
def create_reminder(
    db: Session,
    user_id: int,
    name: str,
    day: int,
    frequency: str = "monthly"
) -> Reminder:
    """
    Create a new reminder.
    """

    # Basic validation (service-level safety)
    if day < 1 or day > 28:
        raise ValueError("Day must be between 1 and 28")

    reminder = Reminder(
        user_id=user_id,
        name=name,
        day=day,
        frequency=frequency
    )

    try:
        db.add(reminder)
        db.commit()
        db.refresh(reminder)
    except IntegrityError:
        db.rollback()
        raise RuntimeError("Failed to create reminder")

    log_action(
        db=db,
        user_id=user_id,
        action="CREATE_REMINDER",
        details=f"{name} on day {day} ({frequency})"
    )

    return reminder


# -----------------------------
# Get All Reminders for User
# -----------------------------
def get_reminders(
    db: Session,
    user_id: int
) -> List[Reminder]:
    """
    Fetch all reminders for a user.
    """
    return (
        db.query(Reminder)
        .filter(Reminder.user_id == user_id)
        .all()
    )


# -----------------------------
# Get Single Reminder
# -----------------------------
def get_reminder_by_id(
    db: Session,
    reminder_id: int,
    user_id: int
) -> Optional[Reminder]:
    """
    Fetch a specific reminder by ID.
    """
    return (
        db.query(Reminder)
        .filter(
            Reminder.id == reminder_id,
            Reminder.user_id == user_id
        )
        .first()
    )


# -----------------------------
# Update Reminder
# -----------------------------
def update_reminder(
    db: Session,
    reminder_id: int,
    user_id: int,
    day: Optional[int] = None,
    frequency: Optional[str] = None
) -> Reminder:
    """
    Update an existing reminder.
    """

    reminder = get_reminder_by_id(db, reminder_id, user_id)

    if not reminder:
        raise ValueError("Reminder not found")

    if day is not None:
        if day < 1 or day > 28:
            raise ValueError("Day must be between 1 and 28")
        reminder.day = day

    if frequency is not None:
        reminder.frequency = frequency

    db.commit()
    db.refresh(reminder)

    log_action(
        db=db,
        user_id=user_id,
        action="UPDATE_REMINDER",
        details=f"Reminder {reminder_id} updated"
    )

    return reminder


# -----------------------------
# Delete Reminder
# -----------------------------
def delete_reminder(
    db: Session,
    reminder_id: int,
    user_id: int
) -> bool:
    """
    Delete a reminder.
    """

    reminder = get_reminder_by_id(db, reminder_id, user_id)

    if not reminder:
        return False

    db.delete(reminder)
    db.commit()

    log_action(
        db=db,
        user_id=user_id,
        action="DELETE_REMINDER",
        details=f"Reminder {reminder_id} deleted"
    )

    return True
