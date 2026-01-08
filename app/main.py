# from fastapi import FastAPI, Depends, UploadFile, File
# from sqlalchemy.orm import Session

# from app.db.session import get_db
# from app.voice.recorder import save_audio_file
# from app.voice.stt import transcribe_audio
# from app.intent.detector import detect_intent, Intent
# from app.intent.slots import (
#     extract_budget_slots,
#     extract_reminder_slots,
#     extract_transaction_slots
# )
# from app.services.budgets import set_budget
# from app.services.reminders import create_reminder
# from app.services.transactions import add_transaction

# app = FastAPI(title="Voice Driven Finance API")

from fastapi import FastAPI
from app.api.routes import all_routers

app = FastAPI(
    title="Voice Driven Finance System",
    version="1.0.0"
)

@app.get("/")
def root():
    return {"message": "Voice Driven Finance System API is running"}

for router in all_routers:
    app.include_router(router)
