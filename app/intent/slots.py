import re
from typing import Optional, Dict


# -----------------------------
# Budget Slots
# -----------------------------
def extract_budget_slots(text: str) -> Dict[str, Optional[float | str]]:
    """
    Extracts slots for budget-related intents.
    Example:
    "set food budget to 6000"
    """

    text = text.lower()

    category = None
    amount = None

    # Category extraction (extendable)
    if "food" in text:
        category = "food"
    elif "travel" in text:
        category = "travel"
    elif "shopping" in text:
        category = "shopping"
    elif "rent" in text:
        category = "rent"

    # Amount extraction
    amount_match = re.search(r"\b(\d{2,7})\b", text)
    if amount_match:
        amount = float(amount_match.group(1))

    return {
        "category": category,
        "amount": amount
    }


# -----------------------------
# Reminder Slots
# -----------------------------
def extract_reminder_slots(text: str) -> Dict[str, Optional[str | int]]:
    """
    Extracts slots for reminder-related intents.
    Example:
    "remind me to pay electricity bill on the 5th every month"
    """

    text = text.lower()

    name = None
    day = None
    frequency = "monthly"

    # Bill / reminder name
    if "electricity" in text:
        name = "electricity bill"
    elif "credit card" in text:
        name = "credit card bill"
    elif "rent" in text:
        name = "rent"

    # Day extraction
    day_match = re.search(r"\b(\d{1,2})\b", text)
    if day_match:
        day = int(day_match.group(1))

    # Frequency
    if "weekly" in text:
        frequency = "weekly"
    elif "monthly" in text:
        frequency = "monthly"

    return {
        "name": name,
        "day": day,
        "frequency": frequency
    }


# -----------------------------
# Transaction / Expense Slots
# -----------------------------
def extract_transaction_slots(text: str) -> Dict[str, Optional[str | float]]:
    """
    Extracts slots for expense-related intents.
    Example:
    "I spent 250 on food"
    """

    text = text.lower()

    category = None
    amount = None
    description = None

    # Category
    if "food" in text:
        category = "food"
    elif "travel" in text:
        category = "travel"
    elif "shopping" in text:
        category = "shopping"

    # Amount
    amount_match = re.search(r"\b(\d{1,7})\b", text)
    if amount_match:
        amount = float(amount_match.group(1))

    # Description (simple heuristic)
    description = text

    return {
        "category": category,
        "amount": amount,
        "description": description
    }
