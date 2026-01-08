from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db
from app.intent.detector import detect_intent, Intent
from app.intent.slots import (
    extract_budget_slots,
    extract_reminder_slots,
    extract_transaction_slots
)
from app.services.budgets import set_budget, get_budget, get_all_budgets
from app.services.reminders import create_reminder
from app.services.transactions import add_transaction, get_transactions, get_total_spent

router = APIRouter()


class VoiceRequest(BaseModel):
    text: str


@router.post("/voice")
def handle_voice(
    request: VoiceRequest,
    db: Session = Depends(get_db)
):
    """
    Handle voice commands by detecting intent and executing appropriate action.
    Uses functions from other modules.
    """
    
    text = request.text
    intent = detect_intent(text)

    if intent == Intent.UPDATE_BUDGET:
        slots = extract_budget_slots(text)
        
        if not slots["category"] or not slots["limit"]:
            return {
                "message": "Could not extract budget information. Please specify category and limit.",
                "intent": intent.value
            }

        budget = set_budget(
            db=db,
            user_id=1,
            category=slots["category"],
            limit=slots["limit"]
        )

        return {
            "message": "Budget updated successfully",
            "intent": intent.value,
            "category": budget.category,
            "limit": budget.limit
        }

    elif intent == Intent.ADD_EXPENSE:
        slots = extract_transaction_slots(text)
        
        if not slots["category"] or not slots["limit"]:
            return {
                "message": "Could not extract transaction information. Please specify category and amount.",
                "intent": intent.value
            }

        transaction = add_transaction(
            db=db,
            user_id=1,
            category=slots["category"],
            limit=slots["limit"],
            description=slots.get("description")
        )

        budget_warning = getattr(transaction, "budget_warning", None)
        response = {
            "message": "Expense added successfully",
            "intent": intent.value,
            "category": transaction.category,
            "amount": transaction.limit,
            "transaction_id": transaction.id
        }
        
        if budget_warning:
            response["budget_warning"] = budget_warning
            response["message"] += f". {budget_warning}"

        return response

    elif intent == Intent.CREATE_REMINDER:
        slots = extract_reminder_slots(text)
        
        if not slots["name"] or not slots["day"]:
            return {
                "message": "Could not extract reminder information. Please specify name and day.",
                "intent": intent.value
            }

        reminder = create_reminder(
            db=db,
            user_id=1,
            name=slots["name"],
            day=slots["day"],
            frequency=slots.get("frequency", "monthly")
        )

        return {
            "message": "Reminder created successfully",
            "intent": intent.value,
            "name": reminder.name,
            "day": reminder.day,
            "frequency": reminder.frequency,
            "reminder_id": reminder.id
        }

    elif intent == Intent.CHECK_BALANCE:
        budgets = get_all_budgets(db=db, user_id=1)
        transactions = get_transactions(db=db, user_id=1, limit=100)
        
        # Calculate remaining budget for each category
        balance_info = []
        for budget in budgets:
            total_spent = get_total_spent(db=db, user_id=1, category=budget.category)
            remaining = budget.limit - total_spent
            
            balance_info.append({
                "category": budget.category,
                "limit": budget.limit,
                "spent": total_spent,
                "remaining": remaining
            })

        return {
            "message": "Balance information retrieved",
            "intent": intent.value,
            "balances": balance_info,
            "total_transactions": len(transactions)
        }

    return {
        "message": f"Intent '{intent.value}' not fully supported yet",
        "intent": intent.value,
        "text": text
    }
