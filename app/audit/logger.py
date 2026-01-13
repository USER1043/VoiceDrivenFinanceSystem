from datetime import datetime
import logging
from app.db.session import get_db_cursor

logger = logging.getLogger("audit")


def log_action(user_id: int, action: str, details: str):
    """
    Writes an audit log entry to the database.
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO audit_logs (user_id, action, details, timestamp)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, action, details, datetime.utcnow())
            )
    except Exception as e:
        # Log error but don't fail the main operation
        logger.error(f"Failed to write audit log: {str(e)}")

