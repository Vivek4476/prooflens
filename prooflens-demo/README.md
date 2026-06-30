# ProofLens — runnable demo

A small, **real** web demo of ProofLens: upload a photo, click **Run**, and get a
0–100 trust score, a band (**Clear / Doubtful / Suspect**), and a per-check
breakdown with reasons.

Unlike the artifact explainer, this actually runs the checks. The deterministic
checks (sharpness, uniqueness, person, EXIF) run for real on the server, and the
content/relevance check is a **real vision-model call made server-side** through a
pluggable backend — so the API key never touches the browser.

> This is a standalone demo, not the full LSQ production service. The
> lead/rep/time "trail" stored alongside hashes is **fabricated locally** for the
> demo (see `store.py`). The image itself is never stored.

---

## What it does

```
photo ──▶ [sharpness] [uniqueness] [person] [metadata]   (deterministic, free)
      └─▶ [content / relevance]                           (the star — vision model)
                         │
                         ▼
            weighted blend + hard gates ──▶ score 0–100 ──▶ band
```

**The checks**

| Check               | How                                            | Real? |
|---------------------|------------------------------------------------|-------|
| `sharpness`         | OpenCV Laplacian variance                      | ✅ |
| `uniqueness`        | imagehash dHash vs local SQLite (Hamming dist) | ✅ |
| `person_presence`   | OpenCV HOG + Haar detection (no identity)      | ✅ |
| `metadata`          | EXIF presence via Pillow (backstop)            | ✅ |
| `content_relevance` | **vision model** via pluggable backend         | ✅ (or stub) |

**Fusion** — weighted blend of the soft scores, then hard gates that cap the
final score: exact-duplicate, photo-of-a-screen, designed-graphic/meme,
`meeting_plausibility < 30`, fully-blurred. **Bands:** Suspect < 40,
Doubtful 40–70, Clear ≥ 70. All weights/thresholds live in `config.py` and are
overridable via env (see `.env.example`).

---

## Setup

Requires Python 3.10+.

```bash
cd prooflens-demo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The vision SDKs (`anthropic`, `google-genai`, `openai`) are listed too, but you
only need the one for the backend you pick. The app runs with **no keys** on the
default `stub` backend.

## Run

```bash
uvicorn app:app --reload
# open http://localhost:8000
```

Drop in a photo, hit **Run**. The backend badge (top-right) shows which vision
backend is active; when it's `stub`, the content check is labelled *stubbed* so
the UI stays honest.

## Switching the vision backend

Set `VISION_BACKEND` (env or `.env`, copied from `.env.example`):

| `VISION_BACKEND` | Model                     | Key needed |
|------------------|---------------------------|------------|
| `stub` (default) | deterministic fake        | none |
| `anthropic`      | Claude Haiku 4.5          | `ANTHROPIC_API_KEY` |
| `gemini`         | Gemini Flash              | `GEMINI_API_KEY` |
| `openai`         | GPT-4o mini               | `OPENAI_API_KEY` |
| `local`          | Qwen2-VL / Moondream      | `LOCAL_BASE_URL`, `LOCAL_MODEL` (Ollama/vLLM) |

```bash
export VISION_BACKEND=anthropic
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn app:app --reload
```

Images are resized to a ~768px long edge before the model call (cuts
tokens/latency), and **every backend answers the same rubric/prompt** so results
are comparable. Keys come from env vars only and are never sent to the browser.

## Bake-off — pick the cheapest good model

Compare every configured backend over a labelled folder:

```bash
python compare.py samples
```

It prints, per backend: **accuracy** (vs the folder labels), **false-positive
rate**, **avg latency**, and **approx cost/photo**. Backends whose key isn't set
are skipped, not failed.

Labels come from `samples/labels.csv` (`filename,label` where label is `good` or
`bad`). Drop your own images into a folder with a matching `labels.csv` to run
your own bake-off. Costs are rough public list prices in `config.py` /
`.env.example` — adjust as pricing changes.

## Tests

```bash
pytest
```

Covers the deterministic checks and fusion/gates. The vision call is mocked, so
tests need no keys or network.

---

## Project layout

```
prooflens-demo/
  app.py                # FastAPI: serves index.html + POST /score
  config.py             # weights, thresholds, bands, models (env-overridable)
  fusion.py             # weighted blend + hard gates + banding
  store.py              # SQLite hash store (hashes + fake trail; never images)
  compare.py            # the bake-off CLI
  checks/               # sharpness, uniqueness, person, metadata, relevance
  vision/               # VisionBackend + anthropic/gemini/openai/local/stub
  static/index.html     # the demo UI (ABSLI styled)
  samples/              # a few generated images + labels.csv
  tests/                # pytest: deterministic checks + fusion (vision mocked)
  requirements.txt  .env.example
```

## Honest limits / TODO

- The lead/rep/time **trail is fabricated** for the demo. _TODO: wire to the real
  upload context in the LSQ service._
- ProofLens **scores and flags — it never blocks an upload**. It raises the cost
  of faking and catches the lazy majority; it cannot prove a meeting happened.
- No facial recognition, no gesture analysis, no identity storage. The person
  check is **detection only**. Images are never persisted.
