# 🎙️ VoxFin — Voice-Driven Finance System

VoxFin is a **voice-first personal finance assistant** that enables users to manage budgets, track expenses, and monitor spending using **natural language (text or voice)**.

This is the **backend API** for the VoxFin system. The backend is built with FastAPI and provides a RESTful API for voice and text-based finance operations.

For frontend please visit [this repo.](https://github.com/GIRISHKUMAR020106/VoiceDrivenUI)

---

## 🚀 What VoxFin Does

- Set and update budgets using natural language
- Record expenses using voice or text
- Check total spending and financial summaries
- Generate spoken responses (TTS)
- Maintain audit logs for financial actions
- Intent detection for finance-related commands

---

## 🧠 Core Features

### Budget Management

- Example: `set food budget to 6000`
- Stored per user and category
- API endpoint: `POST /text/process`, `POST /voice/process`

### Expense Tracking

- Example: `i spent 250 on food`
- Adds to transaction history and analytics
- Budget warnings when limits are exceeded

### Voice Interaction

- **Speech-to-Text (STT)**: Uses OpenAI Whisper for audio transcription
- **Text-to-Speech (TTS)**: Uses gTTS for voice responses
- Backend handles both STT and TTS processing

### Intent Detection

Supported intents:

- `UPDATE_BUDGET` - Set or modify budget limits
- `ADD_EXPENSE` - Record new expenses
- `CHECK_BALANCE` - View spending summaries
- `CREATE_REMINDER` - Set financial reminders
- `UNKNOWN` - Unrecognized commands

### Analytics API

- Total amount spent
- Budget summaries by category
- Reminder count and details

### Audit Logging

- All financial actions are logged for traceability

---

## 🛠️ Tech Stack

### Backend

- **FastAPI** - Modern Python web framework
- **Uvicorn** - ASGI server
- **Supabase** - Database and authentication
- **Redis** - Caching and state management
- **OpenAI Whisper** - Speech-to-text transcription
- **gTTS** - Text-to-speech synthesis
- **Transformers (FLAN-T5)** - Intent normalization via LLM
- **Python-JOSE** - JWT authentication
- **Passlib** - Password hashing with bcrypt
- **SQLAlchemy** - ORM (via Supabase client)
- **Alembic** - Database migrations

---

## 📁 Project Structure

```
VoiceDrivenFinanceSystem/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── ai/
│   │   └── parser.py           # AI command normalizer (FLAN-T5)
│   ├── api/
│   │   ├── deps.py             # API dependencies
│   │   └── routes/
│   │       ├── health.py       # Health check endpoints
│   │       └── voice.py        # Voice/text processing endpoints
│   ├── auth/
│   │   ├── security.py         # JWT authentication
│   │   └── test_auth.py        # Auth tests
│   ├── audit/
│   │   └── logger.py           # Audit logging
│   ├── cache/
│   │   ├── redis_client.py     # Redis connection
│   │   ├── state_store.py      # State management
│   │   └── test_redis.py       # Redis tests
│   ├── db/
│   │   ├── models.py           # Pydantic data models
│   │   ├── session.py          # Supabase client
│   │   ├── seed_user.py        # Default user seeding
│   │   └── migrations/         # Alembic migrations
│   ├── intent/
│   │   ├── detector.py         # Intent classification
│   │   ├── slots.py            # Slot extraction
│   │   └── state.py            # Intent state management
│   ├── services/
│   │   ├── budgets.py          # Budget CRUD operations
│   │   ├── transactions.py     # Transaction management
│   │   └── reminders.py        # Reminder management
│   ├── utils/
│   │   └── validation.py       # Input validation
│   └── voice/
│       ├── audio_preprocess.py # Audio preprocessing
│       ├── recorder.py         # Audio file handling
│       ├── stt.py              # Speech-to-text (Whisper)
│       └── tts.py              # Text-to-speech (gTTS)
├── tests/
│   ├── test_intents.py         # Intent detection tests
│   ├── test_validation.py      # Validation tests
│   └── test_voice_flow.py      # End-to-end voice flow tests
├── requirements.txt            # Python dependencies
├── pyproject.toml             # Project metadata
└── alembic.ini                # Alembic configuration
```

---

## ⚙️ Installation

### Prerequisites

- Python 3.11+
- Redis server
- Supabase project

### Setup

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies (installs from uv.lock)
uv sync

# Activate the virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Set up environment variables
cp .env.example .env
# Edit .env with your Supabase and Redis credentials
```

### Environment Variables

```env
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
REDIS_URL=redis://localhost:6379
JWT_SECRET_KEY=your_jwt_secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

---

## ▶️ Running the Backend

```bash
# Start Redis server (required)
redis-server

# Run the FastAPI server
uv run python -m uvicorn app.main:app

# API will be available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

---

## 📡 API Endpoints

### Text Processing

- `POST /text/process` - Process text commands
- `GET /text/process` - Process text commands (GET)

### Voice Processing

- `POST /voice/process` - Process voice audio files

### Analytics

- `GET /analytics/summary` - Get spending summary

### Health

- `GET /health` - Health check

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_intents.py -v
```

---

## 👥 Contributors

1. Prajan Karthik - https://github.com/USER1043
2. Girish Kumar S - https://github.com/GIRISH020106
3. Riteesh T M - https://github.com/RiteeshTM
4. Nehan G R M - https://github.com/NEHANGRM

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
