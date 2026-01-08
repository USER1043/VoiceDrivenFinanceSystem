# 🎙️ VoxFi — Voice‑Driven Finance System

VoxFi is a **voice‑first personal finance assistant** that allows users to manage budgets, track expenses, and check spending using **natural language (text or voice)**.

The system is designed with a **clean separation of concerns**:
- **Frontend** handles UI, Speech‑to‑Text (STT), and Text‑to‑Speech (TTS)
- **Backend** handles intent detection, slot extraction, business logic, database persistence, and analytics

This architecture makes the system **scalable**, **modular**, and **production‑ready**.

---

## 🧠 Core Features

### ✅ Budget Management
- Set or update budgets using natural language  
  _Example_: `set food budget to 6000`
- Budgets are stored per user and category

### ✅ Expense Tracking
- Record expenses via text or voice  
  _Example_: `i spent 250 on food`
- Expenses contribute to analytics and balance checks

### ✅ Voice Support
- **STT**: Converts speech → text (frontend)
- **TTS**: Converts system response → speech (frontend)
- Backend remains **voice‑agnostic** and works purely on text

### ✅ Intent Detection
Supported intents:
- `UPDATE_BUDGET`
- `ADD_EXPENSE`
- `CHECK_BALANCE`
- `CREATE_REMINDER`
- `UNKNOWN`

### ✅ Analytics
- Total spending
- Budget summaries
- Reminder count

### ✅ Audit Logging
- All financial actions are logged for traceability

---

## 🏗️ System Architecture

