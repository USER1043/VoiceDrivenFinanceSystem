# VoxFin

A voice-first personal finance tracker: say *"paid 180 for auto"*, confirm the card, done.
Built for one person's real daily use (INR, UPI-first), deployed on free infrastructure.

> **Status: V2, milestone M0 (foundation).** See [`docs/V2_PLAN.md`](docs/V2_PLAN.md) for the
> full plan and milestones. The original hackathon code is archived at the `v1-hackathon` tag.

## Stack

| Part | Tech |
|---|---|
| API | FastAPI · SQLAlchemy 2 · Alembic · Postgres 16 · Pydantic Settings |
| Web | React · Vite · TypeScript · TanStack Query · installable PWA |
| Auth | Password login (argon2) with hashed, revocable cookie sessions |
| Speech / AI (M2) | Groq Whisper + Groq LLM tool calling, Gemini fallback (free tiers) |
| Deploy | One Docker image (API serves the built PWA) on Render's free tier, Neon free Postgres, nightly encrypted backups via GitHub Actions |

## Layout

```
api/            FastAPI app, Alembic migrations, tests
  app/          config, db, models, auth, seed, routers
  migrations/   the only source of schema truth
web/            React PWA
ops/            local backup script (docker compose)
docs/           plan and deployment guide
Dockerfile      builds web + api into one image
docker-compose.yml   local stack: db, app, backups
render.yaml          Render deploy blueprint
```

## Run it locally

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Node 22.

```bash
cp .env.example .env            # set OWNER_EMAIL and POSTGRES_PASSWORD (+ DATABASE_URL to match)

# Local runs use AUTH_MODE=dev (no login). To try the login screen locally, set
# AUTH_MODE=password and OWNER_PASSWORD_HASH from `cd api && uv run python -m app.auth hash-password`.

# Option A: everything in Docker, production-like → http://localhost:8000
docker compose up --build

# Option B: hot reload
docker compose up -d db
cd api && uv sync && uv run alembic upgrade head && uv run python -m app.seed
uv run uvicorn app.main:app --reload         # API on :8000
cd ../web && npm install && npm run dev      # PWA on :5173, proxies /api to :8000
```

API docs: http://localhost:8000/api/docs

## Checks (same as CI)

```bash
cd api
uv run ruff format --check . && uv run ruff check . && uv run mypy app
TEST_DATABASE_URL=postgresql+psycopg://voxfin:<password>@localhost:5432/voxfin_test uv run pytest
uv run alembic check          # models and migrations agree

cd ../web
npm run lint && npm run build
```

Tests run against a real Postgres database (create `voxfin_test` first:
`docker compose exec db createdb -U voxfin voxfin_test`).

## Changing the schema

1. Edit `api/app/models.py`.
2. `uv run alembic revision --autogenerate -m "what changed"` and review the generated file.
3. `uv run alembic upgrade head`. Containers apply migrations on start.

## Deploying

See [`docs/DEPLOY.md`](docs/DEPLOY.md).

## License

MIT; see [LICENSE](LICENSE).
