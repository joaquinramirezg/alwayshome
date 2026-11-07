# web/ (phase 2 frontend, not started)

Next.js + TypeScript on Vercel, calling the API in `api/main.py`. Plan, screens and stack: `docs/DEPLOYMENT.md` → "Frontend".

To start it:
```
npx create-next-app@latest web --ts --tailwind --app --eslint --src-dir --use-npm
```
Then set `NEXT_PUBLIC_API_URL=http://localhost:8000` and run the API with `uv run uvicorn api.main:app --reload --port 8000`.
