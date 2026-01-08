import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import engine, get_db, Base
from app.api.routes import all_routers
from app.voice.recorder import save_audio_file
from app.voice.stt import transcribe_audio
from app.voice.tts import synthesize_speech
from app.intent.detector import detect_intent, Intent
from app.intent.slots import (
    extract_budget_slots,
    extract_reminder_slots,
    extract_transaction_slots
)
from app.services.budgets import set_budget, get_budget, get_all_budgets
from app.services.reminders import create_reminder, get_reminders
from app.services.transactions import add_transaction, get_transactions, get_total_spent
from app.audit.logger import log_action
from app.db.models import User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Lifespan context manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage startup and shutdown events.
    - Create database tables on startup
    - Close connections on shutdown
    """
    logger.info("🚀 Starting Voice Driven Finance System...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables initialized")
    
    # Seed default user if needed
    db = next(get_db())
    try:
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            default_user = User(id=1, email="default@voice-finance.com")
            db.add(default_user)
            db.commit()
            logger.info("✅ Default user created")
    finally:
        db.close()
    
    yield  # Application runs here
    
    logger.info("🛑 Shutting down Voice Driven Finance System...")


# Initialize FastAPI application
app = FastAPI(
    title="Voice Driven Finance System",
    version="1.0.0",
    description="AI-powered voice-driven personal finance management system",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Root endpoint
@app.get("/")
def root():
    return {
        "message": "Voice Driven Finance System API",
        "version": "1.0.0",
        "status": "running"
    }


# Voice command processing endpoint (main feature)
@app.post("/voice/process")
async def process_voice_command(
    file: UploadFile = File(...),
    user_id: int = 1
):
    """
    Process voice command end-to-end:
    1. Save audio file
    2. Transcribe speech to text using Whisper
    3. Detect intent from text
    4. Extract relevant information (slots)
    5. Execute appropriate action (budget, transaction, reminder)
    6. Generate TTS response
    """
    try:
        # Step 1: Save uploaded audio file
        audio_path = await save_audio_file(file)
        logger.info(f"📁 Audio saved to: {audio_path}")
        
        # Step 2: Transcribe audio to text
        text = transcribe_audio(audio_path)
        logger.info(f"🎤 Transcribed: {text}")
        
        # Step 3: Detect intent
        intent = detect_intent(text)
        logger.info(f"🎯 Detected intent: {intent.value}")
        
        db = next(get_db())
        response_data = {
            "transcribed_text": text,
            "intent": intent.value,
            "status": "unknown"
        }
        
        try:
            # Step 4 & 5: Extract slots and execute action based on intent
            if intent == Intent.UPDATE_BUDGET:
                slots = extract_budget_slots(text)
                if slots["category"] and slots["limit"]:
                    budget = set_budget(
                        db=db,
                        user_id=user_id,
                        category=slots["category"],
                        limit=slots["limit"]
                    )
                    response_data.update({
                        "status": "success",
                        "action": "Budget updated",
                        "category": budget.category,
                        "limit": budget.limit
                    })
                else:
                    response_data.update({
                        "status": "error",
                        "message": "Could not extract budget details. Please specify category and amount."
                    })

            elif intent == Intent.ADD_EXPENSE:
                slots = extract_transaction_slots(text)
                if slots["category"] and slots["amount"]:
                    transaction = add_transaction(
                        db=db,
                        user_id=user_id,
                        category=slots["category"],
                        amount=slots["amount"],
                        description=slots.get("description")
                    )
                    response_data.update({
                        "status": "success",
                        "action": "Expense recorded",
                        "category": transaction.category,
                        "amount": transaction.amount,
                        "transaction_id": transaction.id
                    })
                else:
                    response_data.update({
                        "status": "error",
                        "message": "Could not extract expense details. Please specify category and amount."
                    })

            elif intent == Intent.CREATE_REMINDER:
                slots = extract_reminder_slots(text)
                if slots["name"] and slots["day"]:
                    reminder = create_reminder(
                        db=db,
                        user_id=user_id,
                        name=slots["name"],
                        day=slots["day"],
                        frequency=slots.get("frequency", "monthly")
                    )
                    response_data.update({
                        "status": "success",
                        "action": "Reminder created",
                        "reminder_name": reminder.name,
                        "day": reminder.day,
                        "frequency": reminder.frequency
                    })
                else:
                    response_data.update({
                        "status": "error",
                        "message": "Could not extract reminder details. Please specify name and day."
                    })

            elif intent == Intent.CHECK_BALANCE:
                transactions = get_transactions(db=db, user_id=user_id)
                total_spent = get_total_spent(db=db, user_id=user_id)
                response_data.update({
                    "status": "success",
                    "action": "Balance retrieved",
                    "total_spent": total_spent,
                    "transaction_count": len(transactions)
                })

            else:
                response_data.update({
                    "status": "unknown",
                    "message": "Could not understand command. Please try again."
                })
        
        finally:
            db.close()
        
        # Step 6: Generate TTS response
        tts_message = generate_tts_response(response_data)
        response_data["voice_response"] = tts_message
        
        logger.info(f"✅ Voice command processed successfully")
        return JSONResponse(content=response_data, status_code=200)
        
    except Exception as e:
        logger.error(f"❌ Error processing voice command: {str(e)}")
        return JSONResponse(
            content={
                "status": "error",
                "message": f"Error processing voice command: {str(e)}"
            },
            status_code=500
        )


# Statistics endpoint
@app.get("/analytics/summary")
def get_financial_summary(user_id: int = 1):
    """
    Get financial summary including total spent, budgets, and reminders.
    """
    try:
        db = next(get_db())
        try:
            total_spent = get_total_spent(db=db, user_id=user_id)
            budgets = get_all_budgets(db=db, user_id=user_id)
            transactions = get_transactions(db=db, user_id=user_id)
            reminders = get_reminders(db=db, user_id=user_id)
            
            return {
                "user_id": user_id,
                "total_spent": total_spent,
                "transaction_count": len(transactions),
                "budget_count": len(budgets),
                "reminder_count": len(reminders),
                "budgets": [
                    {"category": b.category, "limit": b.limit} for b in budgets
                ],
                "status": "success"
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error retrieving summary: {str(e)}")
        return JSONResponse(
            content={
                "status": "error",
                "message": str(e)
            },
            status_code=500
        )


# Helper function to generate TTS response
def generate_tts_response(response_data: dict) -> str:
    """Generate a natural language response based on the action taken."""
    status = response_data.get("status", "unknown")
    
    if status == "success":
        action = response_data.get("action", "")
        if "Budget" in action:
            return f"Budget updated for {response_data.get('category')} to {response_data.get('limit')} dollars."
        elif "Expense" in action:
            return f"Expense of {response_data.get('amount')} dollars recorded for {response_data.get('category')}."
        elif "Reminder" in action:
            return f"Reminder '{response_data.get('reminder_name')}' set for day {response_data.get('day')}."
        elif "Balance" in action:
            return f"You have spent {response_data.get('total_spent')} dollars total."
    
    return "Command processed. Please check the response for details."


# Include all routers
for router in all_routers:
    app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting application on http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
