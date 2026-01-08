from supabase import Client
from typing import List, Optional
from datetime import datetime

from app.db.models import Transaction
from app.audit.logger import log_action
from app.services.budgets import get_budget


# -----------------------------
# Add Transaction / Expense
# -----------------------------
def add_transaction(
    supabase: Client,
    user_id: int,
    category: str,
    amount: float,
    description: Optional[str] = None
) -> Transaction:
    """
    Add a new transaction (expense).
    """

    if amount <= 0:
        raise ValueError("Transaction amount must be positive")

    budget = get_budget(supabase=supabase, user_id=user_id, category=category)

    total_spent = get_total_spent(supabase=supabase, user_id=user_id, category=category)
    new_total = total_spent + amount

    budget_warning = None
    if budget:
        if new_total > budget.limit:
            budget_warning = (
                f"WARNING: Budget exceeded! Limit: {budget.limit}, "
                f"Total spent: {new_total:.2f}"
            )
        elif new_total > budget.limit * 0.9:
            budget_warning = (
                f"WARNING: Approaching budget limit. Limit: {budget.limit}, "
                f"Total spent: {new_total:.2f}"
            )

    # Insert transaction
    data = {
        "user_id": user_id,
        "category": category,
        "amount": amount,
        "description": description,
        "created_at": datetime.utcnow().isoformat()
    }

    try:
        response = supabase.table("transactions").insert(data).execute()
        if not response.data:
            raise RuntimeError("Failed to add transaction")
        
        transaction_data = response.data[0]
        transaction = Transaction(**transaction_data)
        
        log_action(
            supabase=supabase,
            user_id=user_id,
            action="ADD_TRANSACTION",
            details=f"{category} → {amount}"
        )

        if budget_warning:
            transaction.budget_warning = budget_warning

        return transaction
    except Exception as e:
        raise RuntimeError(f"Failed to add transaction: {str(e)}")


# -----------------------------
# Get Transactions
# -----------------------------
def get_transactions(
    supabase: Client,
    user_id: int,
    limit: int = 50
) -> List[Transaction]:
    try:
        response = (
            supabase.table("transactions")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [Transaction(**row) for row in response.data]
    except Exception as e:
        raise RuntimeError(f"Failed to get transactions: {str(e)}")


# -----------------------------
# Get Total Spent
# -----------------------------
def get_total_spent(
    supabase: Client,
    user_id: int,
    category: Optional[str] = None
) -> float:
    try:
        query = (
            supabase.table("transactions")
            .select("amount")
            .eq("user_id", user_id)
        )
        
        if category:
            query = query.eq("category", category)
        
        response = query.execute()
        
        return sum(float(row["amount"]) for row in response.data)
    except Exception as e:
        raise RuntimeError(f"Failed to get total spent: {str(e)}")
