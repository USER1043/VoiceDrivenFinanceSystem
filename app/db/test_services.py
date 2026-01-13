from app.db.session import get_db_cursor, init_db
from app.services.budgets import set_budget

# Initialize database tables
init_db()

budget = set_budget(
    user_id=1,
    category="food",
    limit=6000
)

print("Budget created/updated with ID:", budget.id)

