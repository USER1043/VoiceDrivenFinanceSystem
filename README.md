# 🎙️ VoxFin — Voice‑Driven Finance System

VoxFin is a **voice‑first personal finance assistant** that enables users to manage budgets, track expenses, and monitor spending using **natural language (text or voice)**.

The project is built with a **clean frontend–backend separation**, making it scalable, testable, and production‑ready.

This repo only contains the backend, for frontend please visit [this repo.](https://github.com/GIRISHKUMAR020106/VoiceDrivenUI)

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
    │
    backend/
    ├── app/
    │   ├── main.py                 
    │   │
    │   ├── core/
    │   │   ├── config.py           
    │   │   ├── security.py         
    │   │   └── logging.py           
    │   │
    │   ├── api/
    │   │   ├── __init__.py
    │   │   ├── voice.py

---

---

## ⚙️ Tech Stack

### Backend
- FastAPI
- SQLAlchemy
- SQLite / PostgreSQL
- Python 3.11
- Uvicorn

### Frontend
- React (Vite)
- Axios
- Web Speech API (STT & TTS)
- CSS

---

## ▶️ Running the Project

### Backend

```bash
cd VoiceDrivenFinanceSystem
uv run python -m uvicorn app.main:app --reload
```
### Frontend
```bash
npm install
npm run dev
http://localhost:5173
```

---

### Contributors
1. Prajan Karthik -  https://github.com/USER1043
2. Girish Kumar S - https://github.com/GIRISH020106
3. Riteesh T M - https://github.com/RiteeshTM
4. Nehan G R M - https://github.com/NEHANGRM

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.





