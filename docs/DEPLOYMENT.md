# Hosting plan

> **Current state (Nov 2026):** phase 2 is live. The web app runs on Vercel at https://alwayshome-mvp.vercel.app and the API (`alwayson-api`) is a Docker container on Render's free plan, deployed from `render.yaml`. The Streamlit app is kept as an internal test bench. The rest of this file is the plan as written on Nov 6, kept for the record.

Two phases. Phase 1 puts the current Streamlit app online today, for judging and as a backup if a laptop fails. Phase 2 is the real product: a React frontend on Vercel talking to a Python API.

## Constraints that drive the design

| Constraint | Consequence |
|---|---|
| Judging is today at 6 PM; presentation on Nov 18 | Phase 1 must take minutes; phase 2 can take days |
| The logic is Python with geospatial libraries (geopandas, shapely, pyproj) and 25 MB of parquet | Too heavy for serverless functions (Vercel Python: size limit, cold starts). The API needs a container |
| Reading a policy PDF with Claude takes 10 to 20 seconds | Needs a host without short request timeouts |
| The repo is public, and the Claude key costs money | Key only on the server; password and per-visitor AI limits on any public URL |
| Policies contain personal data | PDFs processed in memory, never stored; no personal fields extracted (already true) |

## Phase 1: Streamlit Community Cloud (today, about 10 minutes)

Free, deploys straight from GitHub, built for exactly this app.

1. Go to https://share.streamlit.io and sign in with the GitHub account that owns the repo (joaquinramirezg).
2. **Create app** → repository `joaquinramirezg/alwayshome`, branch `main`, main file `app.py`.
3. **Advanced settings**:
   - Python version: 3.14 if offered, otherwise 3.13 (the code needs 3.12 or newer).
   - Secrets (TOML):
     ```toml
     ANTHROPIC_API_KEY = "sk-ant-..."
     APP_PASSWORD = "pick-a-password"     # remove this line to make the app open to everyone
     AI_CALLS_PER_SESSION = "10"          # cap on paid AI calls per visitor
     ```
4. Deploy. The first build takes a few minutes. You get a URL like `https://alwayson-....streamlit.app`.

What the app already does for hosting: reads these secrets, asks for the password when `APP_PASSWORD` is set, caps AI calls per visitor, and serves the sample policies and demo addresses from cached results (no AI cost). Dependencies come from `requirements.txt`.

If the build fails on the Python version or on installing the project from `pyproject.toml`, pick 3.13 and redeploy, or send the build log.

## Phase 2: React frontend + Python API

```
Browser ──> Next.js app on Vercel (React, TypeScript)
               │  fetch JSON
               ▼
            AlwaysHome API: FastAPI in a Docker container (Google Cloud Run, Render or Railway)
               │  same Python modules as the Streamlit app: wildfire, gaps, assess, policy_extract, report
               ├─> data/processed/*.parquet (shipped inside the image)
               ├─> Census geocoder (address -> tract)
               └─> Claude API (policy PDFs, report rewrite), key stored as a server secret
```

Streamlit stays as the internal test bench: same backend code, so every feature is tested in both.

### Backend: done and tested

- `api/main.py`: FastAPI app. Run locally: `uv run uvicorn api.main:app --reload --port 8000`, interactive docs at http://localhost:8000/docs.
- Endpoints:

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Status, whether AI is on, which parts are real vs placeholder |
| GET | `/api/samples` | Sample homeowners and sample policy PDFs |
| GET | `/api/area?address=` | Hazard zone, fire history, ZIP insurance market |
| POST | `/api/assess` | Contract inputs → plan (validated both ways, see `docs/inputs_and_contract.md`) |
| POST | `/api/policy/extract` | Upload 1 to 2 PDFs → fields with quote, page, check, plus merged insurance |
| GET | `/api/policy/sample/{name}` | Same for a bundled sample (cached, free) |
| POST | `/api/report` | Plan → Markdown report (template, or AI rewrite) |

- Safety built in: per-IP hourly AI limit (`AI_CALLS_PER_HOUR`), 10 MB and PDF-type checks, 2 files max, CORS limited to `ALLOWED_ORIGINS`, path checks on sample names, output contract checked before anything is returned.
- `Dockerfile`: Python 3.14 slim + uv, ships only processed/demo/sample data.
- Tests: `tests/test_api.py` (18 tests, no key needed). CI: `.github/workflows/ci.yml` runs the whole suite on every push.

### Where to host the API

| Host | Fit | Notes |
|---|---|---|
| **Google Cloud Run** (recommended) | Scales to zero, long timeouts, generous free tier, deploys a Dockerfile | Needs a Google Cloud account with billing enabled |
| Render | Easiest UI, deploys the Dockerfile from GitHub | Free tier sleeps after inactivity (slow first request) |
| Railway / Fly.io | Simple, fast | Small monthly cost |
| Vercel Python functions | Not a good fit | Geospatial stack and data exceed function limits; PDF calls can hit timeouts |

Deploy to Cloud Run (once `gcloud` is set up): `gcloud run deploy alwayson-api --source . --region us-west1 --allow-unauthenticated --set-env-vars ALLOWED_ORIGINS=https://<vercel-app>.vercel.app --set-secrets ANTHROPIC_API_KEY=anthropic-key:latest`

### Frontend: built (`web/`)

Next.js 16 + TypeScript + Tailwind, four steps (Location, Your home, Insurance, Your plan) plus the report. It calls `/api/*`, which Next.js forwards to `API_URL`, so the browser never talks to the API directly (no CORS setup, and the API key never reaches the browser). Run and deploy steps: `web/README.md`.

#### Deploy both, step by step

1. **API on Render:** render.com > New > Blueprint > this repo (uses `render.yaml`, Docker). Paste `ANTHROPIC_API_KEY` when asked. Wait for the health check at `https://<name>.onrender.com/api/health`. Use the Starter plan: the free 512 MB instance may run out of memory loading the geospatial tables.
2. **Frontend on Vercel:** vercel.com > Add New Project > this repo > Root Directory `web` > env `API_URL=https://<name>.onrender.com` > Deploy.
3. Open the Vercel URL, then `/?demo=altadena_fair_only&step=4` to check the full flow.

Known risk: reading a policy PDF takes 10 to 60 seconds; if the Vercel proxy times out on it, call the API directly from the browser for that one request (set `ALLOWED_ORIGINS` on the API to the Vercel URL).

#### Original plan for the frontend

Stack: **Next.js (App Router) + TypeScript on Vercel**, Tailwind CSS with shadcn/ui components, react-hook-form + zod (forms mirror `validate_inputs`), TanStack Query for API calls, react-markdown for the report, MapLibre or Leaflet for the map.

Screens, one step at a time:

1. **Address**: autocomplete input; map of the census tract with the hazard zones; exposure score card (score / 100, rating, "why" breakdown).
2. **Your home**: the 8 checklist questions as illustrated cards (picture of open vs enclosed eaves, coarse vs fine vent mesh), "I don't know" always available; optional photo upload later.
3. **Your insurance**: drag-and-drop PDF; review screen showing each extracted value next to the highlighted line in the PDF (pdf.js), with ✅ / ⚠️; edit any value; or type by hand.
4. **Your plan**: before / after damage gauge, coverage gaps as cards by severity, ranked fixes with cost, payback and "why", budget slider updating the plan live.
5. **Report**: readable plan, download as PDF, "send to my broker".

Ideas that make it stand out: the quote-highlight review (shows the AI is checkable), the illustrated checklist (homeowners don't know what "1/8 inch mesh" means), and a shareable plan link.

### Order of work

1. Today: phase 1 online (Streamlit Cloud), backend and container ready (done in this branch).
2. Next: deploy the API (Cloud Run or Render), scaffold the Next.js app in `web/`, screens 1 and 4 first, then 3, then 2 and 5.
3. Before Nov 18: house model in, cost sources in, custom domain, analytics without personal data.

### Decisions for the team

1. Host for the API: Cloud Run (needs billing account) or Render (free, sleeps)?
2. Who owns the frontend, and is Next.js + Tailwind fine?
3. Public URL or password-protected for the Nov 18 presentation?
