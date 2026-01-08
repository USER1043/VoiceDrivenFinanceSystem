import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Depends, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

# DB
from app.db.session import engine, SessionLocal, Base
from app.db.models import User

# Voice
from app.voice.recorder import save_audio_file
from app.voice.stt import transcribe_audio
from app.voice.tts import synthesize_speech

# Intent
from app.intent.detector import detect_intent, Intent
from app.intent.slots import (
    extract_budget_slots,
    extract_reminder_slots,
    extract_transaction_slots,
)

# Services
from app.services.budgets import set_budget, get_all_budgets
from app.services.reminders import create_reminder, get_reminders
from app.services.transactions import (
    add_transaction,
    get_transactions,
    get_total_spent,
)

# Routers
from app.api.routes import all_routers

# -------------------------------------------------
# LOGGING
# -------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-finance")

# -------------------------------------------------
# DB DEPENDENCY (PROD SAFE)
# -------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------------------------------
# APP LIFESPAN
# -------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Voice Driven Finance System")

    # Create tables
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database initialized")

    # Seed default user
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            db.add(User(id=1, email="default@voice-finance.com"))
            db.commit()
            logger.info("✅ Default user seeded")
    finally:
        db.close()

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
# CORS (PROD FRIENDLY)
# -------------------------------------------------
# For development, allow common origins
# In production, restrict to specific frontend URL
# NOTE: Cannot use allow_origins=["*"] with allow_credentials=True
# Browser security restriction - must specify exact origins
import os
is_dev = os.getenv("ENVIRONMENT", "development") == "development"

# Common development origins
dev_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    # Add more as needed
]

# Production origins - add your frontend URL here
prod_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=dev_origins if is_dev else prod_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight for 1 hour
)

# -------------------------------------------------
# CORS PREFLIGHT HANDLER
# -------------------------------------------------
@app.options("/{full_path:path}")
async def options_handler(request: Request, full_path: str):
    """Handle CORS preflight requests explicitly"""
    origin = request.headers.get("origin")
    # Use appropriate origin list based on environment
    allowed_origins = dev_origins if is_dev else prod_origins
    if origin and origin in allowed_origins:
        return JSONResponse(
            content={},
            headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Max-Age": "3600",
            }
        )
    return JSONResponse(content={})

# -------------------------------------------------
# ROOT
# -------------------------------------------------
@app.get("/")
def root():
    return {
        "status": "running",
        "service": "Voice Driven Finance System",
        "version": "1.0.0",
    }

# -------------------------------------------------
# REQUEST MODELS
# -------------------------------------------------
class TextProcessRequest(BaseModel):
    text: str
    user_id: Optional[int] = 1


# -------------------------------------------------
# MAIN TEXT PIPIELINE (BACKUP)
# -------------------------------------------------
@app.post("/text/process")
def process_text_command_post(
    request: Optional[TextProcessRequest] = Body(None),
    text: Optional[str] = Query(None),
    user_id: int = Query(1),
    db: Session = Depends(get_db),
):
    # Support both JSON body and query parameter
    if request:
        text = request.text
        user_id = request.user_id or user_id
    elif not text:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Text parameter is required"}
        )
    return _process_text_command(text, user_id, db)


@app.get("/text/process")
def process_text_command_get(
    text: str = Query(...),
    user_id: int = Query(1),
    db: Session = Depends(get_db),
):
    return _process_text_command(text, user_id, db)


def _process_text_command(
    text: str,
    user_id: int,
    db: Session,
):

    intent = detect_intent(text)

    response = {
        "intent": intent.value,
        "status": "unknown",
    }

    if intent == Intent.UPDATE_BUDGET:
        slots = extract_budget_slots(text)
        if slots["category"] and slots["limit"]:
            budget = set_budget(
                db=db,
                user_id=user_id,
                category=slots["category"],
                limit=slots["limit"],
            )
            response.update({
                "status": "success",
                "category": budget.category,
                "limit": budget.limit,
                "voice_response": f"Budget updated for {budget.category} to {budget.limit}",
            })

    elif intent == Intent.ADD_EXPENSE:
        slots = extract_transaction_slots(text)
        if slots["category"] and slots["limit"]:
            txn = add_transaction(
                db=db,
                user_id=user_id,
                category=slots["category"],
                limit=slots["limit"],
                description=slots.get("description"),
            )
            budget_warning = getattr(txn, "budget_warning", None)
            voice_msg = f"Expense of {txn.limit} added"
            if budget_warning:
                voice_msg += f". {budget_warning}"
            response.update({
                "status": "success",
                "category": txn.category,
                "limit": txn.limit,
                "budget_warning": budget_warning,
                "voice_response": voice_msg,
            })

    else:
        response.update({
            "status": "error",
            "voice_response": "Sorry, I did not understand that",
        })

    return response


# -------------------------------------------------
# MAIN VOICE PIPELI NE
# -------------------------------------------------
@app.post("/voice/process")
async def process_voice_command(
    file: UploadFile = File(...),
    user_id: int = 1,
    db: Session = Depends(get_db),
):
    try:
        # 1. Save audio
        audio_path = await save_audio_file(file)
        logger.info(f"🎙 Audio saved: {audio_path}")

        # 2. STT
        text = transcribe_audio(audio_path)
        logger.info(f"📝 Transcribed: {text}")

        # 3. Intent
        intent = detect_intent(text)
        logger.info(f"🎯 Intent: {intent.value}")

        response = {
            "transcribed_text": text,
            "intent": intent.value,
            "status": "unknown",
        }

        # 4. Intent routing
        if intent == Intent.UPDATE_BUDGET:
            slots = extract_budget_slots(text)
            if slots["category"] and slots["limit"]:
                budget = set_budget(
                    db=db,
                    user_id=user_id,
                    category=slots["category"],
                    limit=slots["limit"],
                )
                response.update({
                    "status": "success",
                    "action": "Budget updated",
                    "category": budget.category,
                    "limit": budget.limit,
                })

        elif intent == Intent.ADD_EXPENSE:
            slots = extract_transaction_slots(text)
            if slots["category"] and slots["limit"]:
                txn = add_transaction(
                    db=db,
                    user_id=user_id,
                    category=slots["category"],
                    limit=slots["limit"],
                    description=slots.get("description"),
                )
                response.update({
                    "status": "success",
                    "action": "Expense added",
                    "category": txn.category,
                    "limit": txn.limit,
                    "budget_warning": getattr(txn, "budget_warning", None),
                })

        elif intent == Intent.CREATE_REMINDER:
            slots = extract_reminder_slots(text)
            if slots["name"] and slots["day"]:
                reminder = create_reminder(
                    db=db,
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
            budgets = get_all_budgets(db=db, user_id=user_id)
            total = get_total_spent(db=db, user_id=user_id)
            
            # Calculate balance per category (cascading operation)
            balance_info = []
            for budget in budgets:
                category_spent = get_total_spent(db=db, user_id=user_id, category=budget.category)
                remaining = budget.limit - category_spent
                balance_info.append({
                    "category": budget.category,
                    "limit": budget.limit,
                    "spent": category_spent,
                    "remaining": remaining
                })
            
            response.update({
                "status": "success",
                "action": "Balance checked",
                "total_spent": total,
                "budgets": balance_info,
            })

        else:
            response.update({
                "status": "error",
                "message": "Could not understand command",
            })

        # 5. TTS message
        response["voice_response"] = generate_tts_response(response)

        return JSONResponse(content=response)

    except Exception as e:
        logger.exception("❌ Voice processing failed")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)},
        )

# -------------------------------------------------
# ANALYTICS
# -------------------------------------------------
@app.get("/analytics/summary")
def analytics_summary(
    user_id: int = 1,
    db: Session = Depends(get_db),
):
    return {
        "user_id": user_id,
        "total_spent": get_total_spent(db, user_id),
        "budgets": [
            {"category": b.category, "limit": b.limit}
            for b in get_all_budgets(db, user_id)
        ],
        "reminders": len(get_reminders(db, user_id)),
    }

# -------------------------------------------------
# TTS RESPONSE HELPER
# -------------------------------------------------
def generate_tts_response(data: dict) -> str:
    if data.get("status") != "success":
        return "Sorry, I could not process your request."

    action = data.get("action", "")
    if action == "Budget updated":
        return f"Budget set for {data['category']} at {data['limit']} rupees."
    if action == "Expense added":
        msg = f"Expense of {data['limit']} rupees recorded."
        if data.get("budget_warning"):
            msg += f" {data['budget_warning']}"
        return msg
    if action == "Balance checked":
        msg = f"You have spent {data['total_spent']} rupees in total."
        if data.get("budgets"):
            for budget_info in data["budgets"]:
                remaining = budget_info.get("remaining", budget_info['limit'] - budget_info['spent'])
                msg += f" {budget_info['category']}: {budget_info['spent']:.2f} spent out of {budget_info['limit']:.2f}, {remaining:.2f} remaining."
        return msg

    return "Action completed successfully."

# -------------------------------------------------
# ROUTERS
# -------------------------------------------------
for router in all_routers:
    app.include_router(router)
