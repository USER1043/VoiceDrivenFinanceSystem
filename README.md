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

## 🏗️ System Architecture
Frontend (React + Web APIs)
├─ UI (Chat‑style interface)
├─ Speech Recognition (STT)
├─ Speech Synthesis (TTS)
└─ Axios API Client
↓
Backend (FastAPI)
├─ Intent Detection
├─ Slot Extraction
├─ Business Logic
├─ Database (SQLAlchemy)
└─ Analytics
