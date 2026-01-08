from supabase import Client
from typing import Optional, List
from datetime import datetime

from app.db.models import Reminder
from app.audit.logger import log_action


# -----------------------------
# Create Reminder
# -----------------------------
def create_reminder(
    supabase: Client,
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

    data = {
        "user_id": user_id,
        "name": name,
        "day": day,
        "frequency": frequency,
        "created_at": datetime.utcnow().isoformat()
    }

    try:
        response = supabase.table("reminders").insert(data).execute()
        
        if not response.data:
            raise RuntimeError("Failed to create reminder")
        
        reminder_data = response.data[0]
        reminder = Reminder(**reminder_data)

        log_action(
            supabase=supabase,
            user_id=user_id,
            action="CREATE_REMINDER",
            details=f"{name} on day {day} ({frequency})"
        )

        return reminder
    except Exception as e:
        raise RuntimeError(f"Failed to create reminder: {str(e)}")


# -----------------------------
# Get All Reminders for User
# -----------------------------
def get_reminders(
    supabase: Client,
    user_id: int
) -> List[Reminder]:
    """
    Fetch all reminders for a user.
    """
    try:
        response = (
            supabase.table("reminders")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        return [Reminder(**row) for row in response.data]
    except Exception as e:
        raise RuntimeError(f"Failed to get reminders: {str(e)}")


# -----------------------------
# Get Single Reminder
# -----------------------------
def get_reminder_by_id(
    supabase: Client,
    reminder_id: int,
    user_id: int
) -> Optional[Reminder]:
    """
    Fetch a specific reminder by ID.
    """
    try:
        response = (
            supabase.table("reminders")
            .select("*")
            .eq("id", reminder_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        if not response.data:
            return None
        
        return Reminder(**response.data[0])
    except Exception as e:
        return None


# -----------------------------
# Update Reminder
# -----------------------------
def update_reminder(
    supabase: Client,
    reminder_id: int,
    user_id: int,
    day: Optional[int] = None,
    frequency: Optional[str] = None
) -> Reminder:
    """
    Update an existing reminder.
    """

    reminder = get_reminder_by_id(supabase, reminder_id, user_id)

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

    try:
        response = (
            supabase.table("reminders")
            .update(update_data)
            .eq("id", reminder_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        if not response.data:
            raise RuntimeError("Failed to update reminder")
        
        updated_reminder = Reminder(**response.data[0])

        log_action(
            supabase=supabase,
            user_id=user_id,
            action="UPDATE_REMINDER",
            details=f"Reminder {reminder_id} updated"
        )

        return updated_reminder
    except Exception as e:
        raise RuntimeError(f"Failed to update reminder: {str(e)}")


# -----------------------------
# Delete Reminder
# -----------------------------
def delete_reminder(
    supabase: Client,
    reminder_id: int,
    user_id: int
) -> bool:
    """
    Delete a reminder.
    """

    reminder = get_reminder_by_id(supabase, reminder_id, user_id)

    if not reminder:
        return False

    try:
        delete_response = (
            supabase.table("reminders")
            .delete()
            .eq("id", reminder_id)
            .eq("user_id", user_id)
            .execute()
        )

        log_action(
            supabase=supabase,
            user_id=user_id,
            action="DELETE_REMINDER",
            details=f"Reminder {reminder_id} deleted"
        )

        return True
    except Exception as e:
        raise RuntimeError(f"Failed to delete reminder: {str(e)}")
