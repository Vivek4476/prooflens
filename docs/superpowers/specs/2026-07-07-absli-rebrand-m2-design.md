# ABSLI-first Rebrand + M2 Adjudication Spine — Design

Date: 2026-07-07
Status: Approved (design), pending implementation plan

## Goal

Turn ProofLens from a generic "Dev Tenant" demo into a product that reads as
**built for Aditya Birla Sun Life Insurance (ABSLI)**, and make the Review Queue
actually work end-to-end. Target: a polished, enterprise-grade experience
suitable for an **ABSLI leadership demo**.

Two decisions locked with the user:
1. **Logo asset:** keep the existing "Aditya Birla Capital — Life Insurance"
   lockup artwork (a genuine Aditya Birla life-insurance brand); fix its fit.
   Text labels read **"Aditya Birla Sun Life Insurance"**.
2. **Brand relationship:** **ABSLI-first** — ABSLI leads the chrome; ProofLens
   is the engine underneath ("Powered by ProofLens").

## Scope

In scope (this spec):
- Identity flip to ABSLI-first in the app chrome.
- Tenant renamed from "Dev Tenant" → "Aditya Birla Sun Life Insurance" at the
  source (DB seed + data migration + frontend fallback constant).
- Logo fit fix (proper aspect-ratio container; no more square clipping).
- **M2 adjudication spine:** `POST /v1/results/{id}/review` implemented, results
  carry a review block, Review Queue wired to real decisions.

Out of scope (separate follow-on spec):
- Dashboard v2 (deltas/trends), analytics date-range/legend, editable settings,
  SSO/RBAC identity. These are real but deferred to keep this unit focused.

## Current state (verified)

- `scripts/seed_dev_tenant.py` seeds `slug="dev"`, `name="Dev Tenant"`. The
  frontend `TenantSwitcher` shows the admin API's tenant name (or falls back to
  the hardcoded "Aditya Birla Capital" when the admin API isn't reachable).
- Chrome is **ProofLens-first**: `Brandmark` (ProofLens product wordmark) on top,
  `TenantSwitcher` (tenant) secondary below it in the sidebar masthead.
- Logo `frontend/public/brand/abc-life-insurance.png` is 412×200 (~2:1). It is
  rendered inside a `h-8 w-8` (32px) square with `overflow-hidden` and
  `h-5 w-auto` → the wide lockup is hard-clipped. Root cause of "bad fit."
- Backend `results` table (`src/prooflens/db/models.py`) has **no** review
  columns. `POST /v1/results/{id}/review` is **not implemented**; the Review
  Queue honestly shows a "pending" toast on action. `audit_log` table exists.
- `frontend/src/lib/api/client.ts` already has `reviewDecision(id, decision,
  note)` posting to `/v1/results/{id}/review`.

## Design

### 1. Identity — ABSLI-first chrome

Replace the ProofLens-hero masthead with an ABSLI-primary one.

- **New `components/brand/AbsliMasthead.tsx`** (or refactor of the existing
  masthead block in `SidebarInner`): renders the ABSLI logo (via `TenantLogo`,
  §2) alongside the wordmark **"Aditya Birla Sun Life Insurance"** as the
  top-level identity. This is the primary brand.
- **ProofLens as engine credit:** a small, muted **"Powered by ProofLens ·
  Capture Integrity"** mark — placed in the sidebar footer (replacing the
  current ProofLens `Brandmark` hero use). ProofLens no longer competes with
  ABSLI for primary attention.
- **Remove** the `TenantSwitcher` dropdown chrome (multi-tenant switching is an
  M4 concern; a single-tenant ABSLI demo shouldn't imply a switcher). Keep the
  code path minimal — ABSLI is simply the workspace.
- **Fallback name** in the frontend updated from "Aditya Birla Capital" →
  "Aditya Birla Sun Life Insurance" so the identity is correct even if the admin
  API is unreachable.

Components affected: `components/brand/Brandmark.tsx` (demoted to engine credit
or replaced by a `PoweredByProofLens` mark), `components/brand/TenantSwitcher.tsx`
(removed/replaced by `AbsliMasthead`), `components/layout/Sidebar.tsx`
(`SidebarInner` masthead + footer rework), `components/layout/MobileNav.tsx`
(shares `SidebarInner`, inherits the change).

### 2. Logo fit — `components/brand/TenantLogo.tsx`

Stop forcing a ~2:1 lockup into a square.

- New `TenantLogo` component: renders the PNG inside a white rounded card sized
  to the logo's real proportions — `object-contain`, `max-h-*` + horizontal
  padding, `w-auto`, **no `overflow-hidden` clipping**. The full "Aditya Birla
  Capital — Life Insurance" lockup shows crisp and uncropped.
- Two sizes: a **masthead** size (larger, horizontal, in the sidebar) and a
  **compact** size for topbar/mobile/collapsed contexts.
- `onError` fallback to a small "ABSLI" text badge (mirrors current resilience).

### 3. Tenant identity at the source

- **`scripts/seed_dev_tenant.py`:** change `name="Dev Tenant"` →
  `name="Aditya Birla Sun Life Insurance"`. Keep `slug="dev"` (internal id; not
  user-visible; avoids churn on `DEFAULT_TENANT` and existing result rows).
- **Alembic data migration:** idempotent `UPDATE tenants SET name=… WHERE
  slug='dev' AND name='Dev Tenant'` so the already-seeded live DB is renamed on
  deploy without reseeding. No schema change here; pairs with §4's migration.

### 4. M2 — Review Queue works end-to-end

**Data model** (`src/prooflens/db/models.py`, `Result`): add nullable columns —
- `review_status: str | None` — one of `approve | reject | false_positive |
  escalate` (null = pending).
- `review_note: str | None`.
- `reviewed_at: datetime | None`.
- `reviewer: str | None`.

Alembic migration adds these as nullable (no backfill needed; existing rows =
pending). Combined with §3's data update in the same migration revision or an
adjacent one.

**Endpoint** `POST /v1/results/{id}/review` (`src/prooflens/api/scoring.py` or a
new `review` router):
- Body: `{ "decision": "approve|reject|false_positive|escalate", "note"?: str }`.
  Note the client currently sends `decision` (align backend to that field name).
- Resolves the result (tenant-scoped), 404 if unknown.
- Sets the review columns; `reviewer = "Demo Operator"` (until SSO); `reviewed_at
  = now()`.
- Writes an `audit_log` row: `event="review.decision"`, `detail={result_id,
  decision, note, reviewer}`.
- Returns the updated result dict including a **`review` block**:
  `{ status, note, reviewed_at, reviewer }`.

**Read paths:** `GET /v1/results` and `GET /v1/results/{id}` include the `review`
block. `GET /v1/results?review=pending|approve|reject|false_positive|escalate`
filters server-side (frontend still guards client-side for safety).

**Repo layer** (`src/prooflens/service/repo.py` Protocol,
`src/prooflens/db/repo.py` Postgres, in-memory repo): add
`record_review(result_id, decision, note, reviewer) -> ResultView`, and surface
the review fields in the result view / `to_dict`.

**Frontend Review Queue** (`app/(app)/review/page.tsx`,
`components/review/ReviewCard.tsx`):
- Remove the "endpoint pending" disclosure card.
- Real optimistic decision → success toast → item leaves the queue.
- Show `reviewer · reviewed_at` on decided items (and in history / verdict
  detail).
- Keyboard shortcuts on the focused card: `A` approve, `R` reject, `F` false
  positive, `E` escalate.
- `useResults` filters out already-actioned (`review_status != null`) items.

**Verdict Detail** (`app/(app)/verdict/[id]/page.tsx`): render the review block
(status, reviewer, timestamp, note) when present.

**Types** (`frontend/src/lib/api/types.ts`): add the `review` block to
`ResultItem`, and `ReviewDecision` includes `escalate`.

## Testing

Backend (`tests/integration/test_scoring_api.py` or a new
`test_review_api.py`):
- `test_review_decision_records_and_returns_block` — POST approve → 200, result
  has `review.status == "approve"`, reviewer + reviewed_at set.
- `test_review_unknown_result_404`.
- `test_review_invalid_decision_422`.
- `test_review_writes_audit_log` — an `audit_log` row with `event=review.decision`.
- `test_results_review_filter` — `?review=pending` excludes actioned items.
- `test_get_result_includes_review_block`.

Frontend: manual/demo verification (queue action → item leaves, toast, reviewer
shown; keyboard shortcuts). No new test harness introduced here.

## Migration & deploy notes

- One Alembic revision adds the four nullable `results` columns **and** renames
  the seeded tenant (idempotent guard on `slug='dev'`). Safe on the live free-
  tier Postgres; nullable adds don't lock meaningfully at demo scale.
- No frontend env changes. No new provider keys.
- `slug` stays `dev`; `DEFAULT_TENANT` unchanged; existing results untouched.

## Risks

- **Field-name drift:** client posts `decision`; backend must accept `decision`
  (not `status`). Called out so the plan pins it.
- **Reviewer identity is a placeholder** ("Demo Operator") until SSO/RBAC (M4) —
  acceptable and honestly labeled for the demo.
- **Logo remains the ABC lockup**, not the official ABSLI "Sun Life" artwork —
  an explicit, user-approved tradeoff; text labels carry the ABSLI name.
