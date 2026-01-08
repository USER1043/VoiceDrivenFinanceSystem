from supabase import Client
from typing import Optional
from datetime import datetime

from app.db.models import Budget
from app.audit.logger import log_action


# -----------------------------
# Create or Update Budget
# -----------------------------
def set_budget(
    supabase: Client,
    user_id: int,
    category: str,
    limit: float
) -> Budget:
    """
    Create a new budget or update an existing one for a category.
    """

    # Validation (service-level safety)
    if limit <= 0:
        raise ValueError("Budget limit must be greater than zero")

    # Check if budget exists
    existing_response = (
        supabase.table("budgets")
        .select("*")
        .eq("user_id", user_id)
        .eq("category", category)
        .execute()
    )

    existing_budget_data = existing_response.data[0] if existing_response.data else None

    if existing_budget_data:
        # Update existing budget
        updated_response = (
            supabase.table("budgets")
            .update({"limit": limit})
            .eq("id", existing_budget_data["id"])
            .execute()
        )
        
        if not updated_response.data:
            raise RuntimeError("Failed to update budget")
        
        budget_data = updated_response.data[0]
        budget = Budget(**budget_data)
        action = "UPDATE_BUDGET"
    else:
        # Create new budget
        data = {
            "user_id": user_id,
            "category": category,
            "limit": limit,
            "created_at": datetime.utcnow().isoformat()
        }
        
        response = supabase.table("budgets").insert(data).execute()
        
        if not response.data:
            raise RuntimeError("Failed to create budget")
        
        budget_data = response.data[0]
        budget = Budget(**budget_data)
        action = "CREATE_BUDGET"

    # Audit log
    log_action(
        supabase=supabase,
        user_id=user_id,
        action=action,
        details=f"{category} budget set to {limit}"
    )

    return budget


# -----------------------------
# Get Budget for Category
# -----------------------------
def get_budget(
    supabase: Client,
    user_id: int,
    category: str
) -> Optional[Budget]:
    """
    Fetch budget for a specific category.
    """

    try:
        response = (
            supabase.table("budgets")
            .select("*")
            .eq("user_id", user_id)
            .eq("category", category)
            .execute()
        )
        
        if not response.data:
            return None
        
        return Budget(**response.data[0])
    except Exception as e:
        return None


# -----------------------------
# Get All Budgets for User
# -----------------------------
def get_all_budgets(
    supabase: Client,
    user_id: int
) -> list[Budget]:
    """
    Fetch all budgets for a user.
    """

    try:
        response = (
            supabase.table("budgets")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        return [Budget(**row) for row in response.data]
    except Exception as e:
        raise RuntimeError(f"Failed to get budgets: {str(e)}")


# -----------------------------
# Delete Budget
# -----------------------------
def delete_budget(
    supabase: Client,
    user_id: int,
    category: str
) -> bool:
    """
    Delete a budget for a category.
    """

    try:
        # First find the budget
        response = (
            supabase.table("budgets")
            .select("*")
            .eq("user_id", user_id)
            .eq("category", category)
            .execute()
        )
        
        if not response.data:
            return False

        budget_id = response.data[0]["id"]
        
        # Delete the budget
        delete_response = (
            supabase.table("budgets")
            .delete()
            .eq("id", budget_id)
            .execute()
        )

        # Audit log
        log_action(
            supabase=supabase,
            user_id=user_id,
            action="DELETE_BUDGET",
            details=f"{category} budget deleted"
        )

        return True
    except Exception as e:
        raise RuntimeError(f"Failed to delete budget: {str(e)}")
