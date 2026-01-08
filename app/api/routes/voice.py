from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.intent.detector import detect_intent, Intent
from app.intent.slots import extract_budget_slots
from app.services.budgets import set_budget

router = APIRouter()


@router.post("/voice")
def handle_voice(
    text: str,
    db: Session = Depends(get_db)
):
    """
    Temporary text-based voice handler.
    (Voice STT can plug in later)
    """
    
    intent = detect_intent(text)

    if intent == Intent.UPDATE_BUDGET:
        slots = extract_budget_slots(text)

        budget = set_budget(
            db=db,
            user_id=1,   # demo user
            category=slots["category"],
            limit=slots["amount"]
        )

        return {
            "message": "Budget updated successfully",
            "category": budget.category,
            "limit": budget.limit
        }

    return {
        "message": "Intent not supported yet"
    }
