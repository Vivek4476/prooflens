# Analytics Date-Range Filters — Revision (default range, validation, gap-fill) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Revise PR #8 so `GET /v1/analytics/summary` defaults to the last 30 days, rejects invalid dates with 400, and returns a gap-filled per-day `series`.

**Architecture:** A `resolve_range` helper turns optional ISO bounds into an always-bounded half-open `[start, end)` UTC range (30-day default; raises `ValueError` on future/order/over-span). A `fill_series` helper enumerates every calendar day in the range, zero-filling empty days. The endpoint wires both in; all other aggregates already run over the date-filtered `list_results` items (from PR #8), so they need no change.

**Tech Stack:** Python 3.14, FastAPI, pytest.

## Global Constraints

- This revises the existing branch `backend/analytics-date-filters` (PR #8); build on its `parse_bound` + `list_results(start, end)`.
- Validation rejects with **HTTP 400** (never clamp): future date, `start > end`, span > **400 days**, or unparseable.
- Default when a bound is omitted: **last 30 days** (`today − 29` … `today`, UTC), always producing a bounded range.
- Analytics is **day-granular** and **UTC**. "Today" = `datetime.now(timezone.utc).date()`.
- Gap-filled `series` spans every calendar day in the resolved range, oldest→newest; empty day = `{date, count:0, clear:0, doubtful:0, suspect:0, avg_score:0}`.
- Do NOT rewrite aggregation as SQL; keep InMemory/Postgres parity.
- The final gate runs ruff over `src tests scripts migrations` (CI does — a narrower local lint previously passed while CI failed).

---

### Task 1: `resolve_range` helper (default + validation)

**Files:**
- Modify: `src/prooflens/api/date_range.py` (add `resolve_range` + constants; keep `parse_bound`)
- Test: `tests/unit/test_date_range.py`

**Interfaces:**
- Consumes: `parse_bound` (existing).
- Produces: `resolve_range(start_date: str | None, end_date: str | None) -> tuple[datetime, datetime]` — an always-bounded half-open `[start, end)` (both tz-aware UTC, non-None); raises `ValueError` on any validation failure.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/unit/test_date_range.py
from datetime import datetime, timedelta, timezone
import pytest
from prooflens.api.date_range import resolve_range

UTC = timezone.utc

def _today():
    return datetime.now(UTC).date()

def test_resolve_defaults_to_last_30_days():
    start, end = resolve_range(None, None)
    assert start.date() == _today() - timedelta(days=29)
    assert end.date() == _today() + timedelta(days=1)      # exclusive next-midnight
    assert (end - start).days == 30

def test_resolve_only_start_defaults_end_to_today():
    d = (_today() - timedelta(days=3)).isoformat()
    start, end = resolve_range(d, None)
    assert start.date() == _today() - timedelta(days=3)
    assert end.date() == _today() + timedelta(days=1)

def test_resolve_only_end_defaults_start_30_back():
    d = (_today() - timedelta(days=2)).isoformat()
    start, end = resolve_range(None, d)
    assert end.date() == _today() - timedelta(days=1)      # exclusive of (d+1)
    assert start.date() == (_today() - timedelta(days=2)) - timedelta(days=29)

def test_resolve_same_day_is_valid():
    d = (_today() - timedelta(days=1)).isoformat()
    start, end = resolve_range(d, d)
    assert (end - start).days == 1

def test_resolve_future_start_rejected():
    d = (_today() + timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match="start_date is in the future"):
        resolve_range(d, None)

def test_resolve_future_end_rejected():
    d = (_today() + timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match="end_date is in the future"):
        resolve_range(None, d)

def test_resolve_start_after_end_rejected():
    s = (_today() - timedelta(days=1)).isoformat()
    e = (_today() - timedelta(days=5)).isoformat()
    with pytest.raises(ValueError, match="start_date must be <= end_date"):
        resolve_range(s, e)

def test_resolve_span_over_400_days_rejected():
    s = (_today() - timedelta(days=500)).isoformat()
    e = _today().isoformat()
    with pytest.raises(ValueError, match="max 400 days"):
        resolve_range(s, e)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_date_range.py -k resolve -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_range'`

- [ ] **Step 3: Implement**

Append to `src/prooflens/api/date_range.py` (ensure `date, timedelta` are imported from `datetime`):

```python
_DEFAULT_DAYS = 30
_MAX_SPAN_DAYS = 400


def _bound_day(value: str | None) -> "date | None":
    dt = parse_bound(value, is_end=False)   # raw day start (or instant); we take the date
    return dt.date() if dt is not None else None


def resolve_range(start_date: str | None, end_date: str | None) -> tuple[datetime, datetime]:
    """Resolve optional ISO date bounds into a bounded half-open [start, end) UTC range.

    Defaults to the last 30 days when a bound is omitted. Day-granular and UTC.
    Raises ValueError (-> HTTP 400) on a future date, start>end, or span > 400 days.
    """
    today = datetime.now(timezone.utc).date()
    start_day = _bound_day(start_date)
    end_day = _bound_day(end_date)

    if start_day is None and end_day is None:
        end_day = today
        start_day = today - timedelta(days=_DEFAULT_DAYS - 1)
    elif start_day is None:
        start_day = end_day - timedelta(days=_DEFAULT_DAYS - 1)
    elif end_day is None:
        end_day = today

    if start_date is not None and start_day > today:
        raise ValueError("start_date is in the future")
    if end_date is not None and end_day > today:
        raise ValueError("end_date is in the future")
    if start_day > end_day:
        raise ValueError("start_date must be <= end_date")
    if (end_day - start_day).days + 1 > _MAX_SPAN_DAYS:
        raise ValueError(f"date range too large (max {_MAX_SPAN_DAYS} days)")

    start = datetime(start_day.year, start_day.month, start_day.day, tzinfo=timezone.utc)
    end_next = end_day + timedelta(days=1)
    end = datetime(end_next.year, end_next.month, end_next.day, tzinfo=timezone.utc)
    return start, end
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_date_range.py -k resolve -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add src/prooflens/api/date_range.py tests/unit/test_date_range.py
git commit -m "feat(api): resolve_range — 30-day default + strict date validation"
```

---

### Task 2: `fill_series` gap-fill helper

**Files:**
- Modify: `src/prooflens/api/date_range.py` (add `fill_series`)
- Test: `tests/unit/test_date_range.py`

**Interfaces:**
- Produces: `fill_series(by_day: dict[str, list], start: datetime, end: datetime) -> list[dict]` — one bucket per calendar day in `[start.date(), (end-1day).date()]`, oldest→newest; empty days zero-filled.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/unit/test_date_range.py
from prooflens.api.date_range import fill_series

class _Row:
    def __init__(self, band, score):
        self.band = band
        self.score = score

def test_fill_series_zero_fills_gaps_in_order():
    start = datetime(2026, 7, 1, tzinfo=UTC)
    end = datetime(2026, 7, 4, tzinfo=UTC)          # covers Jul 1,2,3 (exclusive end)
    by_day = {
        "2026-07-01": [_Row("Clear", 80.0), _Row("Suspect", 10.0)],
        "2026-07-03": [_Row("Doubtful", 50.0)],
    }
    series = fill_series(by_day, start, end)
    assert [b["date"] for b in series] == ["2026-07-01", "2026-07-02", "2026-07-03"]
    assert series[0] == {"date": "2026-07-01", "count": 2, "clear": 1, "doubtful": 0, "suspect": 1, "avg_score": 45.0}
    assert series[1] == {"date": "2026-07-02", "count": 0, "clear": 0, "doubtful": 0, "suspect": 0, "avg_score": 0}
    assert series[2]["count"] == 1 and series[2]["doubtful"] == 1

def test_fill_series_fully_empty_range():
    start = datetime(2026, 7, 1, tzinfo=UTC)
    end = datetime(2026, 7, 3, tzinfo=UTC)          # Jul 1, 2
    series = fill_series({}, start, end)
    assert [b["date"] for b in series] == ["2026-07-01", "2026-07-02"]
    assert all(b["count"] == 0 for b in series)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_date_range.py -k fill_series -v`
Expected: FAIL — `ImportError: cannot import name 'fill_series'`

- [ ] **Step 3: Implement**

Append to `src/prooflens/api/date_range.py`:

```python
def fill_series(by_day: dict[str, list], start: datetime, end: datetime) -> list[dict]:
    """One per-day bucket for every calendar day in [start.date(), (end-1day).date()],
    oldest->newest. Days absent from ``by_day`` are zero-filled so charts render smoothly."""
    out: list[dict] = []
    day = start.date()
    last = (end - timedelta(days=1)).date()
    while day <= last:
        key = day.isoformat()
        rows = by_day.get(key, [])
        day_scores = [x.score for x in rows]
        out.append({
            "date": key,
            "count": len(rows),
            "clear": sum(1 for x in rows if x.band == "Clear"),
            "doubtful": sum(1 for x in rows if x.band == "Doubtful"),
            "suspect": sum(1 for x in rows if x.band == "Suspect"),
            "avg_score": round(sum(day_scores) / len(day_scores), 1) if day_scores else 0,
        })
        day += timedelta(days=1)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_date_range.py -k fill_series -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/prooflens/api/date_range.py tests/unit/test_date_range.py
git commit -m "feat(api): fill_series — zero-fill empty days across the range"
```

---

### Task 3: Wire the endpoint (resolve_range + gap-filled series)

**Files:**
- Modify: `src/prooflens/api/scoring.py` (`analytics_summary`)
- Test: `tests/integration/test_scoring_api.py`

**Interfaces:**
- Consumes: `resolve_range`, `fill_series` (Tasks 1-2).
- Produces: same response shape; `series` now dense; 400 on invalid dates.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/integration/test_scoring_api.py
def test_analytics_default_30_days_dense_series(client):
    _upload(client, "meeting.jpg")
    body = client.get("/v1/analytics/summary").json()
    # default range = last 30 days -> 30 daily buckets, oldest->newest, last is today
    assert len(body["series"]) == 30
    from datetime import date
    assert body["series"][-1]["date"] == date.today().isoformat()
    assert body["total"] >= 1

def test_analytics_future_end_date_400(client):
    from datetime import date, timedelta
    fut = (date.today() + timedelta(days=1)).isoformat()
    r = client.get(f"/v1/analytics/summary?end_date={fut}")
    assert r.status_code == 400

def test_analytics_start_after_end_400(client):
    r = client.get("/v1/analytics/summary?start_date=2026-06-10&end_date=2026-06-01")
    assert r.status_code == 400

def test_analytics_span_over_400_days_400(client):
    r = client.get("/v1/analytics/summary?start_date=2020-01-01&end_date=2026-01-01")
    assert r.status_code == 400

def test_analytics_gap_filled_series_has_zero_days(client):
    _upload(client, "meeting.jpg")   # today only
    from datetime import date, timedelta
    start = (date.today() - timedelta(days=4)).isoformat()
    end = date.today().isoformat()
    body = client.get(f"/v1/analytics/summary?start_date={start}&end_date={end}").json()
    assert len(body["series"]) == 5                       # 5 contiguous days
    assert body["series"][0]["count"] == 0                # 4 days ago, no data
    assert body["series"][-1]["count"] >= 1               # today has the upload
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/integration/test_scoring_api.py -k "default_30 or future_end or start_after_end or span_over or gap_filled" -v`
Expected: FAIL — default series isn't dense / future date isn't rejected yet.

- [ ] **Step 3: Implement the endpoint change**

In `src/prooflens/api/scoring.py`, update the import:

```python
from .date_range import resolve_range, fill_series
```
(remove the now-unused `parse_bound` import if nothing else uses it in this file.)

Replace the parse block + the old per-day `series` construction in `analytics_summary`:

```python
    try:
        start, end = resolve_range(start_date, end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    items, total = repo.list_results(limit=5000, offset=0, start=start, end=end)
```
...and where the old `by_day`/`series` loop was:
```python
    by_day: dict[str, list] = {}
    for r in items:
        by_day.setdefault((r.created_at or "")[:10], []).append(r)
    series = fill_series(by_day, start, end)
```
Leave every other aggregate (bands, reason_counts, scores, images_today, top_reasons, the response dict) unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/integration/test_scoring_api.py -k "default_30 or future_end or start_after_end or span_over or gap_filled" -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Fix any pre-existing analytics test broken by the new default**

The pre-existing `test_results_and_analytics_populate` uploads "today" images with no params. Under the 30-day default those are still in-range, so `total` assertions hold — but if it asserts an exact `series` length (previously = number of days with data), update it to expect the dense 30-day series (or assert on the last bucket). Run the whole file:

Run: `.venv/bin/python -m pytest tests/integration/test_scoring_api.py -q`
Expected: PASS (adjust only the assertions the new dense-series/default behavior legitimately changes).

- [ ] **Step 6: Commit**

```bash
git add src/prooflens/api/scoring.py tests/integration/test_scoring_api.py
git commit -m "feat(api): analytics defaults to 30 days, validates dates, gap-fills series"
```

---

### Task 4: Full-suite gate + lint (matching CI) + OpenAPI

- [ ] **Step 1: Full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 2: Lint + types over the SAME paths CI uses**

Run: `.venv/bin/ruff check src tests scripts migrations && .venv/bin/mypy src`
Expected: clean. (CI runs `ruff check src tests scripts migrations` — lint all four, not just `src tests`.)

- [ ] **Step 3: Confirm OpenAPI still exposes the params (unchanged surface)**

Run:
```bash
PYTHONPATH=src .venv/bin/python -c "
from prooflens.api.app import create_app
p = create_app().openapi()['paths']['/v1/analytics/summary']['get'].get('parameters', [])
print(sorted(x['name'] for x in p))
"
```
Expected: `['end_date', 'start_date']` (no new params; behavior changed, not the surface).

- [ ] **Step 4: Commit any fixups**

If Steps 1-2 required changes, commit them. No OpenAPI/`gen:api` change is needed beyond PR #8 (params already present), but the **response `series` is now dense** — note this for the frontend in the PR description.

---

## Self-Review

- **Spec coverage:** validation→400 incl. future/order/span (Task 1); gap-fill (Task 2); 30-day default + endpoint wiring + metrics-already-filtered (Task 3); suite/lint/OpenAPI gate (Task 4). All spec goals mapped.
- **Placeholder scan:** none — every code step shows complete code; Task 3 Step 5 flags a real, specific pre-existing test that may need an assertion update rather than a vague "fix tests".
- **Type consistency:** `resolve_range(start_date, end_date) -> (datetime, datetime)` and `fill_series(by_day, start, end) -> list[dict]` used identically in Tasks 1-3; the endpoint passes `resolve_range`'s output straight to `list_results` and `fill_series`.
