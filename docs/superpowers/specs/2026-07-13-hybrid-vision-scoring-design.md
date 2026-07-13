# Hybrid two-model vision scoring — design

**Date:** 2026-07-13
**Status:** approved (brainstorm), pending implementation plan
**Scope:** add a two-stage "perception → reasoning" vision backend and make it the default.

## Problem

ProofLens scores proof-of-visit photos with a single multimodal call (Groq
`llama-4-scout-17b-16e-instruct`). Two limitations:

1. **Rate limits** — Groq's free vision tier 429s under load; the pipeline then
   fails open to Unassessed/Doubtful, so real photos go un-scored during bursts.
2. **Judgment ceiling** — one 17B model does both the *perceiving* (what's in the
   image) and the *judging* (is this a plausible field visit?). A larger,
   stronger reasoner applied to the perception can sharpen the judgment fields.

## Goal

Introduce a **hybrid vision backend** that splits the work across two Cloudflare
Workers AI models and make it the **default** vision path, while keeping every
existing backend selectable for instant revert:

- **Stage 1 — perception:** `@cf/meta/llama-4-scout-17b-16e-instruct` (Scout),
  the *same model class* already validated for ProofLens, run with the existing
  **v3 rubric unchanged**, producing a full `ContentAssessment`.
- **Stage 2 — reasoning:** `@cf/openai/gpt-oss-120b` (text-only), which reasons
  over Scout's structured perception and returns a **refined judgment**
  (`plausibility`, `visit_context`, `context_confidence`, `reason`).

Both run on Cloudflare via one account token, dodging Groq's rate limits.

### Non-goals

- No change to fusion, scoring config, verdict bands, analytics, DB schema, or
  the webhook contract. The hybrid returns the same `ContentAssessment` shape.
- No frontier/closed models (Claude/GPT/Gemini) — Cloudflare-hosted open models
  only, per the "best available for free-ish on Cloudflare" constraint.
- No change to the v3 rubric or the perceptual fields.

## Architecture

A new `HybridBackend` (`src/prooflens/vision/hybrid.py`) that **composes the
existing `OpenAICompatBackend` (Stage 1) with a new text-only `Reasoner` (Stage
2)**, both pointed at Cloudflare's OpenAI-compatible endpoint. It implements the
existing `VisionBackend` Protocol (`assess(image_bytes) -> ContentAssessment`),
so nothing downstream changes.

```
HybridBackend.assess(image_bytes)
  ├─ scout:    OpenAICompatBackend(model=CF_VISION_MODEL, base_url=CF)   # Stage 1 (image)
  └─ reasoner: Reasoner(model=CF_REASONER_MODEL, base_url=CF)            # Stage 2 (text-only)
```

**Why Stage 2 is not another `OpenAICompatBackend`:** that class's `assess()`
*always* builds an `image_url` from `image_bytes` and returns a full
`ContentAssessment`. The reasoner sends **no image** (only Scout's perception as
text) and returns **only the judgment fields**. So Stage 2 is a new, small
`Reasoner` class (`src/prooflens/vision/reasoner.py`) that makes a text-only
`/chat/completions` call. The raw HTTP-POST + error-to-`VisionUnavailable`
handling currently inside `OpenAICompatBackend` is factored into a shared helper
(e.g. `vision/_http.py`) that both Stage 1 and the `Reasoner` reuse, so error
semantics (HTTP status, timeout, bot-UA header) stay identical across stages.

**Rejected alternatives:**
- *Extend `OpenAICompatBackend` with a second pass* — bloats the single-call
  backend with orchestration; violates single responsibility.
- *Reason inside `fuse.py`* — fusion must stay pure, deterministic math over a
  finished `ContentAssessment`; a network call there breaks that boundary.

Composition matches the codebase's existing Protocol/pluggable-backend pattern.

## Data flow

```
image bytes
   │
   ├─▶ Stage 1: Scout — existing v3 rubric → FULL ContentAssessment
   │            (perceptual fields + Scout's own judgment fields)
   │
   └─▶ Stage 2: gpt-oss-120b [text-only, NO image]
   │            input  = Scout's perceptual fields rendered as JSON
   │            prompt = new judgment-only prompt
   │            output = {plausibility, visit_context, context_confidence, reason}
   ▼
Merge → ContentAssessment:
   • perceptual fields (people_count, people_interacting, setting, environment,
     primary_subject, scene_description, emotional_tone, looks_like_photo_of_a_screen,
     is_designed_graphic, is_meme_or_screenshot)  ← Scout
   • judgment fields (plausibility, visit_context, context_confidence, reason)
     ← reasoner on success, else Scout's own (fallback)
   • backend = "hybrid",  model = "scout+gpt-oss-120b"
```

The reasoner **never receives the image** — it applies stronger reasoning to the
same evidence Scout perceived. Both stages run at **temperature 0** (existing
reproducibility rule: the same photo must yield the same verdict).

## Fail-open behavior (the hard rule: never mislabel an outage as fraud)

| Scenario | Behavior |
|---|---|
| Both stages succeed | Perception = Scout; judgment = reasoner. Full hybrid. `degraded=false`. |
| **Stage 2 fails / 429 / malformed JSON** | Keep Scout's own judgment from Stage 1. Valid verdict. Logged `degraded="scout-only"`. Never worse than single-Scout. |
| **Stage 1 fails / 429** | Raise `VisionUnavailable` → existing fail-open path → **Unassessed** band, routed to review. Identical to today. |

Rationale: a reasoner hiccup must not throw away a good perception (that would be
*worse* than single-Scout), and a perception outage must not manufacture a
verdict. Both directions are covered.

## Configuration

New settings in `config.py` (env-driven, per-backend dict entry):

| Env var | Default | Purpose |
|---|---|---|
| `CF_ACCOUNT_ID` | — | Cloudflare account id (`61e47fc3…c3d1f4`) |
| `CF_API_TOKEN` | — | Workers AI token (scope: Workers AI · Read) |
| `CF_VISION_MODEL` | `@cf/meta/llama-4-scout-17b-16e-instruct` | Stage 1 |
| `CF_REASONER_MODEL` | `@cf/openai/gpt-oss-120b` | Stage 2 |
| `VISION_BACKEND` | **`hybrid`** (was `groq`) | default flips to hybrid |

Cloudflare base URL is derived:
`https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/v1`
(OpenAI-compatible — reuses `OpenAICompatBackend` verbatim).

`build_vision_backend` gains two entries:
- `"hybrid"` → constructs the `HybridBackend`.
- `"cloudflare"` → a plain single-call Scout-on-Cloudflare backend (near-free to
  add; useful as a lighter option and for isolating Stage 1 in tests/ops).

## Reasoner prompt

A new **judgment-only** prompt, versioned alongside the rubric as
`rubrics/reasoner_v1.yaml` (mirrors the existing "prompt IS policy" pattern;
loaded the same way as the rubric, and its version is recorded for provenance).
It:

- States the ProofLens task (judging a field-agent proof-of-visit photo).
- Receives Scout's perceptual fields as JSON (no raw image).
- Returns **only** `{plausibility (0–100), visit_context (0–100),
  context_confidence (high|moderate|low), reason (short string)}` as JSON.
- Is parsed with the existing `parse_model_json` and validated by a small
  pydantic model; malformed output triggers the Stage-2 fallback (use Scout's
  judgment), never a crash.

## Telemetry & provenance

- Log both provider request-ids (Scout + reasoner) and a `degraded` flag per
  assessment.
- `ContentAssessment.model = "scout+gpt-oss-120b"` so the UI/history honestly
  shows the pipeline that produced the verdict.
- `backend = "hybrid"`.

## Cost / rate-limit note

Two calls per image ≈ 2× Neurons vs single-call. Accepted: user opted for "best
available, limited free use is fine." Cloudflare free allocation (~10k
Neurons/day) suits dev + low production volume; sustained high volume crosses
into (cheap) paid. This is a knowingly-accepted tradeoff, not a silent one.

## Testing

- **Unit (offline, mocked sub-backends — no network):**
  - happy path: perception from Scout + judgment from reasoner merged correctly.
  - Stage-2 raises → judgment falls back to Scout's; `degraded="scout-only"`.
  - Stage-2 returns malformed JSON → same fallback.
  - Stage-1 raises → `VisionUnavailable` propagates (existing fail-open).
  - merge precedence: reasoner judgment overrides Scout's when present.
- **Live smoke (opt-in, env-guarded):** one real end-to-end call against
  Cloudflare, skipped by default so CI stays deterministic/offline.
- Existing backend tests, fusion tests, and golden set stay green (unchanged
  contract).

## Rollout

1. Land behind config with `VISION_BACKEND=hybrid` as default in code.
2. Set `CF_ACCOUNT_ID` / `CF_API_TOKEN` on Render (server env). Until set, the
   hybrid raises a clear "missing Cloudflare credentials" error at construction;
   operators can pin `VISION_BACKEND=groq` to revert instantly.
3. Verify live on a sample; watch `degraded` rate and latency.
