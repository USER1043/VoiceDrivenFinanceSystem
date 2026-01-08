def validate_budget_slots(slots: dict):
    if not slots.get("category"):
        raise ValueError("Category required")

    if not slots.get("amount"):
        raise ValueError("Limit required")

    if slots["amount"] <= 0:
        raise ValueError("Limit must be positive")
