# Assessment hardening — shipped + deferred (2026-07-12)

Follow-up to `docs/superpowers/SCORING_ASSESSMENT_AUDIT.md`. This PR ships the
**safe, no-judgment engineering hardening** from the audit. The remaining items
change verdict policy, product surface, or need external systems — they are
**deferred with a proposed approach**, because picking new threshold/cap numbers
autonomously would violate the audit's own finding C2 ("don't ship uncalibrated
thresholds").

## Shipped in this PR (no verdict-policy judgment required)

| Item | Change | Risk |
|------|--------|------|
| **Decode-bomb guard (C6)** | `MAX_IMAGE_PIXELS = 40 MP`; PIL global bomb guard + a pre-decode dimension check in `engine/checks/_imaging.py` so cv2/PIL never allocate a pathological raster (OOM protection on the memory-constrained Render box). Oversized → the deterministic checks report unavailable (fail-open), never a crash. | None — safety only, no verdict change. |
| **SSRF gate (C6)** | New `lsq/ssrf.py::validate_public_http_url` (https-only, rejects loopback/link-local/private/reserved/multicast, incl. `169.254.169.254`), wired into `RealLSQClient.fetch_image` **before** any fetch so Phase 3 cannot ship the sink without the guard. | None — `RealLSQClient` is not used yet (FakeLSQ everywhere). |
| **Vision determinism (M1)** | `OpenAICompatBackend` temperature `0.2 → 0.0` (configurable). Same photo → same assessment; a verdict that flips between calls is indefensible. | Low — strictly more reproducible. |
| **Plausibility fails closed (M2)** | `fuse.py` missing-plausibility default `100 → 0`, aligning with the schema's own coercion. A malformed content response no longer reads as "perfectly plausible." | Very low — in practice the field is always present; this only changes the malformed-response path. |

All covered by new tests (`test_ssrf.py`, `test_imaging_guard.py`,
`test_vision_backend.py`, + a fusion case). Backend suite: 300 passing, ruff + mypy clean.

## Deferred — needs an owner decision (verdict policy)

1. **Fail-open floor (C4).** Today vision-unavailable caps to `no_content = 69.0`
   (one point below Clear), so forcing a Groq 429 downgrades a fake from Suspect to
   near-pass. Options: (a) lower the cap to Suspect-adjacent (`≤39`) so it surfaces
   for review — stronger anti-fraud, but during a real Groq outage *every* legit
   photo shows Suspect; (b) make "unassessed" its own non-graded state; (c) keep
   Doubtful but drop to mid-band (`55`). **Decision needed:** which policy. It is a
   one-line config change once chosen.
2. **Decouple band from score; drop `avg_score` (C3).** The score is categorical
   (`min(blend, cap)`), so `avg_score` in analytics is a mean of category codes.
   Proposal: stop surfacing `avg_score`, report band-mix instead; longer term, add a
   *calibrated* P(genuine) once (4) exists. Touches analytics API + dashboard —
   product decision.
3. **Dedup robustness + scale (C5).** Raise `dup_near`, add a crop/rotation-robust
   second hash (pHash/embedding), index full history (BK-tree / BIGINT popcount)
   instead of the 50k recency window. Needs a schema migration and a calibrated
   threshold — its own PR.
4. **True vision-coverage metric (C4).** Persist `content.available` as a first-class
   result column so `scored_without_content_pct` is exact (today `most_severe` hides
   it when another gate also fires). Needs a migration.

## Deferred — needs an external system

5. **Capture provenance / liveness (C1)** — the highest-leverage fix, but requires a
   locked in-app camera + signed attestation (C2PA + Play Integrity / iOS App
   Attest, server nonce in-frame). Own project.
6. **Labelled calibration set (C2)** — a few hundred human-adjudicated real
   submissions to set every threshold by its ROC/PR operating point. Own effort;
   unblocks (2) and (3).
