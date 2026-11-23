# ClipForge

Turn a long video (YouTube link or upload) into short, scored, **vertical 9:16 clips with animated
word-by-word captions**, edit them, and publish to **YouTube Shorts** and **Instagram Reels**.

* **Local transcription** with faster-whisper (CPU by default, NVIDIA GPU auto-detected), optional
  WhisperX word alignment and speaker diarization.
* **Gemini** picks 5-10 self-contained highlights and scores them (hook, payoff, emotion,
  standalone), with a title, post caption and hashtags. Long videos are chunked.
* **Smart reframe**: MediaPipe face tracking, active-speaker following (with diarization),
  automatic split screen for two people, smooth camera with dead-zone and hard cuts.
* **Remotion** renders the final 1080x1920 clip: crop path + animated captions in 4 styles, emoji.
* **Editor**: trim against the source, fix caption words, switch style, edit post copy, re-render.
* **Publishing**: OAuth-connected YouTube and Instagram accounts, background uploads with status.
* Live progress over Server-Sent Events, bulk zip download, per-user projects.

```
 Next.js ──REST/SSE──▶ FastAPI ──Celery/Redis──▶ worker (default):    download · Gemini · face tracking · publish
    │                     │                       worker-transcribe:   faster-whisper (GPU/CPU)
    │ presigned PUT/GET   │ SQL                   worker (render q):   cut segment ─HTTP─▶ renderer (Remotion + Chrome)
    ▼                     ▼                                                    shared /data/work volume
 S3 storage            Postgres
 (SeaweedFS locally, Cloudflare R2 in prod)
```

**Pipeline:** ingest → audio (16 kHz mono) → transcribe (chunked, word timestamps) → highlights
(Gemini JSON, validated, retried once, snapped to sentences, de-overlapped) → reframe (crop path
keyframes) → render (Remotion) → ready → (optional) publish. Every stage is idempotent, retried
on transient errors, and fails with a readable message; failed or stalled projects can be retried.

---

## Quick start (step by step, Windows)

No coding needed. Plan for about 1 hour the first time (mostly downloads).

**What you need:** Windows 10/11, 16 GB RAM recommended (8 GB minimum), ~30 GB free disk.
An NVIDIA graphics card makes transcription much faster but is optional.

### Step 1. Install WSL2 and Docker Desktop
1. Open **PowerShell as Administrator** (Start menu → type `PowerShell` → right-click → *Run as administrator*) and run:
   ```powershell
   wsl --install
   ```
   Restart the PC when it asks.
2. Install **Docker Desktop**: <https://www.docker.com/products/docker-desktop/> (keep "Use WSL 2" ticked).
   Open it once and wait until the bottom-left says **Engine running**.

### Step 2. Get the code
Either install Git (<https://git-scm.com/download/win>) and run:
```powershell
git clone https://github.com/PRiNCeKUsHW/clipforge.git
cd clipforge
```
or on GitHub click **Code → Download ZIP**, unzip it, and open PowerShell inside the unzipped folder
(in File Explorer: click the address bar, type `powershell`, press Enter).

### Step 3. Get a free Gemini API key
Go to <https://aistudio.google.com/apikey>, sign in with Google, click **Create API key**, copy it.
(Gemini picks the best moments. It is the only online service the app uses; the free tier is enough.)

### Step 4. Run the setup script
In PowerShell, inside the project folder:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```
It creates your `.env` file, generates the secret keys, asks you to paste the Gemini key, detects an
NVIDIA GPU, builds everything and opens <http://localhost:3000>. **The first build takes 10–30 minutes.**

### Step 5. Make clips
1. On <http://localhost:3000> click **Sign up** (any email + password; it only lives on your PC).
2. **New project** → paste a YouTube link (or upload a video file).
   Optional: tell it what you want, e.g. *"only funny moments"*.
3. Under **Clip style** choose captions on/off and a layout (see the table in [Using it](#4-using-it)).
4. Click **Generate clips** and watch the progress. A 10-minute video takes roughly 10–20 minutes on
   CPU (the first run also downloads the speech model, ~1.5 GB).
5. Open a clip to **edit** (layout, caption style, trim, title/hashtags) and **Re-render**, or click
   **MP4** / **Download all (.zip)**.
6. Upload the MP4s to YouTube Shorts / Instagram Reels yourself, or set up auto-publishing
   ([docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#4-youtube-publishing-google-cloud), needs your own Google/Meta developer app).

### Every day after that
Run in the project folder:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start.ps1
```

It starts Docker Desktop if needed, starts the app (with the GPU if you have one; add `-Cpu` to skip it)
and opens <http://localhost:3000>. To do it by hand instead: start **Docker Desktop**, wait for
*Engine running*, run `docker compose up -d` (with an NVIDIA GPU:
`docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d`) and open <http://localhost:3000>.

To stop it: `docker compose stop`. To get updates: `git pull` then run the setup script again.

### Tips
* Keep clips under 60 s (the default). YouTube blocks claimed Shorts longer than 1 minute.
* Re-uploading TV shows, films or other creators' videos can get copyright claims or blocks. Use content you have rights to.
* If a project says **"This looks stuck"**, click **Retry**. Finished steps are skipped.
* More fixes are in [Troubleshooting](#8-troubleshooting).

---

## 1. Prerequisites (Windows)

1. **WSL2**: in an *Administrator* PowerShell: `wsl --install`, reboot. If `wsl --status` errors
   with `REGDB_E_CLASSNOTREG`, reinstall WSL: `winget install -e --id Microsoft.WSL --force`.
2. **Docker Desktop** (WSL 2 engine): <https://www.docker.com/products/docker-desktop/>.
3. **Gemini API key** (free): <https://aistudio.google.com/apikey>.

## 2. Configure

```powershell
copy .env.example .env
```

Set at least `GEMINI_API_KEY`, `JWT_SECRET` and `TOKEN_ENCRYPTION_KEY` (commands to generate
them are in the file). Everything else has working local defaults. Secrets stay in `.env` (git-ignored).

## 3. Run

```powershell
docker compose up -d --build                                                    # CPU
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build    # NVIDIA GPU
```

| URL | |
|---|---|
| <http://localhost:3000> | the app: sign up, paste a link |
| <http://localhost:8000/docs> | API docs (Swagger) |
| <http://localhost:8888> | storage file browser (SeaweedFS) |

First run downloads the Whisper model into the `whisper-models` volume (cached afterwards).

```powershell
docker compose logs -f worker worker-transcribe renderer   # watch the pipeline
docker compose stop                                         # stop, keep data
docker compose down -v                                      # stop and wipe everything
```

### GPU (optional)

Install a current NVIDIA driver on Windows (it includes WSL support), then check
`docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi` and start with the GPU
override above. `WHISPER_DEVICE=auto` switches to `large-v3-turbo`/float16. On a small GPU set
`WHISPER_BEAM_SIZE=1` for ~2x faster transcription.

### Speaker diarization (optional)

`DIARIZE=true` + a free `HF_TOKEN` (accept the terms of `pyannote/speaker-diarization-3.1` and
`pyannote/segmentation-3.0`), and build with WhisperX: `$env:INSTALL_WHISPERX="true"; docker compose up -d --build`.
With speaker labels the reframe follows whoever is talking.

## 4. Using it

1. **New project**: paste a YouTube link or upload a file; optionally tell Gemini what you want
   ("only funny moments"). Under **Clip style** pick captions on/off and a layout:
   | Layout | Looks like | Best for |
   |---|---|---|
   | Smart | follows the speaker, splits automatically for two people side by side | anything |
   | Podcast split | two speakers stacked top/bottom, captions on the seam | podcasts, interviews |
   | Full face | one full-screen crop following whoever talks | solo talking head |
   | Title + video | whole frame in the middle, clip topic above, captions below, blurred background | tech, gameplay, tutorials |
   | Blur fit | whole frame in the middle on a blurred background | screen recordings, wide shots |

   Clips are capped at 59 s (YouTube blocks claimed Shorts over 1 minute) and letterbox bars baked
   into films are removed automatically.
2. Watch live progress: downloading → transcribing → finding highlights → reframing → rendering.
3. **Clips grid**: sorted by virality score; play, download, or *Download all (.zip)*.
4. **Edit** a clip:
   * *Captions*: pick a style (Bold pop, Karaoke, Clean, Hype), fix words (clear one to hide it).
   * *Trim*: preview the source, nudge start/end, "Set" from the player.
   * *Details*: hook title, description, hashtags.
   * Click **Re-render** to apply changes.
5. **Publish**: connect accounts on *Connected accounts* (needs OAuth credentials, see
   [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#4-youtube-publishing-google-cloud)), then publish from the editor.

## 5. Tests

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements-dev.txt -r worker\requirements-dev.txt pgserver
cd worker;   ..\.venv\Scripts\python -m pytest; cd ..
cd backend;  ..\.venv\Scripts\python -m pytest; cd ..
cd frontend; npm install; npm test; cd ..
cd renderer; npm install; npm test; cd ..
```

| Suite | Covers |
|---|---|
| worker (pytest) | Gemini JSON validation + retry, sentence snapping, overlap removal, chunking, chunked transcription at quiet points, GPU/CPU detection, face tracking / speaker mapping / smoothing / split-screen planning, render props + render-service client, YouTube resumable upload + Instagram container flow (mocked HTTP), real ffmpeg |
| backend (pytest, real Postgres) | migrations match models, auth, uploads, privacy between users, SSE, retry/stall, clip editing (trim re-slicing keeps caption edits), re-render, zip download, OAuth state/redirect/callback, encrypted tokens, publish jobs |
| frontend (Vitest) | formatting, error mapping, YouTube URL parsing, SSE parsing, caption line grouping, time parsing |
| renderer (Vitest) | caption grouping, active word, emoji, crop interpolation and placement |

CI runs all four on every push (`.github/workflows/ci.yml`).

## 6. Key concepts

* **Celery + Redis**: task queue. Queues: `default`, `transcribe` (own worker, concurrency 1),
  `render`. Transient errors (network, 429/5xx) retry with backoff.
* **SSE**: the API relays worker progress (Redis pub/sub) to the browser's `EventSource`.
* **Presigned URLs**: the browser uploads/downloads directly to storage; videos never pass through the API.
* **Chunked transcription**: audio is transcribed in 10-minute pieces split at the quietest moment,
  so memory stays flat for multi-hour videos.
* **Crop path**: the reframe stage stores keyframes (`{t, x}`) per clip; Remotion interpolates
  them per frame. `layout` is `single`, `split` (two panels) or `fit` (already vertical).
* **Remotion**: the composition is React; the render service bundles it once and renders each
  clip with its props (words, crop, style). Free for individuals/small teams; companies need a license.

## 7. Repository layout

```
backend/    FastAPI (api/, core/, models/, schemas/, services/), Alembic migrations, tests
worker/     Celery tasks: ingest, transcription, highlights, reframe, render client, publish
renderer/   Remotion composition (captions, styles, crop) + render service
frontend/   Next.js 16 (App Router) + Tailwind + shadcn/ui + TanStack Query
scripts/    setup.ps1: one-time Windows setup (creates .env, secrets, starts Docker)
            start.ps1: daily start (launches Docker Desktop, starts the app, opens the browser)
deploy/     Caddyfile for production
docs/       DEPLOYMENT.md (VPS, Vercel, Railway/Render, R2, Google + Meta app setup)
```

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| Docker Desktop: "initializing Secrets Engine … The file cannot be accessed by the system" | Docker wasn't shut down cleanly. Click **Quit** (not *Reset to factory defaults*) and run `scripts\start.ps1`, which clears the leftover socket |
| "GEMINI_API_KEY is not set" | add it to `.env`, `docker compose up -d`, then **Retry** |
| Project stuck, "This looks stuck" | a worker restarted mid-task; click **Retry** (finished steps are skipped) |
| Workers die on long videos | raise Docker's memory: `%USERPROFILE%\.wslconfig` → `[wsl2]` `memory=10GB`, then `wsl --shutdown` |
| Rendering slow | it's CPU-bound Chrome; lower `RENDER_CONCURRENCY` if memory is tight, raise it if you have cores |
| YouTube 403 / "confirm you're not a bot" | retry later, rebuild the worker (new yt-dlp), or set `YTDLP_COOKIES_FILE` |
| Connect buttons say "Not configured" | set the Google/Meta OAuth credentials in `.env` |
| Instagram: "needs a public URL" | Instagram can't reach localhost; use R2 + `PUBLIC_MEDIA_BASE_URL` |
| No faces tracked | MediaPipe's model favours faces that are reasonably large; wide shots fall back to centre crop. `REFRAME_DETECTOR=haar` is an alternative |

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for production.
