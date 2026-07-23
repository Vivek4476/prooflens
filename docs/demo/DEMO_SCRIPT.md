# ProofLens — POC Demo Script

**~4 minutes. Three beats: Wow → Dashboard → Pipeline/Fail-open.**
Vision provider for this demo: **GitHub Models · `openai/gpt-4o-mini`** (free, US-hosted).
Mixed audience → lead with the fraud-catch wow; the technical proof sits underneath.

---

## 0. One-time setup (before the room)

```bash
cd ~/Desktop/prooflens
source .venv/bin/activate

# .env.local (gitignored) already holds:
#   VISION_BACKEND=github
#   GITHUB_MODELS_TOKEN=github_pat_…
#   GITHUB_MODEL=openai/gpt-4o-mini

# Drop 2–3 REAL non-customer photos into docs/demo/assets/ :
#   genuine_meeting.jpg, genuine_field.jpg   (see assets/README.md)
```

**Bring up the full local stack** (three terminals):

```bash
# 1) Postgres
docker compose -f deploy/docker-compose.yml up -d

# 2) API (seeds handled below). PYTHONPATH=src is required.
PYTHONPATH=src VISION_BACKEND=github \
  GITHUB_MODELS_TOKEN=$(grep GITHUB_MODELS_TOKEN .env.local | cut -d= -f2) \
  uvicorn prooflens.api.app:app --reload --port 8000

# 3) Frontend
cd frontend && npm run dev     # http://localhost:3000
```

**Seed realistic dashboard data** (once the DB is up):

```bash
export DATABASE_URL=postgresql+psycopg://prooflens:prooflens@localhost:5432/prooflens
PYTHONPATH=src python scripts/seed_dev_tenant.py           # creates the dev tenant
PYTHONPATH=src python scripts/seed-realistic.py --days 75  # thousands of rows, realistic
```

The seed now populates realistic per-check latencies, so **system-health median processing
time shows a real number (~0.4–1s), not 0 ms.**

---

## Beat 1 — The Wow: it catches fakes, trusts the real thing (~90s)

> "Field staff submit a photo as proof they met a customer. The question is simple and
> expensive: *is this a real photo of a real visit — or a fake?*"

Run the live scorer on your photo set:

```bash
GITHUB_MODELS_TOKEN=$(grep GITHUB_MODELS_TOKEN .env.local | cut -d= -f2) \
  PYTHONPATH=src python docs/demo/score_photo.py docs/demo/assets/*.jpg
```

**What the room sees (verified live 2026-07-23):**

```
🚫 fraud_screen.jpg
    score=20.0   band=Suspect   reason=Photo of another screen — screen edge and glare detected.
🚫 fraud_screenshot.jpg
    score=20.0   band=Suspect   reason=Photo of another screen — screen edge and glare detected.
    vision saw: The image appears to be a screenshot of a user interface with empty fields and buttons.
✅ genuine_meeting.jpg      ← your real photo
    score=~90    band=Clear     reason=Looks like a genuine in-person meeting.
    vision saw: Two people seated at a desk in an office, appearing to talk…
```

> "No one told it what a screen looks like. The model *describes what it sees* and the
> engine turns that into a score and a plain-English reason. Real meeting → trusted.
> Screenshot, photo-of-a-screen, AI image → caught."

**Talking point:** every verdict carries a reason from a fixed vocabulary — defensible,
auditable, never a black-box number.

---

## Beat 2 — The Dashboard: the whole channel at a glance (~60s)

Open **http://localhost:3000**.

> "That's one photo. Here's the whole field force."

Walk the **four-question analytics page** top-to-bottom:
1. **How healthy is submission quality?** — band mix (Clear / Doubtful / Suspect / Unassessed).
2. **Is it getting better or worse?** — trend over time + period deltas.
3. **Why are photos failing?** — top reasons (short labels).
4. **Who needs attention?** — DSE scorecards / by-team.

Point at **system health**: "median processing ~0.6s, X% scored with vision" — *(now a real
number thanks to the seed enrichment)*.

> "Fail-open by design: ProofLens **scores and flags — it never blocks** a submission."

---

## Beat 3 — Pipeline + Fail-open: it's a real production system (~50s)

> "For the technical folks — two things that make this safe to run."

**(a) Cheap-gates-first.** Show `src/prooflens/engine/pipeline.py`:

> "Free hard checks run first — EXIF, blur, duplicate-hash, screen-recapture. If one
> already rejects the image, we **skip the paid vision call entirely.** We don't spend a
> model call on an image we've already caught."

**(b) Fail-open, never a crash.** Kill the key and re-score:

```bash
GITHUB_MODELS_TOKEN=bad-token \
  PYTHONPATH=src python docs/demo/score_photo.py docs/demo/assets/genuine_meeting.jpg
```

> "Vision unavailable → the photo lands in a distinct **Unassessed** band and routes to
> review. It never blocks the rep, and it never silently passes a fake as Clear."

---

## Close (~20s)

> "Today this runs on a **free** vision model for the POC. For production we swap in a paid
> first-party model — **one environment variable**, zero code change — because every
> provider rides the same OpenAI-compatible backend."

---

## Appendix — quick recovery

| Symptom | Fix |
|---|---|
| Vision returns `Unassessed` for everything | token expired/rate-limited → check `GITHUB_MODELS_TOKEN`; GitHub free tier is modest, wait a minute or re-mint |
| Dashboard empty | seed didn't run → re-run the two seed commands; confirm `DATABASE_URL` |
| median processing = 0 ms | you seeded before this change → `python scripts/seed-realistic.py --wipe-existing-seed --days 75` |
| Want a stronger model | set `GITHUB_MODEL=openai/gpt-4o` (stricter free limits) |
| GitHub blocked entirely | fall back to NVIDIA: `VISION_BACKEND=nvidia`, `NVIDIA_API_KEY=nvapi-…` (already wired) |
