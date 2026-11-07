# AlwaysHome web (Next.js)

The homeowner-facing app. It calls the Python API (`../api/main.py`) through `/api/*`, which Next.js forwards to `API_URL` (see `next.config.ts`).

## Run locally

Two terminals, from the repo root:

```
uv run uvicorn api.main:app --port 8000      # API (uses ANTHROPIC_API_KEY if set)
cd web && npm install && npm run dev          # app at http://localhost:3000
```

Demo shortcut: http://localhost:3000/?demo=altadena_fair_only&step=4 fills a sample homeowner and opens the situation step
(other ids: altadena_fair_dic, palisades_underinsured, wilshire_fully_hardened, all_unknown_no_budget, all_unknown_big_budget; step 1-5: 4 = your situation, 5 = your plan).

## Deploy (Vercel)

1. Deploy the API first (Render Blueprint `render.yaml`, or Cloud Run; see `docs/DEPLOYMENT.md`) and copy its URL.
2. vercel.com > Add New Project > import the GitHub repo > **Root Directory: `web`**.
3. Environment variables (both = the API URL, e.g. `https://alwayson-api.onrender.com`, no trailing slash):
   - `API_URL`: used by the `/api/*` forwarding.
   - `NEXT_PUBLIC_DIRECT_API_URL`: the slow AI calls (policy reading, AI report) go straight to the API so a proxy timeout can't cut them off.
4. Deploy.

Checks before pushing: `npm run lint && npm run build`.
