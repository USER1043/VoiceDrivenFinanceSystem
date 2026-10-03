# Deploying VoxFin (free: Render + Neon)

No domain or credit card needed. You get `https://<name>.onrender.com` with HTTPS, which
the microphone and the installable PWA both require.

```
phone ──HTTPS──► Render free web service (Docker: FastAPI + built PWA, password login)
                        │  TLS
                        ▼
                 Neon free Postgres (scales to zero when idle)

GitHub Actions ──nightly──► encrypted pg_dump → workflow artifact (30 days)
```

## Free-tier facts that shape this setup

| | Limit | What we do about it |
|---|---|---|
| Render | Sleeps after 15 min without traffic; wakes in ~30–60 s. 750 instance-hours/month. | Optional keep-warm ping (step 6). The UI says "waking up" meanwhile. |
| Render | Free Postgres is deleted after 30 days. | Use Neon for the database. |
| Groq / Gemini | Free quotas are shared by everyone on your instance. | Per-person command limit (section 5). |
| Neon | 100 compute-hours/month; compute sleeps after 5 min idle. 0.5 GB storage. 6 h point-in-time restore. | `/api/health` never touches the DB, so pings don't keep Neon awake. Nightly backups cover more than 6 h. |

## 1. Create the Neon database

1. Sign up at neon.com and create a project. **Region: AWS Asia Pacific (Singapore)**, to
   sit next to Render's Singapore region. Postgres version 16 or 17.
2. On the project dashboard, open **Connect** and copy the connection string.
   Turn **connection pooling off** (use the direct host, without `-pooler`): the app keeps
   its own small pool, and migrations need a direct connection.
   It looks like `postgresql://user:pass@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require`.
   The app accepts it as is.

## 2. Make your password hash

On your computer, in the repo:

```bash
cd api
uv sync
uv run python -m app.auth hash-password     # prints $argon2id$...
```

Use a long passphrase (12+ characters; four random words is good). Only the hash leaves
your machine.

## 3. Deploy on Render

1. Merge the V2 branch into `main` (the blueprint deploys `main`).
2. Sign up at render.com with GitHub, then **New → Blueprint** and pick this repository.
   Render reads `render.yaml` and asks for the three secrets:
   - `DATABASE_URL`: the Neon string from step 1
   - `OWNER_EMAIL`: your email
   - `OWNER_PASSWORD_HASH`: the hash from step 2 (paste it as is, no quotes)
3. Apply. The first build takes a few minutes. On every start the container runs the
   migrations and the seed, then serves the app.
4. Open `https://<name>.onrender.com/api/health/db`. It should say `"database": "ok"`.

From then on, Render deploys automatically after CI passes on `main`
(`autoDeployTrigger: checksPass`).

## 4. Install on your phone

Open the `onrender.com` URL in Chrome on your phone, sign in, then **⋮ → Add to Home
screen** (or **Install app**). The session lasts 90 days per device.

## 5. Friends: accounts and Google sign-in

VoxFin supports several people, each with completely separate data. The account with
`OWNER_EMAIL` is the **admin**.

- **Sign-up** is open while `SIGNUP_ENABLED=true`. Share the URL; people tap
  **Create account**. Set it to `false` in Render's **Environment** to close sign-ups
  (existing accounts keep working).
- **Forgotten passwords:** there is no email, so open **Settings → People**, tap
  **Reset link** next to the person and send them the link privately. It works once,
  for 24 hours, and signs them out of their other devices.
- **Disable** someone in the same list to sign them out everywhere and block logins.
  Their data stays.
- The **People** list shows sign-up date, last seen and activity counts, never
  anyone's transactions or amounts. Note that whoever holds the Neon database (you) can
  technically read everything in it, so tell your friends that.
- Each person gets 30 voice/typed commands per 10 minutes (`COMMANDS_PER_10_MINUTES`) so
  one heavy user can't use up the shared free AI quota.

### Google sign-in (optional, free)

1. Go to console.cloud.google.com, create a project, then open **Google Auth Platform**.
2. **Branding:** app name `VoxFin`, your email as support and developer contact.
3. **Audience:** *External*. Either click **Publish app** (anyone with a Google account
   can sign in; the basic email/profile scopes need no Google review) or stay in
   *Testing* and add your friends' Gmail addresses as test users (up to 100).
4. **Clients → Create client → Web application.** Add the authorized redirect URI
   `https://<name>.onrender.com/api/auth/google/callback` (exactly, with https).
5. In Render's **Environment**, set `PUBLIC_URL=https://<name>.onrender.com`,
   `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`, then redeploy. A **Continue with
   Google** button appears on the login screen.

Signing in with Google using the same email as an existing account links the two, so
either method works afterwards. People who joined with Google can add a password under
**Settings → Your account**.

## 6. Voice keys (optional, free)

Voice works without any keys: the browser turns speech into text, and a built-in rule
parser understands phrases like "paid 180 for auto", "set food budget to 6000" or "how much
did I spend on food last month?". Questions are answered from the database; the LLM only
works out what was asked and never sees amounts.
Keys make it better at accents and free-form phrasing:

| Key | Where | What it adds |
|---|---|---|
| `GROQ_API_KEY` | console.groq.com → API Keys | Whisper speech-to-text on the server, plus an LLM that understands free-form commands |
| `GEMINI_API_KEY` | aistudio.google.com → Get API key | Backup LLM if Groq is down or rate-limited |

Add them in Render under **Environment**, then redeploy. The voice screen picks up the
change automatically. If a provider fails, the next one is tried, ending with the rule
parser, so a broken key never blocks logging.

Check how well a provider understands your phrases (from `api/`, with the key in `.env`):

```bash
uv run python -m evals.run --provider groq
```

## 7. Nightly backups

In GitHub: **Settings → Secrets and variables → Actions → New repository secret**:

- `BACKUP_DATABASE_URL`: the same Neon connection string
- `BACKUP_PASSPHRASE`: a long random string. **Also save it in your password manager**;
  without it the backups can't be opened.

Then **Actions → Backup → Run workflow** once to check it works. After that it runs every night
at 03:00 IST and keeps 30 days of encrypted dumps as workflow artifacts. They are
encrypted because artifacts of a public repository can be downloaded by any signed-in
GitHub user.

> GitHub pauses scheduled workflows after 60 days without repository activity. Regular
> commits prevent this; otherwise re-enable it from the Actions tab.

### Restore (test this once, before you need it)

1. Download the artifact zip from the Backup run and unzip it.
2. Decrypt and restore into a new Neon branch (or the main one):

```bash
gpg --decrypt voxfin-<stamp>.sql.gz.gpg | gunzip | psql "<neon connection string>"
```

## 8. Optional: keep it awake

Render sleeps after 15 minutes idle, so the first voice command after a break waits ~30–60 s.
To avoid that, create a free job at cron-job.org that requests
`https://<name>.onrender.com/api/health` every 10 minutes, for example from 07:00 to 00:00 IST.
That endpoint doesn't touch the database, so Neon still sleeps. About 17 hours/day is
roughly 520 of Render's 750 free hours.

## Running locally

See the README: `docker compose up --build` runs Postgres, the app and a local backup
service with `AUTH_MODE=dev` (no login).

## Later: your own VM and domain

If you get a domain, an Oracle Cloud Always Free VM running `docker compose` (never sleeps,
no cold starts) behind a Cloudflare Tunnel is the upgrade path. The same Docker image works
unchanged, and the password login stays.
