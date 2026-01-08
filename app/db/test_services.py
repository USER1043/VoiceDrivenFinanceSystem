from app.db.session import SessionLocal
from app.services.budgets import    set_budget

db = SessionLocal()

budget = set_budget(
    db=db,
    user_id=1,
    category="food",
    limit=6000
)

print("Budget created/updated with ID:", budget.id)

db.close()
