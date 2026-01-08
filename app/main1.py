from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

# DB
from app.db.session import SessionLocal
from app.db.models import Budget

# Redis state
from app.cache.state_store import get_state, save_state, clear_state

# Services
from app.services.budgets import set_budget

app = FastAPI(
    title="Voice Driven Finance – Sanity Test",
    version="1.0"
)

# -----------------------------
# DB Dependency
# -----------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------
# ROOT
# -----------------------------
@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "DB + Redis sanity app running"
    }

# -----------------------------
# TEST DB WRITE + READ
# -----------------------------
@app.post("/test/db")
def test_db(db: Session = Depends(get_db)):
    """
    Writes a budget to DB and reads it back.
    """

    budget = set_budget(
        db=db,
        user_id=1,          # demo user
        category="food",
        limit=5000
    )

    return {
        "db_status": "ok",
        "budget": {
            "id": budget.id,
            "user_id": budget.user_id,
            "category": budget.category,
            "limit": budget.limit
        }
    }

# -----------------------------
# TEST REDIS WRITE + READ
# -----------------------------
@app.post("/test/redis")
def test_redis():
    """
    Writes conversation state to Redis and reads it back.
    """

    test_state = {
        "intent": "UPDATE_BUDGET",
        "slots": {
            "category": "food",
            "limit": 5000
        },
        "completed": False
    }

    save_state(1, test_state)
    stored_state = get_state(1)

    return {
        "redis_status": "ok",
        "stored_state": stored_state
    }

# -----------------------------
# TEST FULL FLOW (DB + REDIS)
# -----------------------------
@app.post("/test/full")
def test_full_flow(db: Session = Depends(get_db)):
    """
    Simulates what /voice would do (without STT).
    """

    # Step 1: Save partial state to Redis
    save_state(1, {
        "intent": "UPDATE_BUDGET",
        "slots": {},
        "completed": False
    })

    # Step 2: Complete action in DB
    budget = set_budget(
        db=db,
        user_id=1,
        category="food",
        limit=6000
    )

    # Step 3: Clear Redis state
    clear_state(1)

    return {
        "success": True,
        "workflow": "DB + Redis",
        "result": {
            "category": budget.category,
            "limit": budget.limit
        }
    }
