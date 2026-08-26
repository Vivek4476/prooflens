# ProofLens Redesign — The Glass Cockpit

**Date:** 2026-08-24 (updated 2026-08-25)
**Status:** Design + open items resolved; deployment target set. **Ready for Phase-1 implementation plan.**
**Supersedes:** the multi-page reviewer UI (now collapsed to a single page)

---

## 1. Problem & context

ProofLens is a **fully-automated image-authenticity engine** for ABSLI field-force
"proof-of-meeting" photos: an LSQ webhook delivers a photo → a pipeline of checks →
a fused **0–100 score + band (Suspect / Doubtful / Clear / Unassessed) + one-line reason**
→ written back to LSQ. The engine (`src/prooflens`) is strong. The product *around* it is not:
the frontend has collapsed to a single page, prod's API instance sleeps on Render's free tier,
and the July audit's highest-leverage gaps (capture provenance, calibration) are still open.

We are giving it a makeover. Locked decisions from the brainstorm:

- **Scope:** a *premium product layer* over the existing engine. The FastAPI backend is reused;
  the frontend is rebuilt. **Not** a broader CRM, **not** a re-platform onto Twenty.
- **The product is fully automated.** No human adjudicates a photo. There is **no triage queue**
  and **no "mark genuine/fraud"** action. The human watches, trusts, and audits the machine, and
  acts only on the *system* (retries, tuning, investigations).
- **The human-facing app = Mission Control (live) + Audit Ledger (record).** Watch decisions
  stream in real time; drill into any one to see *why*; search the immutable history for disputes.
- **Intelligence spent in two places:** a *harder-to-fool verdict* (engine) **and** a *copilot layer*
  (summaries, clustering, anomaly, NL search).

Approved visual reference (interactive mock): the Mission Control artifact built during the brainstorm.

---

## 2. Foundation (stack)

Evolve the existing stack; do not adopt a foreign one.

| Layer | Choice | Why |
|---|---|---|
| Framework | **Next.js 15 App Router + React 18 + TypeScript** | already in `frontend/`; keep routing/SSR |
| UI system | **shadcn/ui + Tailwind** primitives we own | Twenty/Linear-grade polish, restyled to ABSLI brand, no license baggage |
| Data | **TanStack Query** over the existing **REST** API | matches FastAPI; no GraphQL rewrite |
| Charts | **Recharts / Tremor** | KPI sparklines, decision-mix, trends |
| Live | **Server-Sent Events (SSE)** from the API | one-way decision stream; simpler than websockets |
| Tokens | **`frontend/src/styles/tokens.css` (existing ABSLI tokens)** | single source of truth; crimson = brand-only, indigo = interaction, verdict hues = band-only, always paired with the word |

**Explicitly rejected:** forking Twenty's components — it is **AGPL-3.0** (a licensing landmine for a
proprietary ABSLI tool) and GraphQL-native. We mine the open-source CRMs (Twenty's density &
detail-panel patterns, Frappe's list-views) for *inspiration only*, and build on shadcn primitives.

---

## 3. The product surface (phased)

### Phase 1 — Mission Control + Audit Ledger  *(this spec's build target)*

The daily-driver "glass cockpit." One operator (compliance) watches the automation.

**Mission Control (home)**
- **Health KPI strip:** decisions today, auto-cleared %, Suspect/fraud %, avg confidence, P50
  latency, and a vision-engine status light. Each with a delta and a sparkline.
- **Live decision stream:** auto-decisions arrive in real time (SSE), each stamped
  `✓ LSQ` (written back) or `◷ retry queued` (Unassessed). Newest on top, capped list.
- **System-level alerts:** fraud-rate breaches, latency spikes, per-rep anomalies. Actionable at
  the *system* level only.
- **Decision mix** (today's band distribution) and **Provenance coverage** gauge (% of captures
  signed — the lead trust metric).

**Decision drawer (read-only "why")** — opens from any stream row or ledger entry:
- evidence photo + capture-metadata overlay + **provenance seal**;
- verdict ring + band + reason;
- **copilot case summary** (auto-written, risky spans highlighted);
- **why-it-decided** check breakdown, showing which gate capped the score;
- signals/provenance key-values;
- footer states **"Auto-decided & written to LSQ"**; the only controls act on the system —
  **Re-run scoring**, **Flag for model review**, **Open in Audit Ledger**. No verdict override.

**Audit Ledger** — searchable, immutable record of every automated decision (rep, opportunity,
band, score, confidence, timestamp, reasoning snapshot). Filters by band/rep/team/region/date;
each row opens the same read-only drawer. This is the dispute/compliance backbone (DPDP export).

**The one deliberate escape hatch:** a **dispute → automatic re-score** path. A contested decision
can be *re-run by the machine* (fresh vision pass, updated provenance), producing a new immutable
decision linked to the original. This is **not** manual grading — no human sets a band. **DECIDED
2026-08-25 (kept):** machine-driven re-score only; the verdict always comes from the engine.

### Phase 2 — Analytics *(separate follow-on spec)*
Fraud trends over time, rep/team leaderboards, region drill-down. Kill the misleading `avg_score`
KPI (audit finding C3) — report band distribution and provenance coverage instead.

### Phase 3 — Live Score Theater *(separate follow-on spec)*
The stakeholder showcase: drop a photo, watch the pipeline light up check-by-check, land on a
verdict. Reuses the drawer's anatomy with orchestrated motion.

---

## 4. Intelligence

### 4a. Engine — harder-to-fool verdict *(large; its own sub-project, tracked separately)*
- **Capture provenance / liveness** — signed on-device capture (Play Integrity / App Attest,
  C2PA, nonce-in-frame). Highest-leverage audit gap (stops stock/AI/screenshot photos scoring
  Clear). Requires mobile-capture (LSQ camera) integration — **out of scope for the Phase-1 UI
  build**, but the UI is designed provenance-first (seal, coverage gauge) so it lands cleanly.
- **Vision backend — DECIDED 2026-08-25: NVIDIA free tier.** `meta/llama-3.2-90b-vision-instruct`
  @ `integrate.api.nvidia.com/v1` via the already-wired `nvidia_backend` (`VISION_BACKEND=nvidia`,
  `NVIDIA_API_KEY=nvapi-…`). Validated live: authenticates, reads images (counted people, ID'd
  meeting scene), returns clean JSON (no reasoning-model `<think>` noise), ~8.4s. Free, DPDP-viable
  (US-hosted). Paid first-party (Gemini Flash / Claude Haiku, both wired) is a **future hardening
  option**, not a blocker.
- **Calibrated thresholds** against a labelled validation set (audit C2).

### 4b. Copilot — reviewer experience *(built alongside Phase 1)*
- **Auto-written case summary** — generated at decision time, stored on the decision record, shown
  in the drawer. Plain language, highlights the deciding signals.
- **Near-duplicate clustering** — perceptual-hash grouping surfaced in the drawer/rep view.
- **Per-rep anomaly detection** — submission-rate baselines → alerts (e.g. "4 near-dupes in 7 days").
- **Natural-language search** — "Suspect cases in Mumbai this week" → structured query over decisions.

---

## 5. Architecture & data flow

```
LSQ webhook ──► engine pipeline ──► Decision record (immutable) ──► LSQ writeback
                                          │
                    ┌─────────────────────┼──────────────────────┐
                    ▼                     ▼                       ▼
             SSE stream            Decisions REST API        Audit Ledger
           (Mission Control)      (drawer, analytics)       (search + export)
```

- **Decision record** becomes a first-class, append-only entity: inputs, per-check findings,
  fused score/band/reason, confidence, model id, latency, provenance result, **copilot summary**,
  timestamps. Powers the stream, drawer, ledger, and analytics — one source of truth.
- **New backend surface (REST):** `GET /decisions` (filter/paginate), `GET /decisions/{id}`,
  `GET /decisions/stream` (SSE), `POST /decisions/{id}/rescore` (dispute path),
  `GET /analytics/*` (aggregates), `GET /search?q=` (NL → structured). Provenance verification and
  copilot-summary generation happen inside the pipeline at decision time (stored, not recomputed).

### Component boundaries (frontend)
Each unit has one purpose, a typed prop interface, and is testable in isolation:
`KpiStrip`, `DecisionStream` (+ `useDecisionStream` SSE hook), `AlertsPanel`, `DecisionMix`,
`ProvenanceGauge`, `DecisionDrawer` (composes `EvidenceCard`, `VerdictHeader`, `CopilotSummary`,
`CheckBreakdown`, `SignalsList`), `AuditLedgerTable`, `NlSearchBar`. Data access is centralised in
a typed API client + TanStack Query hooks; components never fetch directly.

---

## 6. Error handling & edge cases
- **Unassessed** is a first-class outcome, never Clear — the stream shows `retry queued`, the
  drawer shows the fail-open note. Preserve the existing fuse.py behaviour.
- **SSE drop** → the hook reconnects with backoff and backfills via `GET /decisions` so the stream
  is never silently stale; a "reconnecting" state is visible.
- **Vision backend down** → health light goes amber/red; new decisions route Unassessed; alert fires.
- **Copilot summary generation fails** → decision still persists; drawer falls back to the
  rule-based reason. Copilot is additive, never load-bearing for a verdict.

## 7. Testing
- Backend: pytest for the new decisions/stream/rescore/search endpoints; the engine keeps its suite.
- Frontend: component tests (Vitest/RTL) per unit; the SSE hook tested against a mock event source;
  `next build` + tsc + lint green as the existing gate.
- Visual truth: the approved artifact is the reference for layout/tokens.

## 8. Deployment target — DigitalOcean droplet *(validated 2026-08-25)*

Production runs on the **existing DO droplet `68.183.94.47`** (shared with the Iris agent), **not**
Render. Validated feasible: 1 vCPU / 1.9 GB RAM (~1.5 GB available), 45 GB disk, Python 3.12.3,
**reaches the NVIDIA vision API (HTTP 200)**. It fits *because* vision is offloaded to NVIDIA's
cloud — the droplet only orchestrates (light FastAPI + small Postgres).

Topology — **native, not Docker** (leaner on a 2 GB shared box; Docker isn't installed):
- **uvicorn** ProofLens API as a **systemd** service (mirror `iris-listen`), bound to `127.0.0.1`.
- **system Postgres** (apt), tuned small (`shared_buffers ~128MB`, `max_connections ~20`), local socket.
- **Caddy** reverse proxy → automatic HTTPS (sslip.io or a real domain), same pattern as the n8n→DO plan.
- **1–2 GB swapfile** added (box has 0 swap today) as headroom on the single vCPU.
- `VISION_BACKEND=nvidia` + `NVIDIA_API_KEY` from a secrets file; migrations + seed via the start script.
- Deploy from `main` via `git pull` + service restart (a small deploy script), **after Phase 1 merges**.

Risk: small shared box. If Iris + ProofLens ever spike together, resize (~$12/mo) or split to a
dedicated droplet. Deploy is a **post-build** step; Phase-1 development uses a fresh local/staging env.

## 9. Out of scope / deferred
- Provenance/liveness capture SDK (§4a) — separate sub-project, gated on LSQ camera + mobile work.
- Phases 2 and 3 — separate specs.
- **Prod revival is deferred deliberately.** The old free-tier Render Postgres expired (~2026-08-05,
  the 30-day free limit), so `prooflens-api` crash-loops on a dead DB host (`failed to resolve host
  dpg-…`). We are **not** resurrecting free-tier prod (it would re-expire). Phase 1 builds against a
  **fresh seeded local/staging environment**; production redeploys on the **DigitalOcean droplet (§8)**
  once the makeover is ready. Old prod data is unrecoverable and near-zero loss (seed/demo only; the
  webhook path never took real traffic).

## 10. Decisions log & open actions
- ✅ **Dispute → re-score hatch** — KEPT (§3): machine-driven re-score, never manual grading.
- ✅ **Vision provider** — NVIDIA free tier (§4a); paid first-party is future hardening.
- ✅ **Prod DB vs fresh env** — build on a fresh seeded env; defer durable deploy.
- ✅ **Hosting** — DigitalOcean droplet, native systemd (§8).
- ⏳ **Owner action:** rotate the Render API key (`rnd_vyVk…`) pasted in chat — exposed in transcript.
