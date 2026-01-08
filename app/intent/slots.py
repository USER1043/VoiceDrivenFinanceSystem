import re
from typing import Dict, Optional


# -----------------------------
# Budget Slots
# -----------------------------
def extract_budget_slots(text: str) -> Dict[str, Optional[str | float]]:
    """
    Example:
    'set food budget to 6000'
    """

    text = text.lower()
    category = None
    limit = None

    if "food" in text:
        category = "food"
    elif "travel" in text:
        category = "travel"
    elif "shopping" in text:
        category = "shopping"
    elif "rent" in text:
        category = "rent"

    amount_match = re.search(r"\b(\d{2,7})\b", text)
    if amount_match:
        limit = float(amount_match.group(1))

    return {
        "category": category,
        "limit": limit
    }


# -----------------------------
# Reminder Slots
# -----------------------------
def extract_reminder_slots(text: str) -> Dict[str, Optional[str | int]]:
    """
    Example:
    'remind me to pay electricity bill on 5'
    """

    text = text.lower()
    name = None
    day = None
    frequency = "monthly"

    if "electricity" in text:
        name = "electricity bill"
    elif "credit card" in text:
        name = "credit card bill"
    elif "rent" in text:
        name = "rent"

    day_match = re.search(r"\b(\d{1,2})\b", text)
    if day_match:
        day = int(day_match.group(1))

    if "weekly" in text:
        frequency = "weekly"

    return {
        "name": name,
        "day": day,
        "frequency": frequency
    }


# -----------------------------
# Expense Slots
# -----------------------------
def extract_transaction_slots(text: str) -> Dict[str, Optional[str | float]]:
    """
    Example:
    'I spent 250 on food'
    """

    text = text.lower()
    category = None
    amount = None

    if "food" in text:
        category = "food"
    elif "travel" in text:
        category = "travel"
    elif "shopping" in text:
        category = "shopping"

    amount_match = re.search(r"\b(\d{1,7})\b", text)
    if amount_match:
        amount = float(amount_match.group(1))

    return {
        "category": category,
        "amount": amount,
        "description": text
    }
