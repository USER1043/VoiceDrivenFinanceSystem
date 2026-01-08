import re
from typing import Dict, Optional

# -----------------------------
# Budget Slots
# -----------------------------
def extract_budget_slots(text: str) -> Dict[str, Optional[str | float]]:
    """
    Extract slots for budget intent.
    Example:
    "set food budget to 6000"
    """

    text = text.lower()

    category = None
    limit = None

    # Category detection
    if "food" in text:
        category = "food"
    elif "travel" in text:
        category = "travel"
    elif "shopping" in text:
        category = "shopping"
    elif "rent" in text:
        category = "rent"
    elif "entertainment" in text:
        category = "entertainment"

    # limit / limit detection
    limit_match = re.search(r"\b(\d{2,7})\b", text)
    if limit_match:
        limit = float(limit_match.group(1))

    return {
        "category": category,
        "limit": limit
    }


# -----------------------------
# Reminder Slots
# -----------------------------
def extract_reminder_slots(text: str) -> Dict[str, Optional[str | int]]:
    """
    Extract slots for reminder intent.
    Example:
    "remind me to pay electricity bill on the 5th"
    """

    text = text.lower()

    name = None
    day = None
    frequency = "monthly"

    # Reminder name
    if "electricity" in text:
        name = "electricity bill"
    elif "credit card" in text:
        name = "credit card bill"
    elif "rent" in text:
        name = "rent"
    elif "internet" in text:
        name = "internet bill"

    # Day detection
    day_match = re.search(r"\b(\d{1,2})\b", text)
    if day_match:
        day = int(day_match.group(1))

    # Frequency detection
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
# Expense / Transaction Slots
# -----------------------------
def extract_transaction_slots(text: str) -> Dict[str, Optional[str | float]]:
    """
    Extract slots for expense intent.
    Example:
    "I spent 250 on food"
    """

    text = text.lower()

    category = None
    limit = None

    # Category detection
    if "food" in text:
        category = "food"
    elif "travel" in text:
        category = "travel"
    elif "shopping" in text:
        category = "shopping"
    elif "rent" in text:
        category = "rent"

    # amount detection (stored as limit in Transaction model)
    match = re.search(r"\b(\d{1,7})\b", text)
    if match:
        limit = float(match.group(1))

    return {
        "category": category,
        "limit": limit,
        "description": text
    }
