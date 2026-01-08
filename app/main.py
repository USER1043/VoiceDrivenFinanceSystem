import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Depends, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from supabase import Client
from pydantic import BaseModel

# 🧠 AI NORMALIZER
from app.ai.parser import normalize_command

# DB
from app.db.session import get_supabase
from app.db.models import User

# Voice
from app.voice.recorder import save_audio_file
from app.voice.stt import transcribe_audio

# Intent + slots
from app.intent.detector import detect_intent, Intent
from app.intent.slots import (
    extract_budget_slots,
    extract_reminder_slots,
    extract_transaction_slots,
)

# Services
from app.services.budgets import set_budget, get_all_budgets
from app.services.reminders import create_reminder, get_reminders
from app.services.transactions import add_transaction, get_total_spent

# Routers
from app.api.routes import all_routers

# -------------------------------------------------
# LOGGING
# -------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-finance")

# -------------------------------------------------
# DB DEPENDENCY
# -------------------------------------------------
def get_db() -> Client:
    """Get Supabase client for database operations"""
    return get_supabase()

# -------------------------------------------------
# APP LIFESPAN
# -------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Voice Driven Finance System")

    # Check Supabase connection and seed default user
    supabase = get_supabase()
    try:
        # Check if default user exists
        response = supabase.table("users").select("*").eq("id", 1).execute()
        
        if not response.data:
            # Create default user
            supabase.table("users").insert({
                "id": 1,
                "email": "default@voice-finance.com"
            }).execute()
            logger.info("✅ Default user seeded")
        else:
            logger.info("✅ Default user already exists")
    except Exception as e:
        logger.warning(f"⚠️ Could not seed default user: {e}")

    logger.info("✅ Database initialized")

    yield
    logger.info("🛑 Shutting down Voice Driven Finance System")

# -------------------------------------------------
# FASTAPI APP
# -------------------------------------------------
app = FastAPI(
    title="Voice Driven Finance System",
    version="1.0.0",
    description="Voice-powered personal finance assistant",
    lifespan=lifespan,
)

# -------------------------------------------------
# CORS
# -------------------------------------------------
import os

is_dev = os.getenv("ENVIRONMENT", "development") == "development"

dev_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]

prod_origins = ["http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=dev_origins if is_dev else prod_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# ROOT
# -------------------------------------------------
@app.get("/")
def root():
    return {"status": "running", "service": "Voice Driven Finance System"}

# -------------------------------------------------
# REQUEST MODEL
# -------------------------------------------------
class TextProcessRequest(BaseModel):
    text: str
    user_id: Optional[int] = 1

# -------------------------------------------------
# TEXT PIPELINE
# -------------------------------------------------
@app.post("/text/process")
def process_text_post(
    request: Optional[TextProcessRequest] = Body(None),
    text: Optional[str] = Query(None),
    user_id: int = Query(1),
    db: Client = Depends(get_db),
):
    if request:
        text = request.text
        user_id = request.user_id or user_id
    elif not text:
        return JSONResponse(status_code=400, content={"error": "Text required"})

    return _process_text_command(text, user_id, db)


@app.get("/text/process")
def process_text_get(
    text: str = Query(...),
    user_id: int = Query(1),
    db: Client = Depends(get_db),
):
    return _process_text_command(text, user_id, db)


def _process_text_command(text: str, user_id: int, db: Client):
    normalized = normalize_command(text)
    logger.info(f"🧠 AI normalized: '{text}' → '{normalized}'")

    intent = detect_intent(normalized)
    response = {"intent": intent.value, "status": "unknown"}

    # -------------------------
    # UPDATE BUDGET
    # -------------------------
    if intent == Intent.UPDATE_BUDGET:
        slots = extract_budget_slots(normalized)
        if slots["category"] and slots["limit"]:
            budget = set_budget(supabase=db, user_id=user_id, category=slots["category"], limit=slots["limit"])
            response.update({
                "status": "success",
                "category": budget.category,
                "limit": budget.limit,
                "voice_response": f"Budget updated for {budget.category}",
            })

    # -------------------------
    # ADD EXPENSE
    # -------------------------
    elif intent == Intent.ADD_EXPENSE:
        slots = extract_transaction_slots(normalized)
        if slots["category"] and slots["amount"]:
            txn = add_transaction(
                supabase=db,
                user_id=user_id,
                category=slots["category"],
                amount=slots["amount"],
                description=normalized,
            )
            response.update({
                "status": "success",
                "category": txn.category,
                "amount": txn.amount,     # ✅ FIXED
                "budget_warning": getattr(txn, "budget_warning", None),
                "voice_response": "Expense recorded",
            })

    else:
        response.update({
            "status": "error",
            "voice_response": "Sorry, I did not understand that",
        })

    return response

# -------------------------------------------------
# VOICE PIPELINE
# -------------------------------------------------
@app.post("/voice/process")
async def process_voice(
    file: UploadFile = File(...),
    user_id: int = 1,
    db: Client = Depends(get_db),
):
    try:
        audio_path = await save_audio_file(file)
        text = transcribe_audio(audio_path)

        normalized = normalize_command(text)
        logger.info(f"🧠 AI normalized (voice): '{text}' → '{normalized}'")

        intent = detect_intent(normalized)

        response = {
            "transcribed_text": text,
            "normalized_text": normalized,
            "intent": intent.value,
            "status": "unknown",
        }

        if intent == Intent.UPDATE_BUDGET:
            slots = extract_budget_slots(normalized)
            if slots["category"] and slots["limit"]:
                budget = set_budget(supabase=db, user_id=user_id, category=slots["category"], limit=slots["limit"])
                response.update({
                    "status": "success",
                    "action": "Budget updated",
                    "category": budget.category,
                    "limit": budget.limit,
                })

        elif intent == Intent.ADD_EXPENSE:
            slots = extract_transaction_slots(normalized)
            if slots["category"] and slots["amount"]:
                txn = add_transaction(
                    supabase=db,
                    user_id=user_id,
                    category=slots["category"],
                    amount=slots["amount"],
                    description=normalized,
                )
                response.update({
                    "status": "success",
                    "action": "Expense added",
                    "category": txn.category,
                    "amount": txn.amount,     # ✅ FIXED
                    "budget_warning": getattr(txn, "budget_warning", None),
                })

        elif intent == Intent.CREATE_REMINDER:
            slots = extract_reminder_slots(normalized)
            if slots["name"] and slots["day"]:
                reminder = create_reminder(
                    supabase=db,
                    user_id=user_id,
                    name=slots["name"],
                    day=slots["day"],
                    frequency=slots.get("frequency", "monthly"),
                )
                response.update({
                    "status": "success",
                    "action": "Reminder created",
                    "name": reminder.name,
                })

        elif intent == Intent.CHECK_BALANCE:
            budgets = get_all_budgets(supabase=db, user_id=user_id)
            total = get_total_spent(supabase=db, user_id=user_id)

            response.update({
                "status": "success",
                "action": "Balance checked",
                "total_spent": total,
                "budgets": [
                    {
                        "category": b.category,
                        "limit": b.limit,
                        "spent": get_total_spent(supabase=db, user_id=user_id, category=b.category),
                        "remaining": b.limit - get_total_spent(supabase=db, user_id=user_id, category=b.category),
                    }
                    for b in budgets
                ],
            })

        else:
            response.update({"status": "error", "message": "Unknown command"})

        return JSONResponse(content=response)

    except Exception as e:
        logger.exception("❌ Voice processing failed")
        return JSONResponse(status_code=500, content={"error": str(e)})

# -------------------------------------------------
# ANALYTICS
# -------------------------------------------------
@app.get("/analytics/summary")
def analytics(user_id: int = 1, db: Client = Depends(get_db)):
    return {
        "user_id": user_id,
        "total_spent": get_total_spent(supabase=db, user_id=user_id),
        "budgets": [
            {"category": b.category, "limit": b.limit}
            for b in get_all_budgets(supabase=db, user_id=user_id)
        ],
        "reminders": len(get_reminders(supabase=db, user_id=user_id)),
    }

# -------------------------------------------------
# ROUTERS
# -------------------------------------------------
for router in all_routers:
    app.include_router(router)
