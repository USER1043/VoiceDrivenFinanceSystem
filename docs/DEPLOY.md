# Deploying VoxFin

Target: one small always-on VM running `docker compose`, reachable only through a
Cloudflare Tunnel, with Cloudflare Access doing the login. Total cost: ₹0.

```
phone ──HTTPS──► Cloudflare Access (email one-time code)
                        │
                 Cloudflare Tunnel (outbound from the VM, no open ports)
                        │
          VM: cloudflared → app (API + PWA) → postgres
                                backup (nightly pg_dump → ./backups)
```

## 1. Get a VM

**Preferred: Oracle Cloud Always Free.** Create an *Ampere A1* instance (Ubuntu 24.04, 1–2 OCPU,
6–12 GB RAM is plenty). Keep the default security list: you do **not** need to open any ports,
since the tunnel dials out.

Install Docker:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # log out and back in
```

**Fallback: Render + Neon.** Build the same `Dockerfile` as a Render web service, set
`DATABASE_URL` to a Neon connection string (`postgresql+psycopg://...?sslmode=require`), and
add Cloudflare in front via a custom domain. Expect ~30–60 s cold starts after idle.

## 2. Cloudflare (free plan)

You need a domain on Cloudflare (any cheap domain works).

1. **Zero Trust → Networks → Tunnels → Create tunnel** (type *Cloudflared*). Copy the token.
   Add a *public hostname*, e.g. `money.yourdomain.com`, service `http://app:8000`.
2. **Zero Trust → Access → Applications → Add → Self-hosted** for `money.yourdomain.com`.
   Policy: *Allow*, include *Emails* = your email. Login method: one-time PIN.
   Copy the application's **AUD tag**.
3. Your team domain is shown under **Zero Trust → Settings → Custom pages**
   (`<team>.cloudflareaccess.com`).

## 3. Configure and start

```bash
git clone https://github.com/USER1043/VoiceDrivenFinanceSystem.git voxfin && cd voxfin
cp .env.example .env
```

Edit `.env`:

```
ENVIRONMENT=production
OWNER_EMAIL=<the email allowed in Access>
POSTGRES_PASSWORD=<long random string>
AUTH_MODE=cloudflare
CF_ACCESS_TEAM_DOMAIN=<team>.cloudflareaccess.com
CF_ACCESS_AUD=<AUD tag>
CLOUDFLARE_TUNNEL_TOKEN=<tunnel token>
```

```bash
docker compose --profile tunnel up -d --build
docker compose ps           # all healthy
```

Open `https://money.yourdomain.com` on your phone, log in with the emailed code, then
*Add to Home Screen*.

## 4. Update

```bash
git pull && docker compose --profile tunnel up -d --build
```

Migrations and the seed run automatically when the app container starts.

## 5. Backups and restore

Dumps land in `./backups/voxfin-<timestamp>.sql.gz` daily, kept for `BACKUP_KEEP_DAYS`.
Offsite copies (Cloudflare R2 / Google Drive) are planned for M4. Until then, occasionally
copy the folder off the VM.

Restore (test this once, before you need it):

```bash
gunzip -c backups/voxfin-<stamp>.sql.gz | docker compose exec -T db psql -U voxfin voxfin
```
