from app.db.models import AuditLog


def log_action(db, user_id: int, action: str, details: str):
    """
    Writes an audit log entry to the database.
    """
    audit = AuditLog(
        user_id=user_id,
        action=action,
        details=details
    )
    db.add(audit)
    db.commit()
