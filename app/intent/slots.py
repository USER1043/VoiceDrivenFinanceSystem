import re
from typing import Dict, Optional

# -----------------------------
# Budget Slots
# -----------------------------
def extract_budget_slots(text: str) -> Dict[str, Optional[float | str]]:
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
    elif "entertainment" in text:
        category = "entertainment"

    match = re.search(r"\b(\d{1,7})\b", text)
    if match:
        limit = float(match.group(1))

    return {
        "category": category,
        "limit": limit,
    }


# -----------------------------
# Transaction / Expense Slots
# -----------------------------
def extract_transaction_slots(text: str) -> Dict[str, Optional[float | str]]:
    text = text.lower()

    category = None
    amount = None

    if "food" in text or "tea" in text:
        category = "food"
    elif "fuel" in text or "petrol" in text:
        category = "travel"
    elif "shopping" in text:
        category = "shopping"
    elif "rent" in text:
        category = "rent"

    match = re.search(r"\b(\d{1,7})\b", text)
    if match:
        amount = float(match.group(1))

    return {
        "category": category,
        "amount": amount,
        "description": text,
    }


# -----------------------------
# Reminder Slots
# -----------------------------
def extract_reminder_slots(text: str) -> Dict[str, Optional[str | int]]:
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
    elif "internet" in text:
        name = "internet bill"

    match = re.search(r"\b(\d{1,2})\b", text)
    if match:
        day = int(match.group(1))

    if "weekly" in text:
        frequency = "weekly"

    return {
        "name": name,
        "day": day,
        "frequency": frequency,
    }
