# ProofLens Frontend

Enterprise SaaS UI for ProofLens — Next.js 15 (App Router) · TypeScript (strict)
· Tailwind · TanStack Query · Recharts · Framer Motion. It **consumes the
backend's existing APIs** and never mocks responses; the exact contract (and the
endpoints still required) live in [BACKEND_REQUIREMENTS.md](./BACKEND_REQUIREMENTS.md).

## Run (dev)

```bash
# 1. Backend up (from repo root) — provides the API on :8000
docker compose -f deploy/docker-compose.yml up --build   # includes this UI on :3000
# ...or run the API alone and the UI in dev:

cd frontend
cp .env.local.example .env.local          # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                               # http://localhost:3000
```

## Populate demo data (real verdicts)

```bash
python scripts/generate_demo_images.py     # repo root — writes ../demo_images
cd frontend && npm run seed:demo           # pushes them through the REAL /v1/score
```

## Scripts

- `npm run dev` / `build` / `start` — Next.js
- `npm run typecheck` — `tsc --noEmit` (strict)
- `npm run gen:api` — regenerate `src/lib/api/schema.ts` from the live `/openapi.json`
- `npm run seed:demo` — seed the demo through the real scoring API

## Design system

Brand tokens are the single source of truth in
[`src/styles/tokens.css`](./src/styles/tokens.css): ABC crimson is
masthead/primary-only (accent ≤10%), the gold rule sits under the logo, and
verdict green/amber/red are reserved for Clear/Doubtful/Suspect and always paired
with the word. Both light and dark are first-class. See the repo's
`docs/DESIGN_PRINCIPLES.md`.

**Brand asset:** drop the logo at `public/brand/abc-life-insurance.png`. If
absent, the masthead renders a labelled placeholder of a similar aspect ratio.

## Pages

Dashboard (health + risk KPIs + recent verdicts) · Analyze Photo (upload →
pipeline stepper → verdict → explainability) · Upload History (searchable table,
metadata-only) · Review Queue (moderation console; decision endpoint pending) ·
Analytics (band mix + top reasons) · Settings (tenant, scoring policy, health).
