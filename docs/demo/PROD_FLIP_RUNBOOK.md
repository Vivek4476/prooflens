# Production flip — switch prod vision to GitHub Models

Restores real vision scoring on prod (down since Groq deleted the Scout model, 2026-07-20).
**You run these** — I have no Render access. ~5 minutes. Instant rollback included.

## Preconditions
- Branch `feature/github-models-vision-demo` merged to `main` (Render auto-deploys `main`).
- A GitHub fine-grained token with **Models: read** (format `github_pat_…`).
  ⚠️ The token used in the demo is exposed in chat — **mint a fresh one for prod** and
  revoke the demo token afterward.

## Steps

1. **Render → prooflens-api → Environment.** Add / set:

   | Key | Value |
   |---|---|
   | `VISION_BACKEND` | `github` |
   | `GITHUB_MODELS_TOKEN` | `github_pat_…` (fresh prod token) |
   | `GITHUB_MODEL` | `openai/gpt-4o-mini` *(optional; this is the default)* |

2. **Save** → Render redeploys automatically. Wait for "Live".

3. **Verify** — score one real photo through the deployed API (needs the tenant API key):

   ```bash
   curl -s -X POST https://prooflens-api.onrender.com/v1/score \
     -H "X-API-Key: <prod tenant key>" \
     -F "file=@some-real-photo.jpg" | jq '{band,score,reason,model:.checks[]?|select(.name=="content")?.data.model}'
   ```
   Expect a real `band`/`score`/`reason` and `model="openai/gpt-4o-mini"` — **not**
   "Vision check unavailable".

4. **Frontend** (Vercel `prooflens-theta`) needs no change — it reads the API.

## Rollback (instant)
Set `VISION_BACKEND=stub` (safe fake) or unset `GITHUB_MODELS_TOKEN` → redeploy. Scoring
degrades honestly to `Unassessed`; nothing crashes, nothing blocks.

## Fallback provider (if GitHub free limits bite in prod)
Everything rides the same OpenAI-compatible backend, so switching is one env var:

| Provider | Env |
|---|---|
| **NVIDIA** (90B vision, free credits, already wired) | `VISION_BACKEND=nvidia`, `NVIDIA_API_KEY=nvapi-…` |
| **Anthropic** (paid, production-grade) | `VISION_BACKEND=anthropic`, `ANTHROPIC_API_KEY=…` |
| **Gemini** (paid/free, if you get a Google key later) | `VISION_BACKEND=gemini`, `GEMINI_API_KEY=…` |

## Notes
- GitHub Models is a **POC/demo provider** (Azure/US-hosted). For sustained ABSLI
  production traffic (customer photos → DPDP), move to a paid first-party model — that
  decision is separate from this flip.
- `GROQ_MODEL` default was also fixed off the deleted Scout model, so a bare
  `VISION_BACKEND=groq` no longer 404s (defensive; not the chosen path).
