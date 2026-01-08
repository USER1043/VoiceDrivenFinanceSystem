def validate_budget_slots(slots: dict):
    if not slots.get("category"):
        raise ValueError("Category required")

    if not slots.get("limit"):
        raise ValueError("Limit required")

    if slots["limit"] <= 0:
        raise ValueError("Limit must be positive")
