# GitHub Models vision backend + POC demo — design

**Date:** 2026-07-23
**Status:** Approved (brainstorm), pending spec review
**Branch:** `feature/github-models-vision-demo`

## Context

ProofLens's production vision scoring has been down since 2026-07-20: Groq deleted
`meta-llama/llama-4-scout-17b-16e-instruct`, so every photo degrades to the `Unassessed`
band ("Vision check unavailable"). The pipeline fails open (never crashes) but no real
scoring happens.

We need vision back **now** for a proof-of-concept demo. The final production provider
will be a paid first-party API (decided later); for the demo we want a **free, real VLM
that is not China-hosted** (ABSLI customer photos → DPDP) and requires no card / no
real-name verification / no account balance.

Provider hunt (this session): ModelScope (Qwen-VL, free) blocked by Alibaba real-name
auth; Kimi/Moonshot key had no vision model and a suspended/zero-balance account.
**Selected: GitHub Models** — the owner already has a GitHub account, it is Azure/US-hosted,
and it exposes `openai/gpt-4o-mini`, a strong vision model with reliable JSON output.

**Validated live (2026-07-23):** the owner's fine-grained token called
`openai/gpt-4o-mini` on `https://models.github.ai/inference/chat/completions` and correctly
described a synthetic scene **and** read embedded text ("PROOF-42") — exactly ProofLens's
job. Both `models.github.ai` and the legacy Azure endpoint responded.

## Goals

1. Restore real vision scoring via a new, free `github` backend.
2. Deliver a **tightly-scripted, three-beat POC demo** (wow → dashboard → pipeline/fail-open)
   for a mixed audience (lead with the fraud-catch wow; keep technical proof underneath).
3. Prove it **locally first**, then provide exact steps to flip **production** (Render/Vercel).

## Non-goals

- No change to scoring math, fusion, hard gates, webhook, or the golden set (byte-unchanged).
- No real LeadSquared integration (still Phase 3 / FakeLSQ).
- No production purchase decision — GitHub Models is explicitly a demo/POC provider.

## Architecture

GitHub Models is OpenAI-compatible, so it reuses the existing `OpenAICompatBackend`
(`src/prooflens/vision/openai_compat.py`) with no new HTTP code — identical path to the
`gemini` / `groq` / `openrouter` backends.

### 1. Config (`src/prooflens/config.py`)

Add three fields (mirroring the existing provider blocks):

```
github_api_key:  str = Field(default="", alias="GITHUB_MODELS_TOKEN")
github_model:    str = Field(default="openai/gpt-4o-mini", alias="GITHUB_MODEL")
github_base_url: str = Field(default="https://models.github.ai/inference",
                             alias="GITHUB_BASE_URL")
```

Add a `"github"` entry to `build_vision_backend`'s `per_backend` map:
`{"api_key": self.github_api_key, "model": self.github_model, "base_url": self.github_base_url}`.

### 2. Backend registry (`src/prooflens/vision/__init__.py`)

Add `"github"` to the OpenAI-compat tuple (line ~40):
`if name in ("local_vlm", "gemini", "openrouter", "aimlapi", "groq", "cloudflare", "github"):`
— routes to `OpenAICompatBackend`. No new class.

### 3. Landmine fix (same file, `config.py:105`)

Change the dead `groq_model` default off the deleted Scout model to `qwen/qwen3.6-27b`
— per our own vision-outage notes the only currently-valid Groq vision model — so a bare
`VISION_BACKEND=groq` no longer 404s. Groq is **not** the demo path (we use `github`), so
this is purely defensive against a known trap; the exact Groq model id will be re-verified
against Groq's live `/models` list during implementation before committing.

### Data flow (unchanged downstream)

`photo bytes → resize_for_model → base64 data URI → POST /chat/completions
(SYSTEM_PROMPT + USER_PROMPT + image_url) → parse_model_json → ContentAssessment
(backend="github", model="openai/gpt-4o-mini") → existing fusion → verdict`.

Fail-open is inherited unchanged: a `VisionUnavailable` (bad key, rate limit, bad shape)
propagates to the existing `Unassessed` path.

## Demo (three beats, tightly scripted)

### Beat 1 — the wow (fraud catch)
Curated sample set, sourced by us (no real-customer data):
- **Genuine:** stock field/meeting/site photos → expected high score + sensible reason.
- **Fraudulent:** AI-generated "meeting" image, stock studio photo, screenshot-of-a-screen,
  printed-photo-of-a-photo → expected low score, honest reason.
Run genuine vs fraudulent side-by-side through the real `github` backend.
*(Owner may optionally add 1–2 real-ish non-customer field photos for authenticity.)*

### Beat 2 — the dashboard/story
Reuse the seed script for realistic data; **enrich `processing_ms`** so the system-health
median is not 0 ms on the demo. The v4 "four-question" analytics page + DSE scorecards
must look full and alive.

### Beat 3 — pipeline + fail-open
Show the full flow (photo → hard gates → vision → verdict), then demonstrate fail-open by
removing the token → honest `Unassessed`, never a crash — the "real production system"
credibility beat for technical viewers.

## Deliverables

1. `github` vision backend (code + tests) and the `GROQ_MODEL` default fix.
2. Working **local** stack (docker Postgres + uvicorn + `next dev`), screenshotted.
3. Curated demo photo set (committed under a demo assets dir, non-sensitive).
4. **`DEMO_SCRIPT.md`** — 3–4 min walkthrough, exact photos + clicks, beat order
   wow → dashboard → pipeline/fail-open.
5. **Prod flip runbook** — exact Render env (`VISION_BACKEND=github`, `GITHUB_MODELS_TOKEN`)
   + Vercel note; NVIDIA fallback documented as one-env-var swap.

## Testing

- Unit: a `github` backend test mirroring the existing gemini/groq OpenAI-compat tests
  (mock `post_chat`, assert `ContentAssessment` shape, `backend="github"`).
- Config: `build_vision_backend("github")` returns an `OpenAICompatBackend` with the right
  base URL / model.
- Fail-open: missing token raises (ValueError from `OpenAICompatBackend.__init__`), and a
  `VisionUnavailable` routes to `Unassessed` (existing behaviour, re-asserted).
- Live smoke (opt-in, env-guarded, like the hybrid smoke test): real token → real photo →
  `backend="github"`, `model="openai/gpt-4o-mini"`, sensible verdict.
- Regression: full backend suite + ruff + mypy green; golden set unchanged.

## Security

- The GitHub token is **transcript-exposed** → owner rotates after the demo.
- Token lives only in `.env.local` (local) / Render env (prod); **never committed**.
  Confirm `.env.local` is gitignored before any commit.

## Rollout

1. Local: set `GITHUB_MODELS_TOKEN` + `VISION_BACKEND=github` in `.env.local`; run stack;
   verify genuine vs fraudulent photos; capture screenshots.
2. Prod (owner-driven, no Render access on our side): set `VISION_BACKEND=github` +
   `GITHUB_MODELS_TOKEN` on Render; redeploy; score one real photo; confirm
   `model="openai/gpt-4o-mini"`. Instant rollback: unset / `VISION_BACKEND=stub`.

## Risks

- **Free rate limits** (GitHub Models free tier is modest). Mitigation: demo uses few
  photos; use `gpt-4o-mini` (lower tier = more generous) not `gpt-4o`; NVIDIA fallback wired.
- **Compliance:** GitHub Models is a demo provider only; production uses a paid first-party
  API per the separate provider decision.
