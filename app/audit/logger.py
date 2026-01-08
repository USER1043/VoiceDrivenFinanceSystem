from supabase import Client
from datetime import datetime
from app.db.models import AuditLog


def log_action(supabase: Client, user_id: int, action: str, details: str):
    """
    Writes an audit log entry to the database.
    """
    try:
        data = {
            "user_id": user_id,
            "action": action,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        supabase.table("audit_logs").insert(data).execute()
    except Exception as e:
        # Log error but don't fail the main operation
        import logging
        logger = logging.getLogger("audit")
        logger.error(f"Failed to write audit log: {str(e)}")
