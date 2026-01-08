from typing import Dict
from app.intent.detector import Intent


def create_initial_state() -> Dict:
    return {
        "intent": None,
        "slots": {},
        "completed": False
    }


def update_intent(state: Dict, intent: Intent) -> Dict:
    state["intent"] = intent
    return state


def update_slots(state: Dict, new_slots: Dict) -> Dict:
    for key, value in new_slots.items():
        if value is not None:
            state["slots"][key] = value
    return state


def is_budget_state_complete(state: Dict) -> bool:
    slots = state.get("slots", {})
    return slots.get("category") is not None and slots.get("limit") is not None


def is_reminder_state_complete(state: Dict) -> bool:
    slots = state.get("slots", {})
    return slots.get("name") is not None and slots.get("day") is not None


def is_transaction_state_complete(state: Dict) -> bool:
    slots = state.get("slots", {})
    return slots.get("category") is not None and slots.get("amount") is not None


def is_state_complete(state: Dict) -> bool:
    intent = state.get("intent")

    if intent == Intent.UPDATE_BUDGET:
        return is_budget_state_complete(state)

    if intent == Intent.CREATE_REMINDER:
        return is_reminder_state_complete(state)

    if intent == Intent.ADD_EXPENSE:
        return is_transaction_state_complete(state)

    return False


def reset_state() -> Dict:
    return create_initial_state()
