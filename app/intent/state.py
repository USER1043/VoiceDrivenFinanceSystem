from typing import Dict, Optional
from app.intent.detector import Intent


# -----------------------------
# Conversation State Structure
# -----------------------------
def create_initial_state() -> Dict:
    """
    Creates a fresh conversation state.
    """
    return {
        "intent": None,
        "slots": {},
        "completed": False
    }


# -----------------------------
# Update State with Intent
# -----------------------------
def update_intent(state: Dict, intent: Intent) -> Dict:
    """
    Updates intent in the conversation state.
    """
    state["intent"] = intent
    return state


# -----------------------------
# Update Slots Incrementally
# -----------------------------
def update_slots(state: Dict, new_slots: Dict) -> Dict:
    """
    Updates slots in state without overwriting existing valid values.
    """
    for key, value in new_slots.items():
        if value is not None:
            state["slots"][key] = value
    return state


# -----------------------------
# Check Completion for Budget
# -----------------------------
def is_budget_state_complete(state: Dict) -> bool:
    """
    Budget intent requires: category + amount
    """
    slots = state.get("slots", {})
    return slots.get("category") is not None and slots.get("amount") is not None


# -----------------------------
# Check Completion for Reminder
# -----------------------------
def is_reminder_state_complete(state: Dict) -> bool:
    """
    Reminder intent requires: name + day
    """
    slots = state.get("slots", {})
    return slots.get("name") is not None and slots.get("day") is not None


# -----------------------------
# Check Completion for Transaction
# -----------------------------
def is_transaction_state_complete(state: Dict) -> bool:
    """
    Transaction intent requires: category + amount
    """
    slots = state.get("slots", {})
    return slots.get("category") is not None and slots.get("amount") is not None


# -----------------------------
# Generic Completion Check
# -----------------------------
def is_state_complete(state: Dict) -> bool:
    """
    Determines if the current intent has all required slots.
    """
    intent = state.get("intent")

    if intent == Intent.UPDATE_BUDGET:
        return is_budget_state_complete(state)

    if intent == Intent.CREATE_REMINDER:
        return is_reminder_state_complete(state)

    if intent == Intent.ADD_EXPENSE:
        return is_transaction_state_complete(state)

    return False


# -----------------------------
# Reset State (After Execution)
# -----------------------------
def reset_state() -> Dict:
    """
    Clears conversation state after action is completed.
    """
    return create_initial_state()
