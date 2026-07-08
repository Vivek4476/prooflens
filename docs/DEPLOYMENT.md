# Deploying ProofLens

Two pieces deploy from this Git repo:

- **Backend** (FastAPI API + Postgres) → **Render** (uses `render.yaml` + `deploy/Dockerfile`)
- **Frontend** (Next.js UI) → **Vercel** (uses `frontend/`)

Both have generous free tiers. Deploy the **backend first** (the frontend needs
its URL). Secrets are **not** in the repo — you set them in each dashboard.

---

## 1. Backend on Render

1. Push your repo to GitHub (already done: `github.com/Vivek4476/prooflens`).
2. In [Render](https://render.com): **New → Blueprint** → connect the repo →
   Render reads `render.yaml` and proposes a **Postgres database** + a
   **`prooflens-api` web service**. Apply.
3. Render builds `deploy/Dockerfile`, runs `alembic upgrade head`, seeds a dev
   tenant, and starts the API. When it's live you get a URL like
   `https://prooflens-api.onrender.com`.
4. Verify: open `https://<your-api>.onrender.com/healthz` → `{"status":"ok"}`
   and `/docs` for the API explorer.

**Env vars** (Render sets most automatically):

| Var | Value |
|---|---|
| `DATABASE_URL` | auto-wired from the Render Postgres |
| `PROOFLENS_SECRET_KEY` | auto-generated |
| `PROOFLENS_ADMIN_TOKEN` | auto-generated — **copy it**, the frontend needs it |
| `VISION_BACKEND` | `groq` (default; requires `GROQ_API_KEY`). If no key is set, scoring caps to `Doubtful` (never a fake `Clear`). For development/CI without a key, use `stub` — a test-only fixture, never production. |
| `GROQ_API_KEY` | **required for production** — the default backend cannot work without it. |
| `CORS_ORIGINS` | **set after step 2** to your Vercel URL (below) |

> The **async worker** is not in the free blueprint (Render workers need a paid
> plan). It is only used for the async LSQ webhook path — the UI and `/v1/score`
> work without it. To add it: New → Background Worker, same repo/Dockerfile,
> command `python -m prooflens.worker`, same `DATABASE_URL`/`PROOFLENS_SECRET_KEY`.

## 2. Frontend on Vercel

1. In [Vercel](https://vercel.com): **Add New → Project** → import the repo.
2. **Set Root Directory to `frontend`** (important — the app lives in a
   subfolder). Framework auto-detects as Next.js.
3. Add **Environment Variables**:
   - `NEXT_PUBLIC_API_URL` = your Render API URL (e.g. `https://prooflens-api.onrender.com`).
     Already pinned in `frontend/.env.production`; only set this in the dashboard
     to point at a *different* API. A dashboard value overrides the file — if the
     Analyze page can't reach the backend, make sure any dashboard override is
     correct (or remove it) and redeploy, since `NEXT_PUBLIC_*` is inlined at build time.
   - `NEXT_PUBLIC_ADMIN_TOKEN` = the `PROOFLENS_ADMIN_TOKEN` from Render (for the Settings page)
4. Deploy. You get a URL like `https://prooflens.vercel.app`.

## 3. Wire the two together (CORS)

Back in Render → `prooflens-api` → Environment → set:

```
CORS_ORIGINS = https://prooflens.vercel.app
```

Save (the API restarts). Without this, the browser blocks the frontend's API
calls. Open your Vercel URL — the health dot should go green and the pages load.

## 4. Seed demo data (optional)

From your machine, pointed at the deployed API:

```bash
python scripts/generate_demo_images.py
cd frontend
NEXT_PUBLIC_API_URL=https://prooflens-api.onrender.com npm run seed:demo
```

This pushes the sample images through the **real** deployed `/v1/score`, so
History / Analytics / Review populate with genuine verdicts.

---

## Gotchas & notes

- **Free tiers sleep.** Render free web services + Postgres spin down when idle
  (first request after a nap is slow), and free Postgres expires after ~90 days.
  Fine for a demo; upgrade for anything persistent.
- **Secrets never go in Git.** Your API keys live only in the local `.env`
  (gitignored). Re-enter them as env vars in Render/Vercel.
- **`DATABASE_URL` form** is handled automatically — the app normalises
  `postgres://` / `postgresql://` to the `postgresql+psycopg://` driver.
- **Real vision model**: `openrouter` free models rate-limit and can be slow;
  scoring is fail-open, so a slow/failed model degrades to "scored without
  content analysis" rather than erroring. The Analyze page also has a per-request
  Demo / Live-AI switch.

## Alternatives

- **Railway** works the same way (deploy `deploy/Dockerfile` + a Postgres
  plugin; set the same env vars). It supports the worker on its free/hobby tier.
- **Fly.io** if you want the worker + API + Postgres all in one place via
  `fly launch` against `deploy/Dockerfile`.
