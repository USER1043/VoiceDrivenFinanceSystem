# VoxFin V2 — Plan

A voice-first personal finance tracker, built for one person's real daily use,
deployed on free infrastructure.

V1 (the hackathon build) is archived under the git tag `v1-hackathon`. V2 is a
fresh codebase; nothing from V1 is carried over except the lessons below.

---

## 1. Decisions (locked)

| Topic | Decision |
|---|---|
| Users | Several people (friends), each with fully separate data. Open sign-up (can be closed), email + password or Google sign-in, an admin who manages accounts and sees activity counts only. |
| Platform | Web app, installable as a PWA on the phone. No native app. |
| Language | English only (Indian English accents and vocabulary: "chai", "auto", "kirana", "recharge"). |
| Currency | INR only. Amounts stored as integer **paise** (`BIGINT`), never floats. |
| Payment mix | Mostly UPI. Default accounts: **UPI (bank)**, Cash, Card. |
| AI / speech | Free hosted tiers with fallbacks (see §4). No self-hosted models, no torch. |
| Hosting | **Render free web service + Neon free Postgres** on `*.onrender.com` (no domain needed, see §6). Oracle VM + domain is a later upgrade. |
| Auth | Per-user argon2 passwords and Google sign-in (OIDC + PKCE); 90-day cookie sessions stored hashed in Postgres; admin-generated one-time reset links (no email needed). |
| Timeline | No deadline; free-time project. Each milestone must leave the app usable. |

## 2. Lessons from V1 (what not to repeat)

- Three copies of the command pipeline that disagreed with each other → **one** `handle_command()` path.
- NLU stack of FLAN-T5 + regex + keywords + hardcoded categories that fought each other → **one** LLM tool-calling layer with a rule-based fallback, measured by an eval set.
- Schema defined in three places (Alembic, `init_db()`, Pydantic) that didn't match → **Alembic is the only source of schema truth**.
- Dead modules (Redis, auth, TTS, validation) and unused dependencies → nothing lands without a caller and a test.
- `user_id` from the query string → every endpoint requires a logged-in session.
- Floats for money, Python-side sums, N+1 queries → integer paise, SQL aggregates.
- Tests that didn't run → CI on every push; a red CI blocks merging.

## 3. Product scope

### Core loop
1. Tap the mic (or type): *"paid 180 for auto"*.
2. App shows a **confirmation card**: ₹180 · Transport · UPI · Today.
3. Tap ✓ (or say "yes") → saved. "Undo" is always one tap away.

Voice queries: *"how much did I spend on food this month?"* → spoken answer + chart.

### MVP (M1–M4)
- Voice or typed entry with confirmation; multi-turn follow-ups ("on what?" → "groceries").
- Manual add / edit / delete — voice is never the only way.
- Categories (tree) with **aliases** learned from use ("chai" → Food › Tea & snacks).
- Accounts: UPI, Cash, Card; income as well as expenses.
- Monthly budgets per category, alerts at 80% and 100%.
- Voice/typed questions over spending (period, category, merchant, top-N).
- Dashboard: month summary, category breakdown, trend.
- Recurring bills + push reminders (rent, recharge, subscriptions, SIP).
- CSV export.

### After MVP
- **M5 — Bank statement import** (high priority because payments are mostly UPI):
  CSV/PDF statement → parse UPI narrations (`UPI/DR/<ref>/<merchant>/...`) →
  auto-categorise using aliases + LLM → dedupe against voice-logged entries by
  amount/date/UPI ref → review screen.
- Receipt photo → transaction (Gemini vision, free tier).
- Monthly insights ("food up 30% vs last month").

## 4. AI and speech: free providers with fallbacks

Every provider sits behind a small interface with an ordered list of
implementations. Model names live in config, not code, because free tiers change.

| Role | Primary | Fallback(s) |
|---|---|---|
| Speech → text | Groq `whisper-large-v3-turbo` (free tier, ~2,000 req/day) | Browser speech recognition (used automatically when no Groq key is set) |
| Text → tool call | Groq open models (e.g. `gpt-oss-20b`) with tool calling | Gemini Flash-Lite (free tier) → rule-based parser |
| Text → speech | Browser `speechSynthesis` (on-device, free) | — |

Rules:
- The LLM **never** touches the database and never writes SQL. It may only emit
  one of: `add_transaction`, `set_budget`, `query_spending`, `create_reminder`,
  `edit_last`, `undo`, `clarify`.
- The API validates every tool call and turns it into a **pending action**; only
  a confirm writes data.
- Only the utterance plus the list of category/account names is sent to the
  LLM — never history, balances or account numbers.
- Gemini's free tier may use prompts to improve products; that is why it is the
  fallback, not the primary.
- Expected usage ≈ 30 commands/day ≈ 60 API calls/day — far inside all limits.

## 5. Architecture

```
PWA (React + Vite + TS)
  ├─ mic → audio blob ──► POST /api/voice ─► STT chain ────┐
  └─ typed text ────────► POST /api/commands ──────────────┤
                                                           ▼
                                        handle_command(text): LLM chain → tool call
                                                           ▼
                           validate → pending_action → confirm card in UI
                                                           ▼
                                POST /api/pending-actions/{id}/confirm → Postgres
```

- **Backend:** FastAPI, SQLAlchemy 2 (sync, psycopg 3), Alembic, Pydantic Settings.
  Sync is deliberate: one user, simpler code, FastAPI runs sync endpoints in a threadpool.
- **Frontend:** React + Vite + TypeScript, TanStack Query, `vite-plugin-pwa`.
- **Single origin:** the API container also serves the built frontend, so there
  is one hostname, cookie auth works without CORS, and writes from other origins are rejected.

### Data model

| Table | Key columns |
|---|---|
| `users` | email (lowercase), name, timezone, password_hash, google_sub, is_admin, disabled, last_seen_at |
| `password_resets` | token_hash, expires_at (24 h), used_at, created_by |
| `login_sessions` | token_hash (SHA-256 of the cookie token), user_agent, expires_at |
| `accounts` | name, kind (`upi`/`cash`/`card`/`bank`), is_default, archived |
| `categories` | name, kind (`expense`/`income`), parent_id, aliases[], archived |
| `transactions` | kind, amount_paise, occurred_at, account_id, category_id, merchant, note, source (`voice`/`manual`/`import`), raw_text, external_ref (UPI ref for import dedupe) |
| `budgets` | category_id, period (`monthly`), amount_paise |
| `recurring_rules` | name, amount_paise, category_id, account_id, cadence, day_of_month, next_due_on, remind_days_before, active |
| `pending_actions` | tool name, payload (JSONB), source text, status (`pending`/`confirmed`/`cancelled`/`expired`), expires_at |
| `audit_log` | action, entity, entity_id, before/after (JSONB) |

## 6. Deployment (free)

```
phone ──HTTPS──► Render free web service (one Docker image: API + PWA, password login)
                        └──TLS──► Neon free Postgres (Singapore, scales to zero)
GitHub Actions ──nightly──► encrypted pg_dump → artifact (30 days)
```

- **No domain needed:** Render provides `https://<name>.onrender.com`.
- **Auth:** password + `HttpOnly`, `Secure`, `SameSite=Lax` session cookie; login is
  rate-limited; cross-origin writes are rejected.
- **Cold starts:** Render sleeps after 15 min idle (~30–60 s wake). Optional free keep-warm
  ping (cron-job.org) during waking hours fits in the 750 free hours.
- **Neon budget:** 100 compute-hours/month, so nothing frequent may query the database.
  `/api/health` (Render health check, keep-warm ping) is DB-free; `/api/health/db` is for
  manual checks.
- **Backups:** nightly GitHub Actions `pg_dump`, GPG-encrypted, kept 30 days; restore
  procedure in `docs/DEPLOY.md` and tested.
- **Deploys:** `render.yaml` blueprint, auto-deploy from `main` only after CI passes.
- **Scheduled jobs (M4 reminders):** Render free has no cron, so a GitHub Actions schedule
  calls a token-protected endpoint.
- **Upgrade path:** Oracle Always Free VM + Cloudflare Tunnel once there is a domain; same image.

## 7. Engineering standards

- Monorepo: `api/`, `web/`, `docs/`, `ops/`.
- CI (GitHub Actions): ruff + mypy + pytest (against real Postgres) for `api/`;
  oxlint + tsc + build for `web/`; a Docker job builds and boots the production image.
- NLU **eval set** (`api/evals/commands.jsonl`): real-style phrases → expected result.
  The rule parser is gated in CI (≥ 95%); LLM providers run live on demand
  (`python -m evals.run --provider groq`). Add your own misheard phrases as they come up.
- `.env.example` documents every setting; nothing reads `os.environ` outside `config.py`.
- Migrations only through Alembic; `alembic upgrade head` runs on container start.
- Money helpers in one module; no `float` anywhere near amounts.

## 8. Milestones

| # | Milestone | Done when |
|---|---|---|
| **M0** ✅ | Foundation | Monorepo, CI green, compose up locally, schema + migrations + seed, health checks, password login, PWA shell served from the API, Render + Neon deploy, encrypted nightly backups. |
| **M1** ✅ | Manual tracker | CRUD for transactions/categories/accounts/budgets; dashboard; CSV export; usable daily without voice. |
| **M2** ✅ | Voice entry | Record → Groq STT → tool call → confirm card → saved; fallback chain tested; eval set ≥ 90%. |
| **M3** ✅ | Queries + budgets | Spending questions answered correctly; budget alerts. |
| **M4** | Reminders + polish | Recurring rules, Web Push reminders (triggered by a GitHub Actions schedule), voice undo/edit. |
| **M5** | Statement import | UPI/bank statement import with auto-categorisation and dedupe. |

Building M1 before voice is deliberate: the app is useful early, and real
entries become the eval data for M2.

## 9. Open items

- [ ] Neon + Render accounts; deploy following `docs/DEPLOY.md`.
- [ ] Backup secrets in GitHub; run one backup and one test restore.
- [ ] Optional: API keys from Groq console and Google AI Studio (voice works without them).
- [ ] Which bank(s) the statements come from (M5 parser formats).
