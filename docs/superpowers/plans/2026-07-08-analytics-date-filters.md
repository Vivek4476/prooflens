# Analytics Date-Range Filters — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional `start_date`/`end_date` query params to `GET /v1/analytics/summary` so the frontend can scope charts to a time window.

**Architecture:** A pure `parse_bound` helper turns an ISO-8601 bound (date-only → whole-day, or full timestamp → exact instant) into a tz-aware UTC `datetime`. The endpoint parses at the boundary (400 on bad input) and passes `datetime` bounds to `Repo.list_results`, which filters half-open `[start, end)` — SQL in PostgresRepo, list-comp in InMemoryRepo.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy, pytest.

## Global Constraints

- Accept BOTH forms: date-only `YYYY-MM-DD` (whole-day, `end` = that day inclusive) and full ISO-8601 timestamp (exact instant). All bounds are **UTC**; naive timestamps are treated as UTC.
- Filtering is **half-open**: `created_at >= start AND created_at < end`.
- Omitting both params reproduces current behaviour exactly (backward compatible).
- Unparseable date → **HTTP 400**. `start > end` → valid but **empty** result (not an error).
- Response shape is **unchanged** — same keys, filtered aggregates.
- Out of scope, leave unchanged: tenant-scoping of analytics reads; the 5,000-row aggregation cap.

---

### Task 1: `parse_bound` date parser

**Files:**
- Create: `src/prooflens/api/date_range.py`
- Test: `tests/unit/test_date_range.py`

**Interfaces:**
- Produces: `parse_bound(value: str | None, *, is_end: bool) -> datetime | None` — returns a tz-aware UTC `datetime` or `None`; raises `ValueError` on malformed input.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_date_range.py
"""parse_bound: date-only -> whole-day; full timestamp -> exact instant; UTC."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from prooflens.api.date_range import parse_bound

UTC = timezone.utc


def test_none_and_empty_return_none():
    assert parse_bound(None, is_end=False) is None
    assert parse_bound("", is_end=True) is None


def test_date_only_start_is_midnight_utc():
    assert parse_bound("2026-07-08", is_end=False) == datetime(2026, 7, 8, tzinfo=UTC)


def test_date_only_end_adds_one_day():
    # end is inclusive of the whole day -> next midnight
    assert parse_bound("2026-07-08", is_end=True) == datetime(2026, 7, 9, tzinfo=UTC)


def test_full_timestamp_with_offset_is_exact_instant():
    assert parse_bound("2026-07-08T14:30:00+00:00", is_end=False) == datetime(
        2026, 7, 8, 14, 30, tzinfo=UTC
    )


def test_naive_timestamp_is_treated_as_utc():
    assert parse_bound("2026-07-08T14:30:00", is_end=False) == datetime(
        2026, 7, 8, 14, 30, tzinfo=UTC
    )


def test_malformed_raises_valueerror():
    with pytest.raises(ValueError):
        parse_bound("not-a-date", is_end=False)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_date_range.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prooflens.api.date_range'`

- [ ] **Step 3: Implement the helper**

```python
# src/prooflens/api/date_range.py
"""Parse ISO-8601 date-range bounds for analytics filtering.

Accepts a date-only string (YYYY-MM-DD, whole-day semantics) or a full
ISO-8601 timestamp (exact instant). Returns a timezone-aware UTC datetime, or
None when no bound is given. Raises ValueError on malformed input so the API
layer can return HTTP 400.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


def parse_bound(value: str | None, *, is_end: bool) -> datetime | None:
    if not value:
        return None
    v = value.strip()
    # Date-only (YYYY-MM-DD) -> whole-day semantics.
    if len(v) == 10 and v[4] == "-" and v[7] == "-":
        d = date.fromisoformat(v)  # raises ValueError on a bad date
        dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        return dt + timedelta(days=1) if is_end else dt
    # Full timestamp -> exact instant; naive input is treated as UTC.
    dt = datetime.fromisoformat(v)  # raises ValueError on malformed input
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_date_range.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/prooflens/api/date_range.py tests/unit/test_date_range.py
git commit -m "feat(api): add parse_bound ISO-8601 date-range parser"
```

---

### Task 2: `list_results` gains `start`/`end` filtering

Add two optional `datetime` params to the `Repo` protocol and both implementations. Half-open filter.

**Files:**
- Modify: `src/prooflens/service/repo.py` (the `Repo` Protocol `list_results` signature + `InMemoryRepo.list_results`)
- Modify: `src/prooflens/db/repo.py` (`PostgresRepo.list_results`)
- Test: `tests/unit/test_inmemory_review.py` (this file already exercises `InMemoryRepo`)

**Interfaces:**
- Consumes: nothing new.
- Produces: `list_results(self, *, limit=50, offset=0, band=None, review=None, start: datetime | None = None, end: datetime | None = None) -> tuple[list[ResultView], int]` on the protocol and both repos.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_inmemory_review.py` (import `datetime`/`timezone` at top if not present):

```python
def test_list_results_filters_by_date_range():
    from datetime import datetime, timezone
    from prooflens.service.repo import InMemoryRepo
    from prooflens.service.views import TenantView
    from prooflens.engine.scoring_config import ScoringConfig
    from tests.helpers import make_verdict  # existing helper used elsewhere in this file

    repo = InMemoryRepo([TenantView(
        id="t1", slug="dev", webhook_secret="s", field_map={},
        scoring=ScoringConfig(), vision_backend="stub",
    )])
    # Two results, then pin their timestamps to known days.
    repo.record_result("t1", None, make_verdict())
    repo.record_result("t1", None, make_verdict())
    repo.results[0].created_at = "2026-07-01T09:00:00+00:00"
    repo.results[1].created_at = "2026-07-08T09:00:00+00:00"

    start = datetime(2026, 7, 5, tzinfo=timezone.utc)
    rows, total = repo.list_results(start=start)
    assert total == 1
    assert rows[0].created_at.startswith("2026-07-08")

    end = datetime(2026, 7, 5, tzinfo=timezone.utc)
    rows, total = repo.list_results(end=end)
    assert total == 1
    assert rows[0].created_at.startswith("2026-07-01")
```

If `make_verdict` isn't the helper this file uses, use the same result-construction helper already imported at the top of `tests/unit/test_inmemory_review.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_inmemory_review.py -k date_range -v`
Expected: FAIL — `list_results() got an unexpected keyword argument 'start'`

- [ ] **Step 3: Update the Protocol signature**

In `src/prooflens/service/repo.py`, add `start`/`end` to the `Repo.list_results` protocol method signature (add `from datetime import datetime` to the imports if absent):

```python
    def list_results(
        self, *, limit: int = 50, offset: int = 0, band: str | None = None,
        review: str | None = None,
        start: datetime | None = None, end: datetime | None = None,
    ) -> tuple[list[ResultView], int]:
        """Newest-first page of results + total matching count."""
        ...
```

- [ ] **Step 4: Implement `InMemoryRepo.list_results` filtering**

In `src/prooflens/service/repo.py`, update `InMemoryRepo.list_results` to the same signature and add the half-open filter after the band/review filters (before the `reversed`):

```python
    def list_results(
        self, *, limit: int = 50, offset: int = 0, band: str | None = None,
        review: str | None = None,
        start: datetime | None = None, end: datetime | None = None,
    ) -> tuple[list[ResultView], int]:
        rows = [r for r in self.results if band is None or r.band == band]
        if review == "pending":
            rows = [r for r in rows if r.review_status is None]
        elif review:
            rows = [r for r in rows if r.review_status == review]
        if start is not None:
            rows = [r for r in rows if r.created_at and datetime.fromisoformat(r.created_at) >= start]
        if end is not None:
            rows = [r for r in rows if r.created_at and datetime.fromisoformat(r.created_at) < end]
        rows = list(reversed(rows))  # newest first
        return rows[offset : offset + limit], len(rows)
```

- [ ] **Step 5: Implement `PostgresRepo.list_results` filtering**

In `src/prooflens/db/repo.py`, update `PostgresRepo.list_results` to the same signature and add SQL filters after the band/review filters, before `.count()`:

```python
        if start is not None:
            query = query.filter(Result.created_at >= start)
        if end is not None:
            query = query.filter(Result.created_at < end)
```

Add `from datetime import datetime` to the file's imports if absent.

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_inmemory_review.py -k date_range -v`
Expected: PASS

- [ ] **Step 7: Run both repo test files (no regressions)**

Run: `.venv/bin/python -m pytest tests/unit/test_inmemory_review.py tests/unit/test_db_models.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/prooflens/service/repo.py src/prooflens/db/repo.py tests/unit/test_inmemory_review.py
git commit -m "feat(repo): list_results supports half-open start/end date filtering"
```

---

### Task 3: Wire `start_date`/`end_date` onto the analytics endpoint

**Files:**
- Modify: `src/prooflens/api/scoring.py` (`analytics_summary`, ~line 181)
- Test: `tests/integration/test_scoring_api.py`

**Interfaces:**
- Consumes: `parse_bound` (Task 1); `list_results(..., start=, end=)` (Task 2).
- Produces: unchanged response shape; two new optional query params.

- [ ] **Step 1: Write the failing tests**

Add to `tests/integration/test_scoring_api.py`:

```python
def test_analytics_date_filters(client):
    from datetime import date, timedelta
    _upload(client, "meeting.jpg")           # all created "today"
    _upload(client, "screenshot.jpg")
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    all_ = client.get("/v1/analytics/summary").json()
    assert all_["total"] == 2                # no params -> unchanged

    incl = client.get(f"/v1/analytics/summary?start_date={today}").json()
    assert incl["total"] == 2                # today's results are >= today 00:00

    excl = client.get(f"/v1/analytics/summary?start_date={tomorrow}").json()
    assert excl["total"] == 0                # nothing on/after tomorrow


def test_analytics_bad_date_is_400(client):
    r = client.get("/v1/analytics/summary?start_date=not-a-date")
    assert r.status_code == 400


def test_analytics_start_after_end_is_empty_not_error(client):
    _upload(client, "meeting.jpg")
    r = client.get("/v1/analytics/summary?start_date=2999-01-01&end_date=2000-01-01")
    assert r.status_code == 200
    assert r.json()["total"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/integration/test_scoring_api.py -k "date_filters or bad_date or start_after_end" -v`
Expected: FAIL — endpoint doesn't accept `start_date` (param ignored → filters have no effect / assertions fail).

- [ ] **Step 3: Implement the endpoint change**

In `src/prooflens/api/scoring.py`, add the import near the top:

```python
from .date_range import parse_bound
```

(`Query` is already imported from fastapi.) Change the `analytics_summary` signature and the `list_results` call:

```python
@router.get("/v1/analytics/summary")
def analytics_summary(
    repo: Repo = Depends(get_repo),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
) -> dict:
    try:
        start = parse_bound(start_date, is_end=False)
        end = parse_bound(end_date, is_end=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid date range: {exc}") from exc
    items, _total = repo.list_results(limit=5000, offset=0, start=start, end=end)
    # ... existing aggregation over `items` is unchanged ...
```

Leave the rest of the aggregation body exactly as-is (it already operates on the `items` list).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/integration/test_scoring_api.py -k "date_filters or bad_date or start_after_end" -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the whole scoring-api file (no regressions)**

Run: `.venv/bin/python -m pytest tests/integration/test_scoring_api.py -q`
Expected: PASS (including the pre-existing `test_results_and_analytics_populate`)

- [ ] **Step 6: Commit**

```bash
git add src/prooflens/api/scoring.py tests/integration/test_scoring_api.py
git commit -m "feat(api): start_date/end_date query params on analytics summary"
```

---

### Task 4: Full-suite gate + OpenAPI note

- [ ] **Step 1: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 2: Lint + types**

Run: `.venv/bin/ruff check src tests && .venv/bin/mypy src`
Expected: clean.

- [ ] **Step 3: Confirm the OpenAPI surfaced the params (frontend handoff)**

Run:
```bash
.venv/bin/python -c "
from prooflens.api.app import create_app
schema = create_app().openapi()
params = schema['paths']['/v1/analytics/summary']['get'].get('parameters', [])
print(sorted(p['name'] for p in params))
"
```
Expected: `['end_date', 'start_date']`.

This confirms `/openapi.json` changed → the frontend must run `npm run gen:api` after merge and wire the date picker to pass the params. Flag this at handoff.

---

## Self-Review

- **Spec coverage:** both date forms + whole-day/instant semantics (Task 1); half-open filter in both repos (Task 2); endpoint params + 400 + start>end empty (Task 3); backward-compat + OpenAPI/frontend note (Task 3 + Task 4). All spec sections mapped.
- **Placeholder scan:** the only deferral is Task 2's test helper (`make_verdict`) — pointed at "the same helper this file already imports" because the exact result-construction helper lives in that test file. All code steps show concrete code.
- **Type consistency:** `parse_bound(value, *, is_end)` used identically in Tasks 1 & 3; `list_results(..., start, end)` signature identical across the protocol and both repos (Task 2) and the call site (Task 3).
