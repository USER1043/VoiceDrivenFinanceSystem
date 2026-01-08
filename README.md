# 🎙️ VoxFin — Voice‑Driven Finance System

VoxFin is a **voice‑first personal finance assistant** that enables users to manage budgets, track expenses, and monitor spending using **natural language (text or voice)**.

The project is built with a **clean frontend–backend separation**, making it scalable, testable, and production‑ready.

---

## 🚀 What VoxFin Does

- Set and update budgets using natural language  
- Record expenses using voice or text  
- Check total spending and financial summaries  
- Generate spoken responses (TTS)  
- Maintain audit logs for financial actions  

---

## 🧠 Core Features

### ✅ Budget Management
- Example: `set food budget to 6000`
- Stored per user and category

### ✅ Expense Tracking
- Example: `i spent 250 on food`
- Adds to transaction history and analytics

### ✅ Voice Interaction
- **Speech‑to‑Text (STT)** handled in frontend
- **Text‑to‑Speech (TTS)** handled in frontend
- Backend remains **text‑only and deterministic**

### ✅ Intent Detection
Supported intents:
- `UPDATE_BUDGET`
- `ADD_EXPENSE`
- `CHECK_BALANCE`
- `CREATE_REMINDER`
- `UNKNOWN`

### ✅ Analytics
- Total amount spent
- Budget summaries
- Reminder count

### ✅ Audit Logging
- All financial actions are logged for traceability

---

## Tech Stack

### Frontend
- React (Vite)
- JavaScript (ES6+)
- CSS (custom glassmorphism UI)
- Browser Audio APIs (WAV-ready recording)
- Axios for API communication

### Backend (Integrated / Planned)
- FastAPI
- Whisper (Speech-to-Text)
- Intent classification (rule-based / LLM-assisted)
- PostgreSQL / Redis (optional)

---

## Project Structure
frontend/
├── src/
│   ├── components/
│   │   ├── Header.jsx
│   │   ├── VoiceInput.jsx
│   │   └── ResultCard.jsx
│   │
│   ├── pages/
│   │   └── Dashboard.jsx
│   │
│   ├── services/
│   │   └── api.js
│   │
│   ├── utils/
│   │   └── wavEncoder.js
│   │
│   ├── App.jsx
│   ├── main.jsx
│   └── index.css

backend/
├── app/
│   ├── main.py                 # FastAPI app entry point
│   │
│   ├── core/
│   │   ├── config.py           # App config, env vars
│   │   ├── security.py         # Auth, API keys, guards (future)
│   │   └── logging.py          # Audit & request logging
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── voice.py            # Voice & text endpoints
│   │   └── health.py           # Health / test endpoints
│   │
│   ├── voice/
│   │   ├── __init__.py
│   │   ├── recorder.py         # Save uploaded audio (.wav)
│   │   ├── stt.py              # Speech-to-text (Whisper)
│   │   └── tts.py              # Text-to-speech (optional)
│   │
│   ├── intent/
│   │   ├── __init__.py
│   │   ├── classifier.py       # Intent detection logic
│   │   └── rules.py            # Rule-based fallback
│   │
│   ├── services/
│   │   ├──

