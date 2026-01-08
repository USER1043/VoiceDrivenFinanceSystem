from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db

from app.intent.detector import detect_intent, Intent
from app.intent.slots import extract_budget_slots
from app.intent.state import (
    create_initial_state,
    update_intent,
    update_slots,
    is_state_complete,
    reset_state
)

from app.services.budgets import set_budget
from app.cache.state_store import get_state, save_state, clear_state

router = APIRouter()


@router.post("/voice")
def handle_voice(
    text: str,
    db: Session = Depends(get_db)
):
    """
    Voice/Text handler with Redis-backed conversation state.
    """

    user_id = 1  # demo user (replace with auth later)

    # -----------------------------
    # Load or init state
    # -----------------------------
    state = get_state(user_id)
    if not state:
        state = create_initial_state()

    # -----------------------------
    # Detect intent
    # -----------------------------
    intent = detect_intent(text)
    state = update_intent(state, intent)

    # -----------------------------
    # Slot extraction
    # -----------------------------
    if intent == Intent.UPDATE_BUDGET:
        slots = extract_budget_slots(text)
        state = update_slots(state, slots)

        # Not enough info yet → save state
        if not is_state_complete(state):
            save_state(user_id, state)
            return {
                "success": True,
                "intent": intent.value,
                "message": "Need more information to set budget",
                "state": state["slots"]
            }

        # -----------------------------
        # Execute business logic
        # -----------------------------
        budget = set_budget(
            db=db,
            user_id=user_id,
            category=state["slots"]["category"],
            limit=state["slots"]["limit"]
        )

        # Clear state after success
        clear_state(user_id)

        return {
            "success": True,
            "intent": intent.value,
            "data": {
                "category": budget.category,
                "limit": budget.limit
            }
        }

    # -----------------------------
    # Unsupported intent
    # -----------------------------
    save_state(user_id, state)

    return {
        "success": False,
        "intent": intent.value,
        "message": "Intent not supported yet"
    }
