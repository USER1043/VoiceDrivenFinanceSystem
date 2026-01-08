from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from pydantic import BaseModel
from typing import Optional
import logging

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
logger = logging.getLogger(__name__)


class VoiceRequest(BaseModel):
    text: str
    user_id: Optional[int] = 1


class VoiceResponse(BaseModel):
    message: str
    intent: str
    success: bool
    data: Optional[dict] = None


@router.post("/voice", response_model=VoiceResponse)
def handle_voice(
    request: VoiceRequest,
    db: Client = Depends(get_db)
):
    """
    Handle voice commands by detecting intent and executing appropriate action.
    """
    
    text = request.text
    user_id = request.user_id
    
    try:
        intent = detect_intent(text)
        logger.info(f"Detected intent: {intent.value} for user {user_id}")

        if intent == Intent.UPDATE_BUDGET:
            return handle_update_budget(db, user_id, text, intent)
        
        elif intent == Intent.ADD_EXPENSE:
            return handle_add_expense(db, user_id, text, intent)
        
        elif intent == Intent.CREATE_REMINDER:
            return handle_create_reminder(db, user_id, text, intent)
        
        elif intent == Intent.CHECK_BALANCE:
            return handle_check_balance(db, user_id, intent)
        
        else:
            return VoiceResponse(
                message=f"Intent '{intent.value}' is not fully supported yet",
                intent=intent.value,
                success=False,
                data={"text": text}
            )
    
    except Exception as e:
        logger.error(f"Error handling voice command: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing voice command: {str(e)}"
        )


def handle_update_budget(
    db: Client,
    user_id: int,
    text: str,
    intent: Intent
) -> VoiceResponse:
    """Handle budget update intent."""
    slots = extract_budget_slots(text)
    
    if not slots.get("category") or not slots.get("limit"):
        return VoiceResponse(
            message="Could not extract budget information. Please specify both category and limit.",
            intent=intent.value,
            success=False
        )
    
    try:
        budget = set_budget(
            supabase=db,
            user_id=user_id,
            category=slots["category"],
            limit=slots["limit"]
        )
        
        logger.info(f"Budget updated: {budget.category} - ${budget.limit}")
        
        return VoiceResponse(
            message=f"Budget for {budget.category} set to ${budget.limit}",
            intent=intent.value,
            success=True,
            data={
                "category": budget.category,
                "limit": float(budget.limit),
                "budget_id": budget.id
            }
        )
    
    except Exception as e:
        logger.error(f"Error setting budget: {str(e)}")
        raise


def handle_add_expense(
    db: Client,
    user_id: int,
    text: str,
    intent: Intent
) -> VoiceResponse:
    """Handle expense addition intent."""
    slots = extract_transaction_slots(text)
    
    amount = slots.get("amount")
    category = slots.get("category")
    
    if not category or not amount:
        return VoiceResponse(
            message="Could not extract transaction information. Please specify both category and amount.",
            intent=intent.value,
            success=False
        )
    
    try:
        transaction = add_transaction(
            supabase=db,
            user_id=user_id,
            category=category,
            amount=amount,
            description=slots.get("description")
        )
        
        logger.info(f"Transaction added: {transaction.category} - ${transaction.amount}")
        
        # Check for budget warnings
        budget = get_budget(supabase=db, user_id=user_id, category=category)
        budget_warning = None
        
        if budget:
            total_spent = get_total_spent(supabase=db, user_id=user_id, category=category)
            if total_spent >= budget.limit:
                budget_warning = f"Warning: You've exceeded your {category} budget of ${budget.limit}!"
            elif total_spent >= budget.limit * 0.8:
                remaining = budget.limit - total_spent
                budget_warning = f"Note: You have ${remaining:.2f} remaining in your {category} budget"
        
        message = f"Expense of ${transaction.amount} added to {transaction.category}"
        if budget_warning:
            message += f". {budget_warning}"
        
        return VoiceResponse(
            message=message,
            intent=intent.value,
            success=True,
            data={
                "category": transaction.category,
                "amount": float(transaction.amount),
                "transaction_id": transaction.id,
                "description": transaction.description,
                "budget_warning": budget_warning
            }
        )
    
    except Exception as e:
        logger.error(f"Error adding transaction: {str(e)}")
        raise


def handle_create_reminder(
    db: Client,
    user_id: int,
    text: str,
    intent: Intent
) -> VoiceResponse:
    """Handle reminder creation intent."""
    slots = extract_reminder_slots(text)
    
    if not slots.get("name") or not slots.get("day"):
        return VoiceResponse(
            message="Could not extract reminder information. Please specify both name and day.",
            intent=intent.value,
            success=False
        )
    
    try:
        reminder = create_reminder(
            supabase=db,
            user_id=user_id,
            name=slots["name"],
            day=slots["day"],
            frequency=slots.get("frequency", "monthly")
        )
        
        logger.info(f"Reminder created: {reminder.name} on day {reminder.day}")
        
        return VoiceResponse(
            message=f"Reminder '{reminder.name}' created for day {reminder.day} ({reminder.frequency})",
            intent=intent.value,
            success=True,
            data={
                "name": reminder.name,
                "day": reminder.day,
                "frequency": reminder.frequency,
                "reminder_id": reminder.id
            }
        )
    
    except Exception as e:
        logger.error(f"Error creating reminder: {str(e)}")
        raise


def handle_check_balance(
    db: Client,
    user_id: int,
    intent: Intent
) -> VoiceResponse:
    """Handle balance check intent."""
    try:
        budgets = get_all_budgets(supabase=db, user_id=user_id)
        transactions = get_transactions(supabase=db, user_id=user_id, limit=100)
        
        if not budgets:
            return VoiceResponse(
                message="You don't have any budgets set up yet.",
                intent=intent.value,
                success=True,
                data={
                    "balances": [],
                    "total_transactions": len(transactions)
                }
            )
        
        # Calculate remaining budget for each category
        balance_info = []
        total_budget = 0
        total_spent = 0
        
        for budget in budgets:
            spent = get_total_spent(supabase=db, user_id=user_id, category=budget.category)
            remaining = budget.limit - spent
            percentage_used = (spent / budget.limit * 100) if budget.limit > 0 else 0
            
            balance_info.append({
                "category": budget.category,
                "limit": float(budget.limit),
                "spent": float(spent),
                "remaining": float(remaining),
                "percentage_used": round(percentage_used, 1),
                "status": "over_budget" if remaining < 0 else "warning" if percentage_used >= 80 else "good"
            })
            
            total_budget += budget.limit
            total_spent += spent
        
        # Sort by percentage used (highest first)
        balance_info.sort(key=lambda x: x["percentage_used"], reverse=True)
        
        message = f"You have {len(budgets)} budget(s) set up with {len(transactions)} total transactions"
        
        return VoiceResponse(
            message=message,
            intent=intent.value,
            success=True,
            data={
                "balances": balance_info,
                "total_budget": float(total_budget),
                "total_spent": float(total_spent),
                "total_remaining": float(total_budget - total_spent),
                "total_transactions": len(transactions)
            }
        )
    
    except Exception as e:
        logger.error(f"Error checking balance: {str(e)}")
        raise
