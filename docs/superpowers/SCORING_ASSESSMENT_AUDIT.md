# ProofLens — Assessment-Logic Audit (2026-07-12)

Independent third-party review of the image-authenticity **assessment logic** — the
code that turns a proof-of-visit photo into a `0–100 score + band (Suspect/Doubtful/
Clear) + reason`. Two reviewers ran with fresh, adversarial context and blind to each
other — one with a **measurement-science / ML-evaluation** lens, one with a **fraud /
red-team** lens. They converged strongly.

**Bottom line:** the engineering is clean and the fail-open posture is defensible, but
as a *fraud-detection instrument* it is not sound yet: the score is categorical,
nothing is calibrated against ground truth, the "star" signal is an LLM's self-graded
opinion, and there is no liveness / capture-provenance — so the system reduces to "an
LLM's opinion of a JPEG," which is trivially laundered.

---

## 1. Why production scores cluster on a few values (observed, confirmed)

Live prod (92 scored images) — ~80% of scores sit on 4 numbers:

| Score | Count | % | Source |
|------:|------:|--:|--------|
| 20.0 | 34 | 37% | `screen_recapture` / `designed_graphic` / `not_a_visit` caps (all = 20) |
| 15.0 | 19 | 21% | `duplicate` cap |
| 55.0 | 11 | 12% | `weak_visit_context` / `near_duplicate` / `too_blurred` caps |
| 9.0 | 10 | 11% | raw blend for near-zero-content images |
| 30.0 | 3 |  | `no_people` cap |
| 59–90 | 15 |  | genuine gate-free "Clear-ish" blends |

**Root cause** (`engine/fusion/fuse.py:142-149`): `score = min(weighted_blend, lowest_gate_cap)`,
and the caps (`engine/scoring_config.py:43-60`) are fixed constants. Any image that
trips a gate snaps to that constant — so the number carries no more information than
the reason/band it accompanies. The only continuous variation lives in gate-free
images. A second amplifier: when the Groq vision call is unavailable/rate-limited,
content fails open to the `no_content` cap of **69.0 / Doubtful**.

---

## 2. Critical findings (both reviewers agreed)

| # | Finding | Why it matters | File(s) |
|---|---------|----------------|---------|
| **C1** | **No liveness / capture provenance.** EXIF is soft + forgeable; the VLM self-reports "plausibility." A generated / stock / **printed** "two people meeting" photo scores **Clear**. | The whole ballgame for proof-of-visit fraud. Every current check is post-hoc pixel forensics the attacker controls. | `engine/checks/relevance.py:41-49`, `rubrics/v3.yaml` |
| **C2** | **Zero calibration, zero ground truth.** Every threshold (blur 40, dup 6, plausibility 30, bands 40/70, all caps) is hand-picked. The "golden set" is synthetic — a copy-lock, not an accuracy benchmark. | Can't state FPR/recall to an auditor or a wrongly-flagged agent. Cuts tuned on synthetic images won't transfer to rural field photos. | `engine/scoring_config.py`, `tests/golden/` |
| **C3** | **Score is categorical** (`min(blend, cap)`). Near-dup at distance 1 and 6 both score exactly 55. | `avg_score` in analytics is a meaningless mean of category codes — yet it's used to compare agents/zones. Actively misleading. | `engine/fusion/fuse.py:142-149`, `api/analytics.py` |
| **C4** | **Fail-open is an exploit.** Groq free tier 429s → vision unavailable → capped at 69/Doubtful. A fraudster bursts uploads to force 429 and converts a Suspect into a soft Doubtful. The true un-assessed rate is under-counted by `system_health` (because `most_severe` picks another reason when a second gate also fires). | Availability of a free API becomes a fraud lever; on a bad-vision day honest agents also all drop to Doubtful. | `engine/pipeline.py:36-46`, `engine/checks/relevance.py:29-39`, `engine/fusion/fuse.py:131-133` |
| **C5** | **Dedup trivially defeated.** 64-bit dHash, `dup_near=6`: a 5% crop + 1° rotate + re-save pushes past threshold → one real photo → unlimited "visits." A 50k-row recency cap also blinds detection at scale. | Core anti-fraud control bypassed in minutes, scriptable, no ML needed. | `engine/checks/uniqueness.py:77-87`, `db/hashstore.py:20,33` |
| **C6** | **DoS gap (today):** no `Image.MAX_IMAGE_PIXELS` guard — a 25 MB image can decode to hundreds of MP and OOM the Render instance. **Latent SSRF** in the unimplemented `RealLSQClient.fetch_image` (gate is a TODO comment). | Denial of scoring for all agents; SSRF becomes real the moment Phase 3 wires live fetches. | `engine/checks/_imaging.py`, `api/app.py:37`, `lsq/base.py:41-47`, `lsq/real.py:71` |

**Major (false-positive harm to honest agents):** single-agent selfie visits → `SINGLE_PERSON`;
rural/roadside misread → `NOT_A_VISIT` (Suspect); glossy walls → screen-recapture false
positive; low light → `too_blurred`; any Groq outage → everyone drops to Doubtful.

---

## 3. Ranked roadmap (industry-best solutions)

1. **Capture provenance / liveness at the source** — highest leverage. A locked in-app
   camera issuing signed capture attestations (C2PA Content Credentials + Play Integrity /
   iOS App Attest, server-issued nonce burned into the frame). No image without a fresh
   valid attestation may reach *Clear*. Kills the dedup, recapture, and VLM-trust attacks
   at the root. *(C1, C5, and recapture)*
2. **Build a labelled validation set** (a few hundred real ABSL submissions, human-
   adjudicated genuine/not + failure sub-type). Set every threshold by its ROC/PR
   operating point; publish FPR/FNR. Until this exists it's a heuristic prototype, not a
   measurement instrument. *(C2)*
3. **Decouple band from score; kill `avg_score`.** Keep the honest gate→band decision.
   Either replace 0–100 with a *calibrated* P(genuine) fit on the labelled data (logistic/
   GBM over check outputs, reported with a reliability curve), or emit band + reason +
   per-signal breakdown only. *(C3)*
4. **Fix the fail-open floor + harden the VLM.** Vision-unavailable on the default path
   should cap to Suspect-adjacent (≤40) or force mandatory review — not 69. Move
   production scoring to a paid tier with an SLA; add retry backoff. Set `temperature=0` +
   seed, measure test-retest band-flip, fix the `plausibility` default that fails open to
   100, gate on discrete model facts over self-scored integers. *(C4)*
5. **Dedup ensemble + decode bounds.** Add a crop/rotation-robust second hash (pHash/
   embedding) with full-history indexing; raise `dup_near`; surface cross-agent matches.
   Set `Image.MAX_IMAGE_PIXELS`, reject oversized rasters before decode, implement the
   SSRF allowlist before Phase 3. *(C5, C6)*

**Quick wins shippable now:** #4 (fail-open floor) and the `MAX_IMAGE_PIXELS` bound in #5.
**Needs its own brainstorm/spec:** #1 (provenance) and #2 (calibration).

---

## 4. Portable review prompt (for an external model, e.g. GPT)

Self-contained — embeds the algorithm so it works with no repo access. See the chat
transcript / paste block for the full text; it asks the reviewer to assess score
validity, calibration, VLM trust, fail-open, liveness, adversarial evasion, and KPI
trustworthiness, then produce a ranked roadmap.
