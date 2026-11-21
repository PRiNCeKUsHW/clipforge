# Deploying ClipForge

Three pieces need a home:

| Piece | Needs | Where |
|---|---|---|
| **Frontend** (Next.js) | static + small Node server | the VPS (with Caddy) **or** Vercel |
| **API + workers + renderer** | long-running containers, 4+ GB RAM, ffmpeg, Chrome, optional GPU | a VPS (recommended), or Railway / Render |
| **Storage** | S3-compatible, public read for Instagram | **Cloudflare R2** (no egress fees) |

The simplest production setup is **one VPS running `docker-compose.prod.yml`** (Caddy gives you
HTTPS automatically) **plus R2**. Use subdomains of one domain, e.g. `app.example.com` (frontend)
and `api.example.com` (API). Because they're the same *site*, the login cookie works with the
default `SameSite=Lax`.

---

## 1. Cloudflare R2

1. Cloudflare dashboard → **R2** → *Create bucket* (e.g. `clipforge`).
2. **R2 → Manage API tokens → Create API token** with *Object Read & Write* on that bucket.
   Note the *Access Key ID*, *Secret Access Key* and your *account id*.
3. **Bucket → Settings → CORS policy**: browsers upload directly with presigned URLs, so allow your app origin:
   ```json
   [
     {
       "AllowedOrigins": ["https://app.example.com"],
       "AllowedMethods": ["GET", "PUT", "HEAD"],
       "AllowedHeaders": ["*"],
       "ExposeHeaders": ["ETag"],
       "MaxAgeSeconds": 3600
     }
   ]
   ```
4. **Public access (needed for Instagram):** *Bucket → Settings → Custom domains → Connect domain*
   (e.g. `media.example.com`). Instagram downloads the clip from that URL.
   Only `clips/` objects are ever linked publicly; uploads and sources stay unlisted but are
   technically readable by anyone who guesses the key. If that matters, use a separate public bucket for clips.
5. Environment:
   ```env
   S3_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
   S3_PUBLIC_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
   S3_ACCESS_KEY=<access key id>
   S3_SECRET_KEY=<secret access key>
   S3_BUCKET=clipforge
   S3_REGION=auto
   PUBLIC_MEDIA_BASE_URL=https://media.example.com
   ```

## 2. Option A (recommended): one VPS with Docker Compose

**Size:** 4 vCPU / 8 GB RAM minimum (transcription and rendering are CPU-heavy). For fast
transcription use a GPU server (any NVIDIA card with 4+ GB VRAM) and set `WHISPER_GPU=true`.

```bash
# on the server (Ubuntu 24.04)
curl -fsSL https://get.docker.com | sh
git clone <your repo> clipforge && cd clipforge
cp .env.example .env.prod
```

Edit `.env.prod`:

```env
APP_ENV=production
APP_DOMAIN=app.example.com
API_DOMAIN=api.example.com
FRONTEND_URL=https://app.example.com
API_PUBLIC_URL=https://api.example.com
CORS_ORIGINS=https://app.example.com
COOKIE_SECURE=true
COOKIE_SAMESITE=lax

JWT_SECRET=<python -c "import secrets; print(secrets.token_urlsafe(48))">
TOKEN_ENCRYPTION_KEY=<python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

POSTGRES_USER=clipforge
POSTGRES_PASSWORD=<long random>
POSTGRES_DB=clipforge
DATABASE_URL=postgresql+psycopg://clipforge:<same password>@postgres:5432/clipforge
REDIS_URL=redis://redis:6379/0
RENDERER_URL=http://renderer:3100

GEMINI_API_KEY=...
# + the R2 block from step 1, + OAuth credentials from steps 4/5
```

Point DNS **A records** for both domains at the server, then:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml logs -f backend worker
```

Caddy fetches HTTPS certificates on first request. **Updates:** `git pull` and re-run the `up -d --build` command.
**Backups:** `docker compose -f docker-compose.prod.yml exec postgres pg_dump -U clipforge clipforge > backup.sql` (cron it).

## 3. Option B: managed platforms

### Frontend on Vercel
* Import the repo, **Root Directory** `frontend`, framework Next.js.
* Env: `NEXT_PUBLIC_API_URL=https://api.example.com`.
* A custom domain on the same parent domain as the API (`app.example.com`) keeps cookies simple.
  If the frontend stays on `*.vercel.app` (a different site), set on the API
  `COOKIE_SAMESITE=none` and `COOKIE_SECURE=true`, and add the Vercel URL to `CORS_ORIGINS`.

### API, workers, renderer on Railway or Render
Create one service per container from this repo, all with the same env vars:

| Service | Dockerfile | Start command |
|---|---|---|
| backend | `backend/Dockerfile` (root context) | default (`alembic upgrade head && uvicorn ...`), expose port 8000 |
| worker | `worker/Dockerfile` (root context) | `celery -A clipforge_worker.celery_app worker -Q default,render -c 2` |
| worker-transcribe | `worker/Dockerfile` | `celery -A clipforge_worker.celery_app worker -Q transcribe -c 1` |
| renderer | `renderer/Dockerfile` | default, private networking only |

Add managed **PostgreSQL** and **Redis**. The worker and renderer exchange files on a shared
disk (`/data/work`); platforms that can't share a volume between services need the worker and
renderer in **one** container/service (run both processes), so a VPS is simpler. Give the
worker at least 4 GB RAM and the renderer 2 GB.

## 4. YouTube publishing (Google Cloud)

1. <https://console.cloud.google.com> → new project → **APIs & Services → Library → YouTube Data API v3 → Enable**.
2. **OAuth consent screen**: External, app name, support email, scopes
   `.../auth/youtube.upload` and `.../auth/youtube.readonly`. While in *Testing*, add your Google account under **Test users**.
3. **Credentials → Create credentials → OAuth client ID → Web application**.
   Authorized redirect URI: `https://api.example.com/api/oauth/youtube/callback`
   (locally: `http://localhost:8000/api/oauth/youtube/callback`).
4. Set `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`, restart, then **Connected accounts → Connect**.

**Limits to know:**
* Projects that haven't passed Google's **API audit** can only upload **private** videos
  (the API forces `private`). Request the audit from the YouTube API Services form once the app is live.
* Default quota is **10,000 units/day**; one upload costs ~**1,600** units, so about 6 uploads a day.
* Videos ≤ 3 minutes in vertical format are classified as Shorts; ClipForge also adds `#Shorts` to the title.

## 5. Instagram Reels publishing (Meta)

1. Your Instagram account must be a **Professional (Business or Creator)** account **linked to a Facebook Page** you manage.
2. <https://developers.facebook.com> → *Create app* → type **Business** → add **Facebook Login for Business** and **Instagram Graph API**.
3. Facebook Login → Settings → **Valid OAuth Redirect URIs**: `https://api.example.com/api/oauth/instagram/callback`.
4. Permissions used: `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management`.
   In development mode only app roles (you) can connect; other users need **App Review** for these permissions.
5. Set `META_APP_ID` / `META_APP_SECRET` (and `META_GRAPH_VERSION` to a current version).
6. **Public video URL:** Instagram fetches the video itself, so `PUBLIC_MEDIA_BASE_URL` (R2 custom domain)
   must be set. Local `http://localhost` storage can't be reached by Instagram.

Tokens are long-lived (~60 days); reconnect the account when it expires (the accounts page shows the date).

## 6. Production checklist

- [ ] `APP_ENV=production` (the API refuses to start with the default `JWT_SECRET`)
- [ ] Unique `JWT_SECRET`, `TOKEN_ENCRYPTION_KEY`, Postgres password; `.env.prod` never committed
- [ ] `COOKIE_SECURE=true`, HTTPS everywhere, `CORS_ORIGINS` lists only your frontend
- [ ] R2 CORS restricted to your app origin
- [ ] Database backups scheduled
- [ ] `MAX_UPLOAD_MB` / `MAX_VIDEO_MINUTES` set to what your server can handle
- [ ] Remotion license if your company has more than 3 people (`REMOTION_LICENSE_KEY`)
