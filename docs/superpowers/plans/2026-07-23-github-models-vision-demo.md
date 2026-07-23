# GitHub Models Vision Backend + POC Demo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use `- [ ]` tracking.

**Goal:** Restore real vision scoring via a free, US-hosted `github` backend
(`openai/gpt-4o-mini`) and deliver a tightly-scripted three-beat POC demo.

**Architecture:** GitHub Models is OpenAI-compatible → reuse `OpenAICompatBackend`. Add a
`github` backend name in config + registry; no new HTTP class. Additive only.

**Tech Stack:** Python 3.14, FastAPI, pydantic-settings, pytest/ruff/mypy; Next.js frontend.

## Global Constraints
- Additive only: scoring/fusion/hard-gates/webhook/golden set **byte-unchanged**.
- Token never committed; `.env.local` (already gitignored) locally, Render env for prod.
- `openai/gpt-4o-mini`, endpoint `https://models.github.ai/inference`.
- TDD, deterministic temperature 0.0 (inherited from `OpenAICompatBackend`).

---

### Task 1: `github` vision backend (config + registry + tests)
**Files:** Modify `src/prooflens/config.py`, `src/prooflens/vision/__init__.py`;
Test `tests/unit/test_github_wiring.py`, extend `tests/unit/test_vision_backend.py`.
- [ ] Failing test: `get_backend("github", ...)` returns `OpenAICompatBackend` named `github`;
      `Settings().build_vision_backend("github")` wires base_url/model/key from env.
- [ ] Add `github_api_key/github_model/github_base_url` fields + `"github"` in `per_backend`.
- [ ] Add `"github"` to the OpenAI-compat tuple in `get_backend`.
- [ ] Tests pass; commit.

### Task 2: Fix dead `GROQ_MODEL` default
**Files:** Modify `src/prooflens/config.py:105`.
- [ ] Verify Groq's live `/models` for a valid vision id; set default to a current one
      (`qwen/qwen3.6-27b` fallback per notes). Defensive only — not the demo path.
- [ ] Commit.

### Task 3: Opt-in live smoke test
**Files:** Create `tests/live/test_github_live.py` (mirrors `test_hybrid_live.py`).
- [ ] Skip unless `RUN_LIVE_VISION=1` + `GITHUB_MODELS_TOKEN`. Assert `backend=="github"`,
      valid plausibility, populated `scene_description`.
- [ ] Run it live with the real token; commit.

### Task 4: End-to-end integration proof (genuine vs fraud)
**Files:** demo images under `docs/demo/assets/`; `.env.local` (uncommitted).
- [ ] Generate/collect a genuine-style and a clearly-synthetic image; run the real
      `github` backend `.assess()` on each; confirm the pipeline discriminates.
- [ ] Record outputs for the demo script.

### Task 5: Seed `processing_ms` enrichment for the dashboard
**Files:** `scripts/seed-realistic.py` (or `scripts/lib/seed_data.py`).
- [ ] Populate realistic `processing_ms` so system-health median isn't 0 ms.

### Task 6: `DEMO_SCRIPT.md` + prod-flip runbook
**Files:** `docs/demo/DEMO_SCRIPT.md`.
- [ ] 3–4 min walkthrough: wow → dashboard → pipeline/fail-open, exact photos + clicks +
      the local run commands; Render/Vercel prod env steps + NVIDIA fallback.

### Task 7: Regression gate
- [ ] Full backend suite + ruff + mypy green; final commit.
