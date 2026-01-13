from typing import Optional, List
from datetime import datetime
import psycopg2

from app.db.models import Reminder
from app.audit.logger import log_action
from app.db.session import get_db_cursor


# -----------------------------
# Create Reminder
# -----------------------------
def create_reminder(
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

    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO reminders (user_id, name, day, frequency, created_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, user_id, name, day, frequency, created_at
            """,
            (user_id, name, day, frequency, datetime.utcnow())
        )
        
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("Failed to create reminder")
        
        reminder_data = {
            "id": row[0],
            "user_id": row[1],
            "name": row[2],
            "day": row[3],
            "frequency": row[4],
            "created_at": row[5]
        }
        
        reminder = Reminder(**reminder_data)

    log_action(
        user_id=user_id,
        action="CREATE_REMINDER",
        details=f"{name} on day {day} ({frequency})"
    )

    return reminder


# -----------------------------
# Get All Reminders for User
# -----------------------------
def get_reminders(
    user_id: int
) -> List[Reminder]:
    """
    Fetch all reminders for a user.
    """
    with get_db_cursor(commit=False) as cursor:
        cursor.execute(
            """
            SELECT id, user_id, name, day, frequency, created_at
            FROM reminders
            WHERE user_id = %s
            """,
            (user_id,)
        )
        
        rows = cursor.fetchall()
        reminders = []
        for row in rows:
            reminders.append(Reminder(
                id=row[0],
                user_id=row[1],
                name=row[2],
                day=row[3],
                frequency=row[4],
                created_at=row[5]
            ))
        
        return reminders


# -----------------------------
# Get Single Reminder
# -----------------------------
def get_reminder_by_id(
    reminder_id: int,
    user_id: int
) -> Optional[Reminder]:
    """
    Fetch a specific reminder by ID.
    """
    with get_db_cursor(commit=False) as cursor:
        cursor.execute(
            """
            SELECT id, user_id, name, day, frequency, created_at
            FROM reminders
            WHERE id = %s AND user_id = %s
            """,
            (reminder_id, user_id)
        )
        
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return Reminder(
            id=row[0],
            user_id=row[1],
            name=row[2],
            day=row[3],
            frequency=row[4],
            created_at=row[5]
        )


# -----------------------------
# Update Reminder
# -----------------------------
def update_reminder(
    reminder_id: int,
    user_id: int,
    day: Optional[int] = None,
    frequency: Optional[str] = None
) -> Reminder:
    """
    Update an existing reminder.
    """

    reminder = get_reminder_by_id(reminder_id, user_id)

    if not reminder:
        raise ValueError("Reminder not found")

    update_data = {}
    
    if day is not None:
        if day < 1 or day > 28:
            raise ValueError("Day must be between 1 and 28")
        update_data["day"] = day

    if frequency is not None:
        update_data["frequency"] = frequency

    if not update_data:
        return reminder

    with get_db_cursor() as cursor:
        # Build dynamic update query
        set_clauses = ", ".join([f"{k} = %s" for k in update_data.keys()])
        values = list(update_data.values())
        values.extend([reminder_id, user_id])
        
        query = f"""
            UPDATE reminders
            SET {set_clauses}
            WHERE id = %s AND user_id = %s
            RETURNING id, user_id, name, day, frequency, created_at
        """
        
        cursor.execute(query, values)
        
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("Failed to update reminder")
        
        updated_reminder = Reminder(
            id=row[0],
            user_id=row[1],
            name=row[2],
            day=row[3],
            frequency=row[4],
            created_at=row[5]
        )

    log_action(
        user_id=user_id,
        action="UPDATE_REMINDER",
        details=f"Reminder {reminder_id} updated"
    )

    return updated_reminder


# -----------------------------
# Delete Reminder
# -----------------------------
def delete_reminder(
    reminder_id: int,
    user_id: int
) -> bool:
    """
    Delete a reminder.
    """

    reminder = get_reminder_by_id(reminder_id, user_id)

    if not reminder:
        return False

    with get_db_cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM reminders
            WHERE id = %s AND user_id = %s
            """,
            (reminder_id, user_id)
        )

    log_action(
        user_id=user_id,
        action="DELETE_REMINDER",
        details=f"Reminder {reminder_id} deleted"
    )

    return True

