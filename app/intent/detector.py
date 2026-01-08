from enum import Enum


class Intent(str, Enum):
    UPDATE_BUDGET = "UPDATE_BUDGET"
    CREATE_REMINDER = "CREATE_REMINDER"
    CHECK_BALANCE = "CHECK_BALANCE"
    ADD_EXPENSE = "ADD_EXPENSE"
    UNKNOWN = "UNKNOWN"


def detect_intent(text: str) -> Intent:
    """
    Deterministic rule-based intent detection.
    """

    if not text:
        return Intent.UNKNOWN

    text = text.lower()

    # ---- Budget ----
    if "budget" in text or "limit" in text:
        return Intent.UPDATE_BUDGET

    # ---- Reminder ----
    if "remind" in text or "reminder" in text:
        return Intent.CREATE_REMINDER

    # ---- Expense ----
    if "spent" in text or "expense" in text or "paid" in text:
        return Intent.ADD_EXPENSE

    # ---- Balance ----
    if "balance" in text or "money left" in text:
        return Intent.CHECK_BALANCE

    return Intent.UNKNOWN
