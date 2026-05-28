# Production deploy

Pipeline: **push to `main` → tests (CI) → build images (GHCR) → SSH deploy on VPS**.

Edge **proxy** holds ports 80/443; app containers roll one-by-one with healthchecks.

## One-time VPS setup

1. Install Docker Engine + Compose v2 (`docker compose version` ≥ 2.20).

2. Clone the repo, e.g. `/opt/rsd`, copy `.env` (app secrets) and deploy config:

   ```bash
   cp .env.deploy.example .env.deploy
   # REGISTRY=ghcr.io/<your-github-username-lowercase>
   ```

3. TLS certs in `./ssl/` (`fullchain.pem`, `privkey.pem`) — same as before.

4. GHCR read access (private packages):

   ```bash
   # PAT: read:packages
   echo "$TOKEN" | docker login ghcr.io -u YOUR_USER --password-stdin
   ```

   Or set `GHCR_TOKEN` / `GHCR_USER` in `.env.deploy`.

5. GitHub **repository secrets** (Settings → Secrets → Actions):

   | Secret | Purpose |
   |--------|---------|
   | `VPS_HOST` | Server IP or hostname |
   | `VPS_USER` | SSH user |
   | `VPS_SSH_KEY` | Private key (full PEM) |
   | `VPS_APP_PATH` | e.g. `/opt/rsd` |

6. GitHub **environment** `production` (optional): required reviewers before deploy.

7. Optional **secrets** for frontend build in CI: `VITE_GOOGLE_CLIENT_ID`, `VITE_WIDGET_*`.

8. First deploy (after images exist on GHCR):

   ```bash
   export IMAGE_TAG=<git-sha-or-main>
   bash scripts/deploy.sh
   ```

   This starts **proxy** on 443 instead of the old frontend container.

## Day-to-day

- Merge to `main` → automatic CD after green tests.
- Manual: Actions → **CD** → **Run workflow**.

On the server, deploy never runs `docker compose build` — only `pull` + rolling `up`.

## Local development

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Uses bind mounts and `frontend/nginx.conf` (all-in-one nginx with TLS).

## Rollback

```bash
# on VPS
export IMAGE_TAG=<previous-sha>
bash scripts/deploy.sh
```

DB: prefer additive migrations; rollback code does not auto-revert schema.

## Files

| File | Role |
|------|------|
| `docker-compose.yml` | Base stack |
| `docker-compose.prod.yml` | GHCR images + edge proxy |
| `docker-compose.dev.yml` | Local mounts + dev nginx |
| `deploy/nginx/nginx.conf` | TLS + routing (prod) |
| `scripts/deploy.sh` | Pull → migrate → rolling update |
