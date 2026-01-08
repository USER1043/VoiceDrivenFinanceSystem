import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        # add frontend prod URL here later
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
# MAIN TEXT PIPIELINE (BACKUP)
# -------------------------------------------------
@app.post("/text/process")
def process_text_command(
    text: str,
    user_id: int = 1,
    db: Session = Depends(get_db),
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
            )
            response.update({
                "status": "success",
                "category": txn.category,
                "limit": txn.limit,
                "voice_response": f"Expense of {txn.limit} added",
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
            total = get_total_spent(db=db, user_id=user_id)
            response.update({
                "status": "success",
                "action": "Balance checked",
                "total_spent": total,
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
        return f"Expense of {data['limit']} rupees recorded."
    if action == "Balance checked":
        return f"You have spent {data['total_spent']} rupees in total."

    return "Action completed successfully."

# -------------------------------------------------
# ROUTERS
# -------------------------------------------------
for router in all_routers:
    app.include_router(router)
