# Verdict Copy Specification

This document is **policy**. The fusion layer may surface **only** the strings
defined here. The single source of truth in code is
[`src/prooflens/engine/verdicts.py`](../src/prooflens/engine/verdicts.py); the
golden set asserts the exact reason string per image, so any change here that
shifts an outcome fails CI unless the golden expectations are updated in the
same PR.

## Bands (the decision driver)

ProofLens reports one of three bands. The band is written back to LeadSquared
**first**, before score and reason, because it is what a reviewer acts on.

| Band | Score | Meaning |
|------|-------|---------|
| **Clear** | ≥ 70 | No capture-integrity issues found. |
| **Doubtful** | 40–69 | A quality or soft signal warrants a second look. |
| **Suspect** | < 40 | A hard integrity signal fired (recapture, duplicate, wrong content). |

Bands are never conveyed by colour alone. If a UI colours them
(green/amber/red), the band **word** is always shown alongside.

## Reasons (one per failure mode)

Exactly one human-readable reason string per outcome. Rules, enforced by
[`tests/unit/test_verdict_copy.py`](../tests/unit/test_verdict_copy.py):

- **≤ 90 characters.**
- **Plain language** a first-time reader understands.
- **Names the evidence** ("screen edge and glare detected"), never an internal
  check name (no "Laplacian", "dHash", "moiré", "EXIF").
- **Never depends on colour** to convey meaning.

| Failure mode | Reason string | Typical band |
|---|---|---|
| Recycled image (exact/near duplicate) | `Recycled image — matches a photo already submitted for this account.` | Suspect / Doubtful |
| Photo of another screen (recapture) | `Photo of another screen — screen edge and glare detected.` | Suspect |
| Designed graphic / meme / screenshot | `Designed graphic or screenshot, not a photo of a live scene.` | Suspect |
| No people or irrelevant scene | `No people or relevant scene detected in the photo.` | Suspect |
| Too blurred to assess | `Too blurred to assess — please retake in better light.` | Doubtful |
| Scored without content analysis (vision unavailable) | `Scored without content analysis — vision check unavailable.` | Doubtful |
| Clear (no issues found) | `Clear — no capture-integrity issues found.` | Clear |

## Precedence

When several signals fire, the most decision-critical reason wins, in this
order (integrity → quality → transparency → clear):

1. Recycled image
2. Photo of another screen
3. Designed graphic / screenshot
4. No people / irrelevant scene
5. Too blurred to assess
6. Scored without content analysis
7. Clear

So a blurred re-upload reads **"Recycled image"**, not "Too blurred" — the
integrity failure is what matters.

## Write-back order

Custom fields are written to LeadSquared in this order: **band, score, reason**.
The band is the decision-driver and is written first.

## Tone

ProofLens **scores and flags; it never blocks an upload and never claims to
prove a meeting happened.** Copy is factual and non-accusatory: it describes
what was observed in the image, not a judgement about the person. "Suspect"
describes the *image*, never the rep.
