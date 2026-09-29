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

## 5. Nightly backups

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

## 6. Optional: keep it awake

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
