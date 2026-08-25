# Glass Cockpit — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing ProofLens engine into a fully-automated "glass cockpit" — a live Mission Control view and a searchable Audit Ledger, with a read-only "why it decided" drawer and auto-written copilot summaries — reusing the existing component kit and API.

**Architecture:** The backend already persists every decision as a `Result` row and serves `GET /v1/results` (ledger) + `GET /v1/analytics/summary` (KPIs). Phase 1 adds a deterministic copilot summary to each decision, then assembles two new App-Router pages plus a shared read-only drawer from existing primitives. "Live" is short-interval polling of the newest results (not SSE). Vision runs on NVIDIA's free tier.

**Tech Stack:** Backend — Python 3.12, FastAPI, SQLAlchemy, Alembic, pytest. Frontend — Next.js 15 App Router, React 18, TypeScript, Tailwind, TanStack Query, Recharts, framer-motion, Vitest + Testing Library.

## Global Constraints

- **No human adjudication.** No "mark genuine/fraud" control anywhere. Human actions are read-only or system-level only. (spec §1)
- **Verdict colors are band-only, always paired with the word.** Use `BAND_META` from `frontend/src/lib/verdict.ts`; brand crimson is masthead/primary only; indigo (`--accent`) for interaction. (spec §2)
- **Unassessed is a first-class outcome, never Clear.** Preserve `fuse.py` behaviour; the stream/drawer show it as its own neutral band. (spec §6)
- **Copilot is additive, never load-bearing.** If a summary is missing, fall back to `result.reason`. (spec §6)
- **Vision backend = NVIDIA free tier** (`meta/llama-3.2-90b-vision-instruct`); `VISION_BACKEND=nvidia`, `NVIDIA_API_KEY=nvapi-…`. (spec §4a)
- **Reuse before building.** Prefer existing components (`ScoreRing`, `VerdictBadge`, `ChecksList`, `MetricCard`, `ResultsTable`, `Card`, `EmptyState`, `Skeleton`) and hooks (`useResults`, `useAnalytics`). DRY / YAGNI / TDD / frequent commits.
- **Tests:** backend `pytest` (from repo root, venv active); frontend `npm test` (`vitest run`) from `frontend/`. Vitest globals are OFF — import `{ describe, it, expect }` from `"vitest"`.

---

## File Structure

**Backend (create/modify):**
- `src/prooflens/engine/summarize.py` *(create)* — pure `summarize_decision(verdict) -> str`.
- `src/prooflens/db/models.py` *(modify)* — add `copilot_summary` column to `Result`.
- `src/prooflens/db/migrations/versions/<rev>_add_copilot_summary.py` *(create)* — Alembic migration.
- `src/prooflens/service/repo.py` + `src/prooflens/db/repo.py` *(modify)* — thread `copilot_summary` through `record_result`.
- `src/prooflens/service/views.py` *(modify)* — expose `copilot_summary` on `ResultView.to_dict()`.
- `src/prooflens/api/scoring.py` + `src/prooflens/service/processor.py` *(modify)* — generate + persist the summary.
- `tests/live/test_nvidia_live.py` *(create)* — opt-in live smoke test.

**Frontend (create/modify):**
- `frontend/src/lib/api/types.ts` *(modify)* — add `copilot_summary?` to `ResultItem`.
- `frontend/src/lib/live.ts` *(create)* — pure `pickNewIds(prev, next)` + `useLiveDecisions()` hook.
- `frontend/src/lib/provenance.ts` *(create)* — pure `provenanceSignal(checks)`.
- `frontend/src/components/decision/DecisionDrawer.tsx` *(create)* — read-only slide-over.
- `frontend/src/components/mission/DecisionStream.tsx`, `AlertsPanel.tsx`, `DecisionMixBar.tsx`, `ProvenanceGauge.tsx` *(create)*.
- `frontend/src/app/(app)/mission-control/page.tsx` *(create)*.
- `frontend/src/app/(app)/ledger/page.tsx` *(create)*.
- `frontend/src/lib/nav.ts` *(modify)* — add Mission Control + Audit Ledger.

---

## Task 1: Deterministic copilot summary (pure backend function)

**Files:**
- Create: `src/prooflens/engine/summarize.py`
- Test: `tests/unit/test_summarize.py`

**Interfaces:**
- Consumes: `Verdict` (`engine/types.py`: `score, band, reason, reason_code, checks: list[CheckOutcome], rubric_version`); `CheckOutcome` (`name, available, score, summary, ...`).
- Produces: `summarize_decision(verdict: Verdict) -> str` — one/two-sentence plain-language summary, ≤400 chars, deterministic.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_summarize.py
from prooflens.engine.types import Verdict, CheckOutcome
from prooflens.engine.summarize import summarize_decision


def _v(band, reason_code, reason, checks):
    return Verdict(score=0, band=band, reason=reason, reason_code=reason_code,
                   checks=checks, rubric_version="v3")


def test_clear_decision_reads_positive():
    v = _v("Clear", "clear", "Genuine meeting photo",
           [CheckOutcome(name="content", available=True, score=90, summary="two people, meeting")])
    out = summarize_decision(v)
    assert "Clear" in out
    assert len(out) <= 400


def test_suspect_names_the_deciding_signal():
    v = _v("Suspect", "recycled", "Reused image",
           [CheckOutcome(name="uniqueness", available=True, score=5, summary="near-duplicate of 3 prior")])
    out = summarize_decision(v)
    assert "duplicate" in out.lower() or "reused" in out.lower()


def test_unassessed_explains_no_grade():
    v = _v("Unassessed", "no_content_analysis", "Vision check unavailable",
           [CheckOutcome(name="content", available=False, score=None, summary="")])
    out = summarize_decision(v)
    assert "unassess" in out.lower() or "not graded" in out.lower() or "unavailable" in out.lower()


def test_is_deterministic():
    v = _v("Doubtful", "single_person", "Only one person",
           [CheckOutcome(name="content", available=True, score=55, summary="one face")])
    assert summarize_decision(v) == summarize_decision(v)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_summarize.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'prooflens.engine.summarize'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/prooflens/engine/summarize.py
"""Deterministic, plain-language summary of a decision — no LLM call.

Built from the fired reason_code and the per-check outcomes so it is free,
instant, and testable. Copilot is additive: callers fall back to verdict.reason.
"""
from __future__ import annotations

from .types import Verdict

# reason_code -> a plain-language clause explaining the driver.
_REASON_CLAUSE = {
    "clear": "the capture looks like a genuine meeting",
    "recycled": "the image is a near-duplicate of earlier submissions (reused imagery)",
    "screen_recapture": "the frame is a photo of a screen, not a live camera capture",
    "designed_graphic": "the image is a designed graphic / screenshot, not a photo",
    "no_people_or_irrelevant": "no people are present or the scene is irrelevant to a visit",
    "not_a_visit": "the scene does not read as a customer visit",
    "single_person": "only one person is visible, so a two-party meeting can't be confirmed",
    "no_visit_context": "people are present but no meeting interaction is evident",
    "too_blurred": "the image is too blurred to assess",
    "no_content_analysis": "the vision check was unavailable, so it was not graded",
}


def _evidence(verdict: Verdict) -> str:
    """The most informative available check summary, if any."""
    for c in verdict.checks:
        if c.available and c.summary:
            return c.summary.strip().rstrip(".")
    return ""


def summarize_decision(verdict: Verdict) -> str:
    clause = _REASON_CLAUSE.get(verdict.reason_code, verdict.reason.lower())
    if verdict.band == "Unassessed":
        body = f"Not graded — {clause}. Routed for automatic retry."
    else:
        body = f"Scored {verdict.band} because {clause}."
    ev = _evidence(verdict)
    if ev:
        body = f"{body} Detail: {ev}."
    return body[:400]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_summarize.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/prooflens/engine/summarize.py tests/unit/test_summarize.py
git commit -m "feat(engine): deterministic copilot summary generator"
```

---

## Task 2: Persist the copilot summary on every decision

**Files:**
- Modify: `src/prooflens/db/models.py` (Result model, ~line 140-169)
- Create: `src/prooflens/db/migrations/versions/<rev>_add_copilot_summary.py`
- Modify: `src/prooflens/service/repo.py` (Repo protocol `record_result`, ~line 52) and `src/prooflens/db/repo.py` (`record_result`, ~line 122; `list_results`/`get_result` view mapping)
- Modify: `src/prooflens/service/views.py` (ResultView + `to_dict`)
- Modify: `src/prooflens/api/scoring.py` (`score_bytes`, ~line 78-155) and `src/prooflens/service/processor.py` (`process_job`, ~line 67-72)
- Test: `tests/unit/test_result_summary_persist.py`

**Interfaces:**
- Consumes: `summarize_decision` (Task 1).
- Produces: `Result.copilot_summary: str | None`; `record_result(..., copilot_summary: str | None = None)`; `ResultView.to_dict()["copilot_summary"]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_result_summary_persist.py
# Uses the existing in-memory/sqlite repo fixture pattern from tests/conftest.py.
from prooflens.engine.types import Verdict, CheckOutcome


def _verdict():
    return Verdict(score=18, band="Suspect", reason="Reused image", reason_code="recycled",
                   checks=[CheckOutcome(name="uniqueness", available=True, score=5,
                                        summary="near-duplicate of 3 prior")],
                   rubric_version="v3")


def test_record_result_persists_copilot_summary(repo, tenant_id):
    rid = repo.record_result(tenant_id, None, _verdict(), copilot_summary="Scored Suspect because reused.")
    view = repo.get_result(rid, tenant_id=tenant_id)
    assert view is not None
    assert view.to_dict()["copilot_summary"] == "Scored Suspect because reused."


def test_copilot_summary_defaults_none(repo, tenant_id):
    rid = repo.record_result(tenant_id, None, _verdict())
    view = repo.get_result(rid, tenant_id=tenant_id)
    assert view.to_dict()["copilot_summary"] is None
```

> Note: reuse the `repo` and `tenant_id` fixtures already defined in `tests/conftest.py` (the same ones `tests/integration/test_scoring_api.py` uses). If they are not module-visible, import/replicate them from conftest.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_result_summary_persist.py -q`
Expected: FAIL — `TypeError: record_result() got an unexpected keyword argument 'copilot_summary'`

- [ ] **Step 3a: Add the column to the model**

In `src/prooflens/db/models.py`, inside `class Result`, after the `checks` column add:

```python
    copilot_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
```

(Confirm `Text` is imported at the top of `models.py`; `Job.last_error` already uses `Text`, so it is.)

- [ ] **Step 3b: Extend the Repo protocol and Postgres impl**

In `src/prooflens/service/repo.py`, add `copilot_summary: str | None = None` to the `record_result` signature (keyword-only, after `source`).

In `src/prooflens/db/repo.py` `record_result`, add to the `Result(...)` constructor:

```python
        copilot_summary=copilot_summary,
```

and add `copilot_summary: str | None = None` to its signature (keyword-only, after `source`).

- [ ] **Step 3c: Expose on the view**

In `src/prooflens/service/views.py`, add `copilot_summary: str | None` to `ResultView` and include it in `to_dict()`:

```python
            "copilot_summary": self.copilot_summary,
```

Wherever `db/repo.py` builds a `ResultView` from a `Result` row (in `get_result` and `list_results`), pass `copilot_summary=row.copilot_summary`.

- [ ] **Step 3d: Generate the migration**

```bash
alembic revision -m "add copilot_summary to results"
```

Edit the new file in `src/prooflens/db/migrations/versions/`:

```python
def upgrade() -> None:
    op.add_column("results", sa.Column("copilot_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("results", "copilot_summary")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_result_summary_persist.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5a: Wire generation into both scoring paths**

In `src/prooflens/api/scoring.py` `score_bytes`, immediately after the verdict is produced and before `repo.record_result(...)`, add:

```python
    from ..engine.summarize import summarize_decision
    copilot_summary = summarize_decision(verdict)
```

and pass `copilot_summary=copilot_summary` into that `record_result(...)` call.

In `src/prooflens/service/processor.py` `process_job`, after `verdict = score(image_bytes, ctx)` and before `repo.record_result(...)`, add the same two lines and pass `copilot_summary=copilot_summary` into `record_result(...)`.

- [ ] **Step 5b: Run the full backend suite**

Run: `python -m pytest -q`
Expected: PASS (all green, including existing scoring/processor tests)

- [ ] **Step 6: Commit**

```bash
git add src/prooflens/db/models.py src/prooflens/db/migrations/versions src/prooflens/service/repo.py src/prooflens/db/repo.py src/prooflens/service/views.py src/prooflens/api/scoring.py src/prooflens/service/processor.py tests/unit/test_result_summary_persist.py
git commit -m "feat(decisions): persist deterministic copilot summary on every result"
```

---

## Task 3: NVIDIA vision — dev env + opt-in live smoke test

**Files:**
- Modify: `.env.example` (add NVIDIA + `VISION_BACKEND=nvidia`)
- Create: `tests/live/test_nvidia_live.py`

**Interfaces:**
- Consumes: existing `NvidiaBackend` + `config.py` `nvidia_*` fields (already present).
- Produces: a green `VISION_BACKEND=nvidia` dev config + a live smoke test mirroring `tests/live/test_github_live.py`.

- [ ] **Step 1: Write the live smoke test (opt-in, skipped without a key)**

```python
# tests/live/test_nvidia_live.py
import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("NVIDIA_API_KEY"),
    reason="set NVIDIA_API_KEY to run the live NVIDIA vision smoke test",
)


def test_nvidia_backend_returns_content_assessment():
    from prooflens.vision.nvidia_backend import NvidiaBackend
    from prooflens.vision.schema import ContentAssessment
    from PIL import Image
    import io

    img = Image.new("RGB", (400, 300), (230, 232, 238))
    buf = io.BytesIO(); img.save(buf, "JPEG")
    backend = NvidiaBackend(api_key=os.environ["NVIDIA_API_KEY"])
    result = backend.assess(buf.getvalue())  # match the real method name in nvidia_backend.py
    assert isinstance(result, ContentAssessment)
```

> Before running, open `src/prooflens/vision/nvidia_backend.py` and confirm the public method name/signature (e.g. `assess(image_bytes)` vs `analyze(...)`); adjust the call above to match exactly.

- [ ] **Step 2: Run it (expect skip without a key, pass with one)**

Run: `python -m pytest tests/live/test_nvidia_live.py -q`
Expected: `1 skipped`
Then with the key from `~/Desktop/Workspace/po-recruitment-engine/.env`:
Run: `NVIDIA_API_KEY=nvapi-… python -m pytest tests/live/test_nvidia_live.py -q`
Expected: PASS (1 passed)

- [ ] **Step 3: Set the dev default**

In `.env.example`, add (or update):

```
VISION_BACKEND=nvidia
NVIDIA_API_KEY=nvapi-your-key-here
NVIDIA_MODEL=meta/llama-3.2-90b-vision-instruct
```

- [ ] **Step 4: Commit**

```bash
git add .env.example tests/live/test_nvidia_live.py
git commit -m "feat(vision): NVIDIA free backend as dev default + live smoke test"
```

---

## Task 4: Frontend types + live-decisions hook

**Files:**
- Modify: `frontend/src/lib/api/types.ts` (`ResultItem`)
- Create: `frontend/src/lib/live.ts`
- Test: `frontend/src/lib/live.test.ts`

**Interfaces:**
- Consumes: `useResults` (`lib/api/hooks.ts`), `ResultItem` (`lib/api/types.ts`).
- Produces: `pickNewIds(prevIds: string[], next: ResultItem[]): Set<string>`; `useLiveDecisions(limit?: number)` returning `{ items: ResultItem[]; newIds: Set<string>; isLoading: boolean }`.

- [ ] **Step 1: Add the field to the type**

In `frontend/src/lib/api/types.ts`, add to `interface ResultItem`:

```typescript
  copilot_summary?: string | null;
```

- [ ] **Step 2: Write the failing test for the pure diff**

```typescript
// frontend/src/lib/live.test.ts
import { describe, it, expect } from "vitest";
import { pickNewIds } from "./live";
import type { ResultItem } from "./api/types";

const r = (id: string): ResultItem => ({ id } as ResultItem);

describe("pickNewIds", () => {
  it("returns ids present in next but not in prev", () => {
    const out = pickNewIds(["a", "b"], [r("c"), r("b"), r("a")]);
    expect(out).toEqual(new Set(["c"]));
  });
  it("is empty when nothing is new", () => {
    expect(pickNewIds(["a", "b"], [r("a"), r("b")])).toEqual(new Set());
  });
  it("treats the first load as no-animation (empty prev -> empty new)", () => {
    expect(pickNewIds([], [r("a"), r("b")])).toEqual(new Set());
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run (from `frontend/`): `npm test -- live`
Expected: FAIL — cannot find module `./live`

- [ ] **Step 4: Implement**

```typescript
// frontend/src/lib/live.ts
import { useEffect, useRef, useState } from "react";
import { useResults } from "./api/hooks";
import type { ResultItem } from "./api/types";

/** Ids in `next` not seen in `prevIds`. Empty on first load (prevIds empty) to avoid a flash. */
export function pickNewIds(prevIds: string[], next: ResultItem[]): Set<string> {
  if (prevIds.length === 0) return new Set();
  const prev = new Set(prevIds);
  return new Set(next.filter((x) => !prev.has(x.id)).map((x) => x.id));
}

/** Newest decisions on a short poll, tracking which arrived since the last tick (for animation). */
export function useLiveDecisions(limit = 25) {
  const q = useResults({ limit });
  q.refetchInterval; // hooks already poll; see note below
  const prevIds = useRef<string[]>([]);
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const items = q.data?.items ?? [];

  useEffect(() => {
    if (!q.data) return;
    setNewIds(pickNewIds(prevIds.current, items));
    prevIds.current = items.map((x) => x.id);
  }, [q.dataUpdatedAt]); // fires each successful poll

  return { items, newIds, isLoading: q.isLoading };
}
```

> `useResults` currently sets `refetchInterval: 20_000`. For the live feel, add an optional faster interval: in `lib/api/hooks.ts`, allow `useResults(params, refetchInterval = 20_000)` and call `useResults({ limit }, 4_000)` here. Keep the default unchanged for other callers.

- [ ] **Step 5: Run test to verify it passes**

Run (from `frontend/`): `npm test -- live`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/api/types.ts frontend/src/lib/live.ts frontend/src/lib/live.test.ts frontend/src/lib/api/hooks.ts
git commit -m "feat(fe): copilot_summary type + live-decisions polling hook"
```

---

## Task 5: Provenance signal (pure frontend helper)

**Files:**
- Create: `frontend/src/lib/provenance.ts`
- Test: `frontend/src/lib/provenance.test.ts`

**Interfaces:**
- Consumes: `CheckOutcome` (`lib/api/types.ts`).
- Produces: `provenanceSignal(checks: CheckOutcome[]): { state: "signed" | "unsigned" | "na"; label: string }`.
  Phase-1 proxy (true C2PA is deferred): `unsigned` if the `recapture` check flags a screen photo or the `exif` check is unavailable/failing; `signed` if `exif` is available and passing; else `na`.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/lib/provenance.test.ts
import { describe, it, expect } from "vitest";
import { provenanceSignal } from "./provenance";
import type { CheckOutcome } from "./api/types";

const c = (name: string, available: boolean, score: number | null): CheckOutcome =>
  ({ name, available, score, summary: "", data: {} } as CheckOutcome);

describe("provenanceSignal", () => {
  it("signed when exif is available and strong", () => {
    expect(provenanceSignal([c("exif", true, 90)]).state).toBe("signed");
  });
  it("unsigned when a screen recapture is detected", () => {
    expect(provenanceSignal([c("exif", true, 90), c("recapture", true, 5)]).state).toBe("unsigned");
  });
  it("unsigned when exif is unavailable", () => {
    expect(provenanceSignal([c("exif", false, null)]).state).toBe("unsigned");
  });
  it("na when there are no relevant checks", () => {
    expect(provenanceSignal([c("content", true, 80)]).state).toBe("na");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npm test -- provenance`
Expected: FAIL — cannot find module `./provenance`

- [ ] **Step 3: Implement**

```typescript
// frontend/src/lib/provenance.ts
import type { CheckOutcome } from "./api/types";

/** Phase-1 proxy for capture provenance, derived from existing checks.
 *  Full signed-capture (C2PA / Play Integrity) is a separate engine sub-project. */
export function provenanceSignal(
  checks: CheckOutcome[],
): { state: "signed" | "unsigned" | "na"; label: string } {
  const by = (n: string) => checks.find((c) => c.name === n);
  const exif = by("exif");
  const recap = by("recapture");

  if (recap && recap.available && (recap.score ?? 100) < 30) {
    return { state: "unsigned", label: "Screen recapture — unverifiable" };
  }
  if (exif) {
    if (!exif.available) return { state: "unsigned", label: "No capture metadata" };
    return (exif.score ?? 0) >= 50
      ? { state: "signed", label: "Capture metadata present" }
      : { state: "unsigned", label: "Capture metadata weak/stripped" };
  }
  return { state: "na", label: "Provenance not assessed" };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `frontend/`): `npm test -- provenance`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/provenance.ts frontend/src/lib/provenance.test.ts
git commit -m "feat(fe): provenance-signal proxy derived from checks"
```

---

## Task 6: Read-only Decision Drawer

**Files:**
- Create: `frontend/src/components/decision/DecisionDrawer.tsx`
- Test: `frontend/src/components/decision/DecisionDrawer.test.tsx`

**Interfaces:**
- Consumes: `ResultItem` (`lib/api/types`), `ScoreRing`, `VerdictBadge`, `ChecksList`, `BAND_META` (`lib/verdict`), `provenanceSignal` (Task 5), `Button`.
- Produces: `DecisionDrawer({ result, onClose }: { result: ResultItem | null; onClose: () => void })`. Renders nothing when `result` is null. No adjudication controls; actions are read-only/navigational only.

- [ ] **Step 1: Write the failing component test**

```tsx
// frontend/src/components/decision/DecisionDrawer.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { DecisionDrawer } from "./DecisionDrawer";
import type { ResultItem } from "@/lib/api/types";

const result = {
  id: "OPP-1", created_at: "2026-08-25T10:00:00Z", band: "Suspect", score: 18,
  reason: "Reused image", reason_code: "recycled", rubric_version: "v3",
  processing_ms: 1200, source: "webhook", opportunity_id: "OPP-1", rep_id: "R1",
  checks: [{ name: "uniqueness", available: true, score: 5, summary: "near-dupe", data: {} }],
  copilot_summary: "Scored Suspect because reused imagery.",
} as unknown as ResultItem;

describe("DecisionDrawer", () => {
  it("renders nothing when result is null", () => {
    const { container } = render(<DecisionDrawer result={null} onClose={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });
  it("shows the band word, the copilot summary, and NO adjudication control", () => {
    render(<DecisionDrawer result={result} onClose={() => {}} />);
    expect(screen.getByText("Suspect")).toBeInTheDocument();
    expect(screen.getByText(/reused imagery/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /mark genuine|confirm fraud/i })).toBeNull();
    expect(screen.getByText(/written back to lsq/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npm test -- DecisionDrawer`
Expected: FAIL — cannot find module `./DecisionDrawer`

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/decision/DecisionDrawer.tsx
"use client";

import Link from "next/link";
import { X } from "lucide-react";
import { ScoreRing } from "@/components/verdict/ScoreRing";
import { VerdictBadge } from "@/components/verdict/VerdictBadge";
import { ChecksList } from "@/components/verdict/ChecksList";
import { Button } from "@/components/ui/Button";
import { provenanceSignal } from "@/lib/provenance";
import { formatRelative } from "@/lib/utils";
import type { ResultItem } from "@/lib/api/types";

export function DecisionDrawer({
  result,
  onClose,
}: {
  result: ResultItem | null;
  onClose: () => void;
}) {
  if (!result) return null;
  const prov = provenanceSignal(result.checks);
  const written = result.band !== "Unassessed";

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Decision detail">
      <div className="absolute inset-0 bg-black/55" onClick={onClose} />
      <aside className="absolute right-0 top-0 bottom-0 flex w-[560px] max-w-[94vw] flex-col border-l border-border-strong bg-canvas shadow-2xl">
        <header className="flex items-center gap-3 border-b border-border bg-surface px-5 py-4">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-text-muted">
              ProofLens · automated decision
            </div>
            <h2 className="text-[15px] font-semibold">{result.rep_id ?? result.opportunity_id ?? result.id}</h2>
          </div>
          <button aria-label="Close" onClick={onClose} className="ml-auto rounded-md border border-border p-2 text-text-muted hover:bg-surface-2">
            <X size={16} />
          </button>
        </header>

        <div className="overflow-y-auto px-5 py-5">
          <div className={`mb-4 flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium ${written ? "bg-verdict-clear-bg text-verdict-clear-fg" : "bg-verdict-unassessed-bg text-verdict-unassessed-fg"}`}>
            {written
              ? <>✓ Auto-decided &amp; written back to LSQ · {result.opportunity_id ?? result.id}</>
              : <>◷ Held as Unassessed — auto-retry queued · not written to LSQ</>}
          </div>

          <div className="flex items-center gap-4 py-2">
            <ScoreRing score={result.score} band={result.band} size={84} />
            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wider text-text-muted">Verdict</div>
              <VerdictBadge band={result.band} size="lg" />
              <p className="mt-2 max-w-[42ch] text-sm text-text-secondary">{result.reason}</p>
            </div>
          </div>

          <section className="mt-4 rounded-xl border border-border bg-surface p-4">
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              Case summary · <span className="text-accent">auto-written</span>
            </div>
            <p className="text-sm leading-relaxed">{result.copilot_summary ?? result.reason}</p>
          </section>

          <section className="mt-4 rounded-xl border border-border bg-surface p-4">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              Provenance
            </div>
            <div className="text-sm">
              <span className={prov.state === "signed" ? "text-verdict-clear-fg" : prov.state === "unsigned" ? "text-verdict-suspect-fg" : "text-verdict-unassessed-fg"}>
                {prov.state === "signed" ? "✓" : prov.state === "unsigned" ? "✕" : "—"} {prov.label}
              </span>
            </div>
          </section>

          <section className="mt-4 rounded-xl border border-border bg-surface p-4">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              Why it decided
            </div>
            <ChecksList checks={result.checks} rubricVersion={result.rubric_version} />
          </section>

          <div className="mt-4 flex gap-2">
            <Link href={`/verdict/${result.id}`} className="flex-1">
              <Button className="w-full">Open full record</Button>
            </Link>
          </div>
          <p className="mt-2 text-center text-[11px] text-text-muted">
            Decided {formatRelative(result.created_at)} · the verdict is automated — no human override.
          </p>
        </div>
      </aside>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `frontend/`): `npm test -- DecisionDrawer`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/decision/
git commit -m "feat(fe): read-only decision drawer (no adjudication)"
```

---

## Task 7: Mission Control page

**Files:**
- Create: `frontend/src/components/mission/DecisionStream.tsx`
- Create: `frontend/src/components/mission/AlertsPanel.tsx`
- Create: `frontend/src/components/mission/DecisionMixBar.tsx`
- Create: `frontend/src/components/mission/ProvenanceGauge.tsx`
- Create: `frontend/src/app/(app)/mission-control/page.tsx`
- Test: `frontend/src/components/mission/DecisionStream.test.tsx`

**Interfaces:**
- Consumes: `useAnalytics`, `useLiveDecisions` (Task 4), `MetricCard`, `Card`/`CardHeader`, `VerdictBadge`, `DecisionDrawer` (Task 6), `BAND_META`, `AnalyticsSummary`/`ResultItem` types.
- Produces: the four mission components (each a default-styled export) and a `MissionControlPage` default export.

- [ ] **Step 1: Write the failing test for the stream (the one piece with logic)**

```tsx
// frontend/src/components/mission/DecisionStream.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DecisionStream } from "./DecisionStream";
import type { ResultItem } from "@/lib/api/types";

const items = [
  { id: "1", band: "Clear", score: 86, rep_id: "Amit", opportunity_id: "OPP-1",
    created_at: "2026-08-25T10:00:00Z", checks: [] },
  { id: "2", band: "Suspect", score: 18, rep_id: "Raj", opportunity_id: "OPP-2",
    created_at: "2026-08-25T09:59:00Z", checks: [] },
] as unknown as ResultItem[];

describe("DecisionStream", () => {
  it("renders a row per decision and calls onSelect when a row is clicked", () => {
    const onSelect = vi.fn();
    render(<DecisionStream items={items} newIds={new Set(["1"])} onSelect={onSelect} />);
    expect(screen.getByText("Amit")).toBeInTheDocument();
    expect(screen.getByText("Raj")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Amit"));
    expect(onSelect).toHaveBeenCalledWith(items[0]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npm test -- DecisionStream`
Expected: FAIL — cannot find module `./DecisionStream`

- [ ] **Step 3a: Implement DecisionStream**

```tsx
// frontend/src/components/mission/DecisionStream.tsx
"use client";

import { VerdictBadge } from "@/components/verdict/VerdictBadge";
import { formatRelative } from "@/lib/utils";
import type { ResultItem } from "@/lib/api/types";

export function DecisionStream({
  items,
  newIds,
  onSelect,
}: {
  items: ResultItem[];
  newIds: Set<string>;
  onSelect: (r: ResultItem) => void;
}) {
  return (
    <div className="flex flex-col">
      {items.map((r) => {
        const written = r.band !== "Unassessed";
        return (
          <button
            key={r.id}
            onClick={() => onSelect(r)}
            className={`grid grid-cols-[1fr_auto_auto] items-center gap-3 border-b border-border px-4 py-2.5 text-left hover:bg-surface-2 ${newIds.has(r.id) ? "motion-safe:animate-[fadein_.45s_ease]" : ""}`}
          >
            <div>
              <div className="text-[13px] font-semibold">{r.rep_id ?? r.opportunity_id}</div>
              <div className="font-mono text-[10px] text-text-muted">{r.opportunity_id}</div>
            </div>
            <VerdictBadge band={r.band} size="sm" />
            <div className="text-right">
              <div className="text-[11px] text-text-muted">{written ? "✓ LSQ" : "◷ retry"}</div>
              <div className="text-[10px] tabular-nums text-text-muted">{formatRelative(r.created_at)}</div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
```

Add the keyframe once to `frontend/src/styles/tokens.css` (or the global stylesheet):

```css
@keyframes fadein { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: none; } }
```

- [ ] **Step 3b: Implement DecisionMixBar**

```tsx
// frontend/src/components/mission/DecisionMixBar.tsx
import type { AnalyticsSummary } from "@/lib/api/types";

const SEG = [
  { key: "Clear", cls: "bg-verdict-clear" },
  { key: "Doubtful", cls: "bg-verdict-doubtful" },
  { key: "Suspect", cls: "bg-verdict-suspect" },
  { key: "Unassessed", cls: "bg-verdict-unassessed" },
] as const;

export function DecisionMixBar({ dist }: { dist: AnalyticsSummary["band_distribution"] }) {
  const total = SEG.reduce((s, x) => s + (dist?.[x.key] ?? 0), 0) || 1;
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-md">
        {SEG.map((s) => (
          <div key={s.key} className={s.cls} style={{ width: `${((dist?.[s.key] ?? 0) / total) * 100}%` }} />
        ))}
      </div>
      <div className="mt-3 flex flex-col gap-2">
        {SEG.map((s) => (
          <div key={s.key} className="flex items-center gap-2 text-xs">
            <span className={`h-2.5 w-2.5 rounded-sm ${s.cls}`} />
            {s.key}
            <span className="ml-auto tabular-nums font-semibold">{dist?.[s.key] ?? 0}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3c: Implement ProvenanceGauge**

```tsx
// frontend/src/components/mission/ProvenanceGauge.tsx
export function ProvenanceGauge({ pct }: { pct: number }) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <b className="text-xl tabular-nums">{pct}%</b>
        <span className="text-[11px] text-text-muted">captures signed</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded bg-surface-3">
        <div className="h-full rounded bg-accent" style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-2 text-[11px] leading-snug text-text-muted">
        Signed on-device capture is the lead trust metric. Unsigned captures cannot score Clear on provenance alone.
      </p>
    </div>
  );
}
```

- [ ] **Step 3d: Implement AlertsPanel (derived from analytics — no new backend)**

```tsx
// frontend/src/components/mission/AlertsPanel.tsx
import type { AnalyticsSummary } from "@/lib/api/types";

/** Derive system-level alerts from the analytics summary. Pure, testable-by-eye. */
export function AlertsPanel({ a }: { a: AnalyticsSummary | undefined }) {
  const alerts: { cls: string; title: string; body: string }[] = [];
  if (a) {
    if ((a.suspect_pct ?? 0) >= 8)
      alerts.push({ cls: "text-verdict-suspect-fg", title: "Fraud rate elevated",
        body: `Suspect rate at ${a.suspect_pct}% today (threshold 8%).` });
    const health = a.system_health;
    if (health && (health.scored_without_content_pct ?? 0) >= 10)
      alerts.push({ cls: "text-verdict-doubtful-fg", title: "Vision degradation",
        body: `${health.scored_without_content_pct}% scored without vision (fail-open).` });
  }
  if (alerts.length === 0)
    return <p className="px-4 py-6 text-sm text-text-muted">No active alerts. System nominal.</p>;
  return (
    <div className="flex flex-col">
      {alerts.map((al, i) => (
        <div key={i} className="border-b border-border px-4 py-3 last:border-b-0">
          <b className={`text-[12.5px] ${al.cls}`}>{al.title}</b>
          <p className="mt-0.5 text-[11.5px] text-text-secondary">{al.body}</p>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3e: Implement the page**

```tsx
// frontend/src/app/(app)/mission-control/page.tsx
"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/ui/Card";
import { MetricCard } from "@/components/ui/MetricCard";
import { DecisionStream } from "@/components/mission/DecisionStream";
import { AlertsPanel } from "@/components/mission/AlertsPanel";
import { DecisionMixBar } from "@/components/mission/DecisionMixBar";
import { ProvenanceGauge } from "@/components/mission/ProvenanceGauge";
import { DecisionDrawer } from "@/components/decision/DecisionDrawer";
import { useAnalytics } from "@/lib/api/hooks";
import { useLiveDecisions } from "@/lib/live";
import type { ResultItem } from "@/lib/api/types";

export default function MissionControlPage() {
  const analytics = useAnalytics();
  const { items, newIds } = useLiveDecisions(25);
  const [selected, setSelected] = useState<ResultItem | null>(null);
  const a = analytics.data;

  return (
    <div className="space-y-6">
      <PageHeader title="Mission Control" description="Automated decisions, live — watch, trust, audit." />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard label="Decisions today" value={a?.images_today ?? "—"} />
        <MetricCard label="Suspect / fraud" value={a?.suspect_pct ?? "—"} suffix="%" />
        <MetricCard label="Avg score" value={a?.avg_score ?? "—"} />
        <MetricCard label="Avg latency" value={a?.avg_processing_ms ?? "—"} suffix="ms" />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.55fr_1fr]">
        <Card>
          <CardHeader title="Live decision stream" subtitle="auto-scored & written to LSQ" />
          <DecisionStream items={items} newIds={newIds} onSelect={setSelected} />
        </Card>
        <div className="space-y-6">
          <Card>
            <CardHeader title="Alerts" subtitle="system-level" />
            <AlertsPanel a={a} />
          </Card>
          <Card>
            <CardHeader title="Decision mix" subtitle="today" />
            <div className="p-4"><DecisionMixBar dist={a?.band_distribution} /></div>
          </Card>
          <Card>
            <CardHeader title="Provenance coverage" />
            <div className="p-4"><ProvenanceGauge pct={64} /></div>
          </Card>
        </div>
      </div>

      <DecisionDrawer result={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
```

> `ProvenanceGauge pct={64}` is a placeholder until a real coverage metric lands with the provenance engine sub-project. Leave a `// TODO(provenance-engine): replace with real coverage` comment above it so it is not mistaken for live data.

- [ ] **Step 4: Run tests + typecheck + build**

Run (from `frontend/`): `npm test -- DecisionStream` → PASS
Run: `npx tsc --noEmit` → no errors
Run: `npm run build` → succeeds, route `/mission-control` present

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/mission/ frontend/src/app/(app)/mission-control/ frontend/src/styles/tokens.css
git commit -m "feat(fe): Mission Control page — live stream, KPIs, alerts, mix, provenance"
```

---

## Task 8: Audit Ledger page

**Files:**
- Create: `frontend/src/app/(app)/ledger/page.tsx`
- Test: covered by build/tsc + reuse of already-tested `ResultsTable`.

**Interfaces:**
- Consumes: `useResults`, `ResultsTable` (`components/history/ResultsTable`), `DecisionDrawer`, `PageHeader`, `Card`, `EmptyState`, `TableSkeleton`, `BAND_META`.
- Produces: `LedgerPage` default export — filterable, immutable record; row click opens the same read-only drawer.

- [ ] **Step 1: Implement the page (reuses the tested `ResultsTable` + `useResults`)**

```tsx
// frontend/src/app/(app)/ledger/page.tsx
"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { ResultsTable } from "@/components/history/ResultsTable";
import { DecisionDrawer } from "@/components/decision/DecisionDrawer";
import { useResults } from "@/lib/api/hooks";
import type { Band } from "@/lib/api/types";
import type { ResultItem } from "@/lib/api/types";
import { FileSearch } from "lucide-react";

const BANDS: (Band | "all")[] = ["all", "Suspect", "Doubtful", "Clear", "Unassessed"];

export default function LedgerPage() {
  const [band, setBand] = useState<Band | "all">("all");
  const [selected, setSelected] = useState<ResultItem | null>(null);
  const q = useResults({ limit: 100, band: band === "all" ? undefined : band });
  const items = q.data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader title="Audit Ledger" description="Every automated decision, immutable and searchable." />

      <div className="flex gap-2">
        {BANDS.map((b) => (
          <button
            key={b}
            onClick={() => setBand(b)}
            className={`rounded-full border px-3 py-1 text-xs ${band === b ? "border-text bg-text text-canvas" : "border-border text-text-secondary hover:border-border-strong"}`}
          >
            {b === "all" ? "All" : b}
          </button>
        ))}
      </div>

      <Card>
        {q.isLoading ? (
          <TableSkeleton rows={8} />
        ) : items.length === 0 ? (
          <EmptyState icon={FileSearch} title="No decisions" what="No decisions match this filter yet." />
        ) : (
          <div onClickCapture={(e) => {
            const row = (e.target as HTMLElement).closest("[data-result-id]");
            const id = row?.getAttribute("data-result-id");
            const hit = items.find((x) => x.id === id);
            if (hit) setSelected(hit);
          }}>
            <ResultsTable items={items} />
          </div>
        )}
      </Card>

      <DecisionDrawer result={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
```

> `ResultsTable` must expose `data-result-id` on each row for the click-capture to resolve. If it does not, add `data-result-id={item.id}` to its row element (`components/history/ResultsTable.tsx`) — a one-line, backward-compatible change — and note it in the commit.

- [ ] **Step 2: Typecheck + build**

Run (from `frontend/`): `npx tsc --noEmit` → no errors
Run: `npm run build` → succeeds, route `/ledger` present

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/(app)/ledger/ frontend/src/components/history/ResultsTable.tsx
git commit -m "feat(fe): Audit Ledger page over /v1/results with read-only drawer"
```

---

## Task 9: Navigation wiring

**Files:**
- Modify: `frontend/src/lib/nav.ts`

**Interfaces:**
- Consumes: `NAV` array + `NavItem` type.
- Produces: Mission Control (top) + Audit Ledger entries; keeps existing routes.

- [ ] **Step 1: Add nav entries**

In `frontend/src/lib/nav.ts`, import two icons and prepend/insert entries so the array becomes:

```typescript
import {
  BarChart3, LayoutDashboard, ScanSearch, Settings, UploadCloud,
  History as HistoryIcon, Radar, FileSearch, type LucideIcon,
} from "lucide-react";

export const NAV: NavItem[] = [
  { label: "Mission Control", href: "/mission-control", icon: Radar },
  { label: "Audit Ledger", href: "/ledger", icon: FileSearch },
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "Analyze Photo", href: "/analyze", icon: ScanSearch },
  { label: "Bulk upload", href: "/bulk", icon: UploadCloud },
  { label: "Upload History", href: "/history", icon: HistoryIcon },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Settings", href: "/settings", icon: Settings },
];
```

- [ ] **Step 2: Verify nav + active-state**

Run (from `frontend/`): `npm run build` → succeeds
Manual: `npm run dev`, confirm the sidebar shows Mission Control + Audit Ledger and both routes render with the drawer working.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/nav.ts
git commit -m "feat(fe): add Mission Control + Audit Ledger to nav"
```

---

## Self-Review

**Spec coverage:**
- Mission Control (live stream, KPI strip, alerts, decision mix, provenance gauge) → Task 7. ✅
- Read-only decision drawer (evidence*, verdict, copilot summary, checks, provenance, no override) → Task 6. ✅ (*full evidence photo depends on image retention; drawer shows verdict+metadata; image thumbnail is a Phase-1.5 add when retention is confirmed — noted below.)
- Audit Ledger (searchable immutable record, drawer per row) → Task 8. ✅
- Copilot auto-summary generated at decision time, stored, shown → Tasks 1, 2, 6. ✅
- NVIDIA free vision → Task 3. ✅
- Band-only verdict colors / no adjudication / Unassessed-first / copilot-additive → enforced across Tasks 6–8. ✅

**Deliberately deferred (documented, not gaps):**
- **Dispute → re-score endpoint** — needs image retention or LSQ re-fetch; Phase-1.5.
- **True NL search** — Phase 1 ships structured band filtering (Task 8); LLM query-parsing is a fast-follow.
- **Real provenance coverage %** and **evidence photo thumbnail** — both gated on the provenance-engine sub-project / image-retention decision; Task 7 marks the gauge as placeholder.
- **Per-rep anomaly + near-duplicate cluster** in the drawer — Phase 2 (needs a small aggregate endpoint).
- **SSE** — polling is used; SSE is an optional future optimization.

**Type consistency:** `ResultItem.copilot_summary?` (Task 4) is produced by `record_result(copilot_summary=…)` (Task 2) and consumed by the drawer (Task 6). `Band` and `BAND_META` come from `lib/verdict.ts`/`types.ts` throughout. `useResults`/`useAnalytics` signatures match `lib/api/hooks.ts`. `record_result` keyword `copilot_summary` matches between protocol (`service/repo.py`) and impl (`db/repo.py`).

**Deployment:** per spec §8 — after these tasks merge, deploy on the DO droplet (native systemd + Postgres + Caddy + swap, `VISION_BACKEND=nvidia`). Deployment is its own runbook, not a code task in this plan.
